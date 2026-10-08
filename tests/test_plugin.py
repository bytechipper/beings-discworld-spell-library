import ctypes
import ctypes.util
import importlib.util
import json
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT/'ui/spells.js').read_text().split(' = ',1)[1].removesuffix(';\n'))
SPELLS = DATA['spells']
BY_NAME = {s['name']:s for s in SPELLS}

class MarkupAudit(HTMLParser):
    def handle_starttag(self, tag, attrs):
        allowed={'p','div','span','h1','h2','h3','h4','h5','ul','ol','li','dl','dt','dd','b','strong','i','em','code','tt','pre','br','hr','table','thead','tbody','tr','th','td','sup','sub','a','blockquote'}
        assert tag in allowed, tag
        for key,value in attrs:
            assert key in {'href','target','rel','style','colspan','rowspan'}, (key,value)
            if key=='href': assert value.startswith(('https://','http://')), value
            if key=='style': assert not any(x in value.lower() for x in ['url','expression','position','javascript']), value

class PluginTests(unittest.TestCase):
    def test_spell_coverage_and_sorting(self):
        self.assertEqual(len(SPELLS),116)
        self.assertEqual(len(BY_NAME),116)
        self.assertEqual([s['name'] for s in SPELLS],sorted(BY_NAME,key=str.casefold))
        self.assertEqual(sum('Wizard' in s['guilds'] for s in SPELLS),93)
        self.assertEqual(sum('Witch' in s['guilds'] for s in SPELLS),24)
        self.assertEqual(BY_NAME["Jorodin's Magnificent Communicator"]['guilds'],['Wizard','Witch'])
        for s in SPELLS:
            self.assertIn(s['type'],['Miscellaneous','Offensive','Defensive'])
            for field in ['name','abbreviation','gp','size','description','components','article','skills','source','revision']:
                self.assertTrue(s[field],(s['name'],field))
            self.assertNotIn('&&&&',s['gp'])

    def test_details_and_learning_sources(self):
        s=BY_NAME['Amazing Silicate Blorpler']
        self.assertEqual((s['gp'],s['size'],s['abbreviation']),('10','5','asb'))
        self.assertEqual(s['tomes'][0]['name'],"Begynners' Magick")
        self.assertIn('gym',s['learning'][0]['article'])
        self.assertIn('Magic.methods.physical.evoking',s['skills'])
        self.assertIn('Casting messages',s['article'])
        bees=BY_NAME["Mother Feelbright's Busy Bees"]
        self.assertIn('140 levels',bees['acquisition'])
        self.assertIn('Granny Weatherwax',bees['acquisition'])
        self.assertIn('honey',bees['components'])
        self.assertIn('magic.items.held.staff',BY_NAME["Malich's AshkEnte Circle"]['skills'])

    def test_bonus_chart_scale(self):
        s=BY_NAME['Amazing Silicate Blorpler']
        self.assertEqual([b['green_from'] for b in s['bonuses']],[155.1,135.1,155.1,145.1,145.1])
        # Ensure parsing uses the actual width, not border-top-width:0px.
        self.assertNotEqual(s['bonuses'][0]['green_from'],200)
        self.assertEqual(len(s['bonuses']),len(s['skills']))

    def test_bundled_html_is_inert(self):
        for s in SPELLS:
            MarkupAudit().feed(s['article'])
            for book in s['learning']: MarkupAudit().feed(book['article'])

    def test_importer_sanitizes_active_markup(self):
        spec=importlib.util.spec_from_file_location('import_wiki',ROOT/'scripts/import_wiki.py')
        importer=importlib.util.module_from_spec(spec); spec.loader.exec_module(importer)
        from bs4 import BeautifulSoup
        malicious=BeautifulSoup('<div><script>alert(1)</script><img src=x onerror=alert(1)><a href="javascript:alert(1)" onclick="alert(2)">text</a><p style="position:fixed;background:url(x)">safe</p><a href="Rock.html">rock</a></div>','html.parser')
        safe=importer.clean_content(malicious)
        MarkupAudit().feed(safe)
        self.assertNotIn('alert(',safe)
        self.assertNotIn('position',safe)
        self.assertIn('https://dwwiki.mooo.com/wiki/Rock',safe)
        self.assertNotIn('Rock.html',safe)

    def test_lua_entry(self):
        lib=ctypes.CDLL(ctypes.util.find_library('lua5.4'))
        for name,args,result in [('luaL_newstate',[],ctypes.c_void_p),('luaL_openlibs',[ctypes.c_void_p],None),('luaL_loadstring',[ctypes.c_void_p,ctypes.c_char_p],ctypes.c_int),('lua_pcallk',[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_longlong,ctypes.c_void_p],ctypes.c_int),('lua_tolstring',[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p],ctypes.c_char_p),('lua_close',[ctypes.c_void_p],None)]:
            fn=getattr(lib,name);fn.argtypes=args;fn.restype=result
        state=lib.luaL_newstate();lib.luaL_openlibs(state)
        code='local called=false; mud={panel=function(id) assert(id=="net-placeholder"); called=true; return {} end}; '+(ROOT/'src/main.lua').read_text()+'; assert(called)'
        code=code.replace('net-placeholder','beings-discworld-spell-library')
        try:
            result=lib.luaL_loadstring(state,code.encode()) or lib.lua_pcallk(state,0,0,0,0,None)
            self.assertEqual(result,0,lib.lua_tolstring(state,-1,None))
        finally: lib.lua_close(state)

    def test_manifest_permissions_and_panel(self):
        m=tomllib.loads((ROOT/'plugin.toml').read_text())
        self.assertEqual(m['name'],"Being's Discworld Spell Library")
        self.assertFalse(any(m['permissions'].values()))
        self.assertTrue((ROOT/m['entry']).is_file())
        self.assertTrue((ROOT/m['panels']['beings-discworld-spell-library']['entry']).is_file())

    def test_clean_reproducible_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[Path(tmp)/name for name in ['a.mallardx','b.mallardx']]
            for p in paths: subprocess.run([sys.executable,str(ROOT/'scripts/build.py'),str(p)],check=True,capture_output=True)
            self.assertEqual(paths[0].read_bytes(),paths[1].read_bytes())
            with zipfile.ZipFile(paths[0]) as z:
                self.assertIn('ui/spells.js',z.namelist());self.assertIn('NOTICE',z.namelist())
                for name in z.namelist():
                    self.assertTrue(name in ['plugin.toml','LICENSE','README.md','NOTICE'] or name.startswith(('src/','ui/')),name)
                    self.assertEqual(z.read(name),(ROOT/name).read_bytes())
