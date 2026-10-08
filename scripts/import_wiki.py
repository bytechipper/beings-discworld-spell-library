#!/usr/bin/env python3
"""Import a local Discworld wiki backup. Not needed to build the shipped archive."""
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
from bs4 import BeautifulSoup, Comment, Tag
import argparse
import json
import re

ROOT = Path(__file__).resolve().parent.parent
BASE = 'https://dwwiki.mooo.com/wiki/'
ALLOWED = {'p','div','span','h1','h2','h3','h4','h5','ul','ol','li','dl','dt','dd','b','strong','i','em','code','tt','pre','br','hr','table','thead','tbody','tr','th','td','sup','sub','a','blockquote'}

def plain(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip()

def clean_content(content):
    soup = BeautifulSoup(str(content), 'html.parser')
    for node in soup.select('script, style, iframe, object, embed, form, input, button, .toc, .navbox, .mw-editsection, .hid, .tooltiptext, .tooltip-content, .infobox'):
        node.decompose()
    for node in soup.find_all(string=lambda s: isinstance(s, Comment)):
        node.extract()
    for node in list(soup.find_all(True)):
        if node.name not in ALLOWED:
            node.unwrap()
            continue
        attrs = {}
        if node.name in ('td','th'):
            for key in ('colspan','rowspan'):
                if str(node.get(key,'')).isdigit(): attrs[key] = node[key]
        if node.name == 'a':
            href = urljoin(BASE, node.get('href',''))
            parts = urlsplit(href)
            if parts.netloc == 'dwwiki.mooo.com' and parts.path.endswith('.html'):
                href = href.replace('.html', '', 1)
            if urlsplit(href).scheme in ('https','http'):
                attrs.update(href=href, target='_blank', rel='noopener noreferrer')
        # Keep chart colors and widths; discard arbitrary CSS and positioning.
        style = node.get('style','')
        safe = []
        for prop, value in re.findall(r'([\w-]+)\s*:\s*([^;]+)',style):
            if node.name == 'td' and prop == 'background-color' and value.strip().upper() in {'#FF0000','#FF3300','#FF6600','#FF9A00','#FFCD00','#FFFF00','#CDFF00','#9AFF00','#66FF00','#33FF00','#00FF00'}: safe.append(prop+':'+value.strip())
            if prop == 'width' and re.fullmatch(r'\d+(?:\.\d+)?px',value.strip()): safe.append(prop+':'+value.strip())
        if safe: attrs['style'] = ';'.join(safe)
        node.attrs = attrs
    return ''.join(str(x) for x in soup.contents)

def chart_bonuses(content):
    results = []
    # The wiki's colored charts draw bonus along a linear pixel scale.
    for table in content.find_all('table'):
        if table.find_parent('table') or table.get('class') == ['infobox']: continue
        label = plain(table)
        if not ('Spellcheck results' in label or 'Focus tea results' in label): continue
        scale = None
        for row in table.find_all('tr'):
            cells = row.find_all('td',recursive=False)
            numbers = [plain(c) for c in cells]
            if len(numbers)>=5 and all(re.fullmatch(r'\d+',x) for x in numbers): scale = (int(numbers[0]),int(numbers[-1])); break
        if scale is None: continue
        for inner in table.find_all('table'):
            skill = inner.find('a',href=re.compile('Magic\\.'))
            if skill is None: continue
            colored = []
            for cell in inner.find_all('td'):
                style=cell.get('style',''); color=re.search(r'background-color:\s*(#[\da-fA-F]{6})',style); width=re.search(r'(?:^|;)\s*width:\s*([\d.]+)px',style)
                if color and width: colored.append((color[1].upper(),float(width[1])))
            total=sum(w for c,w in colored)
            if not total: continue
            start = 0
            for color,width in colored:
                if color == '#00FF00':
                    bonus=scale[0]+(scale[1]-scale[0])*start/total
                    results.append({'skill':unquote(urlsplit(skill['href']).path).removesuffix('.html').split('/')[-1].lower(), 'green_from':round(bonus,1), 'chart': 'Focus tea' if 'Focus tea' in label else 'Spellcheck'})
                    break
                start += width
    return results

def load(path):
    if not path.is_file(): raise ValueError(f'Missing wiki page: {path}')
    soup=BeautifulSoup(path.read_text(), 'html.parser')
    content=soup.select_one('#mw-content-text')
    if content is None: raise ValueError(f'Missing article in {path}')
    for node in content.select('.hid'): node.decompose()
    return soup, content

def generate(wiki):
    _, index = load(wiki/'Spells.html')
    spells={}
    for table, guild in zip(index.select('table.wikitable'),['Wizard','Witch']):
        for row in table.find_all('tr'):
            cells=row.find_all('td',recursive=False)
            if len(cells)!=10 or not cells[0].find('a'): continue
            link=cells[0].find('a'); name=plain(link); filename=unquote(link['href'])
            record=spells.setdefault(name, {'name':name, 'guilds':[], 'page':filename})
            record['guilds'].append(guild)
            record.update(abbreviation=plain(cells[1]), gp=plain(cells[2]), size=plain(cells[3]), efficiency=plain(cells[4]), extra_target_gp=plain(cells[5]), type=plain(cells[6]), description=plain(cells[7]), components=plain(cells[8]))
            key='tomes' if guild=='Wizard' else 'crystals'
            record[key]=[{'name':plain(a),'page':unquote(a['href'])} for a in cells[9].find_all('a')]
            if not record[key] and plain(cells[9]): record[key]=[{'name':plain(cells[9]), 'page':None}]
    for record in spells.values():
        soup, content=load(wiki/record.pop('page'))
        for box in content.select('.infobox'):
            title=box.find('th')
            if title and plain(title)==record['name']:
                record['facts']={plain(cells[0]):plain(cells[1]) for row in box.find_all('tr') if len(cells:=row.find_all('td',recursive=False))==2}
                break
        record.setdefault('facts',{})
        record['bonuses']=chart_bonuses(content)
        record['skills']=[]
        headings=content.find_all(re.compile('^h[1-5]$'))
        # AshkEnte pages share an article: select this spell's Skills section.
        target=next((h for h in headings if plain(h)==record['name']), None)
        candidates=target.find_all_next(re.compile('^h[1-5]$')) if target else headings
        for heading in candidates:
            if plain(heading).lower()=='skills':
                for node in heading.next_siblings:
                    if isinstance(node,Tag) and re.fullmatch('h[1-5]',node.name): break
                    if isinstance(node,Tag) and node.name in ('ul','ol'):
                        record['skills'].extend(plain(li) for li in node.find_all('li',recursive=False))
                break
        record['article']=clean_content(content)
        record['source']=BASE+record['name'].replace(' ','_')
        match=re.search(r'"wgRevisionId":(\d+)',soup.decode())
        record['revision']=int(match[1]) if match else None
        footer=soup.select_one('#lastmod'); record['modified']=plain(footer) if footer else ''
        record['learning']=[]
        for tome in record.get('tomes',[]):
            if tome['page']:
                _, book=load(wiki/tome['page'])
                record['learning'].append({'name':tome['name'],'source':BASE+tome['name'].replace(' ','_'),'article':clean_content(book)})
        # Retain the article's acquisition text independently for a quick overview.
        acquisition=[]; collecting=False
        for node in content.children:
            if not isinstance(node,Tag): continue
            if node.name in ('h1','h2','h3'):
                collecting=plain(node).casefold() in ('acquisition','learning','obtaining','availability')
            elif collecting: acquisition.append(plain(node))
        record['acquisition']='\n'.join(acquisition)
    return {'schema':1, 'source':BASE+'Spells', 'coverage':'All current spells listed in the backed-up Spells index (wizard and witch tables). Lost/retired spells are not listed.', 'spells':sorted(spells.values(),key=lambda s:s['name'].casefold())}

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('wiki',type=Path); args=parser.parse_args()
    library=generate(args.wiki)
    output=ROOT/'ui/spells.js'
    output.write_text('"use strict";\nwindow.SPELL_LIBRARY = '+json.dumps(library,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n')
    print(f'Imported {len(library["spells"])} spells into {output}')
