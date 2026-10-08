"""Exercise the offline library in Chromium, including every spell popup."""
from pathlib import Path
import sys
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent.parent
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':420,'height':560})
    errors=[]; network=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.route('http://**',lambda route:(network.append(route.request.url),route.abort()))
    page.route('https://**',lambda route:(network.append(route.request.url),route.abort()))
    page.goto((ROOT/'ui/panel.html').as_uri())
    assert page.locator('.spell-row').count()==116
    assert page.locator('.spell-name').first.inner_text()=='A Cup of Tea and Sake'
    assert page.locator('#count').inner_text()=='116'
    assert page.locator('#start,#stop,.go-btn,.see-btn,.remove-btn').count()==0
    if len(sys.argv)>1: page.screenshot(path=str(Path(sys.argv[1])/'library-preview.png'))
    page.locator('#search').fill('ASB')
    assert page.locator('.spell-row').count()==1
    page.locator('.spell-row').click()
    assert page.locator('#spell-dialog').evaluate('(d)=>d.open')
    assert page.locator('#detail-title').inner_text()=='Amazing Silicate Blorpler'
    assert page.locator('#detail-tags .guild-wizard').count()==1
    assert page.locator('#detail-content').get_by_text('155.1',exact=False).count()>0
    assert page.locator('#detail-content').get_by_text("Begynners' Magick",exact=False).count()>0
    page.locator('summary').get_by_text("Begynners' Magick",exact=False).click()
    assert page.locator('details[open]').inner_text().find('gym')>=0
    if len(sys.argv)>1: page.screenshot(path=str(Path(sys.argv[1])/'spell-preview.png'))
    page.keyboard.press('Escape')
    assert not page.locator('#spell-dialog').evaluate('(d)=>d.open')
    assert page.locator('.spell-row').evaluate('(b)=>document.activeElement===b')
    page.locator('#search').fill('jmc'); page.locator('.spell-row').click()
    assert page.locator('#detail-tags .guild-wizard').count()==1
    assert page.locator('#detail-tags .guild-witch').count()==1
    page.locator('#close-detail').click()
    page.locator('#clear-search').click()
    page.locator('#guild').select_option('Witch');page.locator('#type').select_option('Offensive')
    assert page.locator('.spell-row').count()==3
    assert page.locator('.spell-row .guild-witch').count()==3
    page.locator('#search').fill('mfbb');page.locator('.spell-row').click()
    assert '140 levels' in page.locator('#detail-content').inner_text()
    assert 'Granny Weatherwax' in page.locator('#detail-content').inner_text()
    page.locator('#close-detail').click()
    page.locator('#search').fill('nonexistent spell');assert page.locator('#empty').is_visible()
    page.locator('#search').fill('');page.locator('#guild').select_option('');page.locator('#type').select_option('')
    assert page.locator('.spell-row').count()==116
    # All records can open without exceptions, including the two AshkEnte spells.
    page.evaluate('''() => { for (const button of document.querySelectorAll('.spell-row')) {
        button.click(); const d=document.getElementById('spell-dialog');
        if (!d.open || !document.getElementById('detail-title').textContent) throw new Error('Missing detail');
        d.close();
    }}''')
    page.set_viewport_size({'width':300,'height':480})
    page.locator('.spell-row').first.click()
    assert page.locator('#spell-dialog').bounding_box()['width']<=300
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.keyboard.press('Escape')
    page.add_style_tag(content=':root { --mallard-bg:#fff; --mallard-fg:#222; --mallard-bg-elevated:#eee; --mallard-border:#ccc; --mallard-fg-muted:#555; }')
    page.locator('.spell-row').first.click();page.locator('#close-detail').click()
    assert not errors,errors
    assert not network,network
    browser.close()
print('PASS: 116 offline spell popups, search, filters, guild labels, learning sources, bonus data, keyboard, narrow layout, and theme')
