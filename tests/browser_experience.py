"""Visible personalization evidence; use an isolated DB, one bounded Chromium."""
import json
import os
from pathlib import Path

from playwright.sync_api import expect,sync_playwright

base=os.getenv('TEST_BASE_URL','http://127.0.0.1:8011')
out=Path(os.getenv('TEST_SCREENSHOT_DIR','/tmp/taobao-experience-preview'));out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1000})
    page=context.new_page();page.set_default_timeout(30000);errors=[];flows=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(base,wait_until='domcontentloaded')
    page.locator('.native-profile-choices button').first.wait_for()
    expect(page.locator('.native-profile-choices button')).to_have_count(8)
    expect(page.locator('.native-hero')).to_contain_text('8.192')
    page.locator('[data-action="native-compare-profiles"]').first.click()
    page.locator('.native-profile-columns').wait_for()
    expect(page.locator('.native-profile-columns .native-mini')).to_have_count(12)
    expect(page.locator('.native-compare-result')).to_contain_text('mẫu trùng')
    assert context.request.get(base+'/api/auth/me').json()['user'] is None
    page.select_option('#native-compare-right','1')
    expect(page.locator('#native-profile-comparison')).to_contain_text('Chọn hai hồ sơ khác nhau')
    page.select_option('#native-compare-right','3')
    page.locator('.native-profile-columns').wait_for()
    for width in (320,390,768,1440):
        page.set_viewport_size({'width':width,'height':900})
        assert page.locator('#modal').evaluate('(el)=>el.scrollWidth<=el.clientWidth'),width
        page.screenshot(path=str(out/f'compare-{width}.png'))
    page.locator('#modal [data-action="close-modal"]').click()
    flows.append('guest compares real profiles without login or synthetic events; comparison fits four sizes')

    page.set_viewport_size({'width':1440,'height':1000})
    with page.expect_response(lambda r:'/api/recommendations?limit=' in r.url and r.ok):
        page.locator('.native-profile-choices [data-id="4"]').click()
    page.locator('.native-profile-story').wait_for()
    expect(page.locator('.native-history-story')).to_contain_text('Minh Tuấn')
    expect(page.locator('.native-story-counts')).to_contain_text('1.000')
    expect(page.locator('.native-interest-bars button')).to_have_count(4)
    summary=context.request.get(base+'/api/recommendations/experience').json()
    first=summary['top_groups'][0]
    expect(page.locator('.native-interest-bars button').first).to_contain_text(str(first['events'])+' lượt')
    page.locator('#native-evidence').evaluate('(el)=>el.scrollIntoView({block:"start"})')
    page.screenshot(path=str(out/'history-desktop.png'))
    flows.append('visible history group counts match original source inputs')

    before=page.locator('#home-products .product-card-main').evaluate_all('(xs)=>xs.slice(0,12).map(x=>Number(x.dataset.id))')
    clicked=before[0]
    with page.expect_response(lambda r:'/api/recommendations?limit=' in r.url and r.ok) as response:
        page.locator(f'#home-products .product-card-main[data-id="{clicked}"]').click()
    result=response.value.json();after=[p['id'] for p in result['items'][:12]]
    new_count=len(set(after)-set(before))
    assert clicked not in after
    page.locator('#similar-products .product-card').first.wait_for()
    page.locator('[data-action="native-result"]').click()
    expect(page.locator('.native-change-card')).to_contain_text(f'{new_count} mẫu mới')
    expect(page.locator('.native-before-after')).to_contain_text('TRƯỚC THAO TÁC')
    expect(page.locator('.native-change-card')).to_contain_text('bỏ qua mẫu đã xem')
    page.locator('#native-neighbours .native-mini').first.wait_for()
    expect(page.locator('.native-activity-list button').first).to_have_attribute('data-id',str(clicked))
    page.screenshot(path=str(out/'actual-change-desktop.png'))
    flows.append('before/after count equals actual ranking change; viewed sample disappears and recent neighbours load')

    # Failure after a real click keeps an honest old-list message and supports retry.
    def unavailable(route):
        route.fulfill(status=503,content_type='application/json',body='{"detail":"Gợi ý đang bận"}')
    page.route('**/api/recommendations?limit=*',unavailable)
    page.locator('#home-products .product-card-main').first.click()
    page.locator('#similar-products .product-card').first.wait_for()
    page.locator('[data-action="native-result"]').click()
    expect(page.locator('.native-change-card')).to_contain_text('Chưa tải được danh sách mới')
    expect(page.locator('#home-products')).to_have_attribute('aria-busy','false')
    page.unroute('**/api/recommendations?limit=*',unavailable)
    page.locator('[data-action="native-refresh"]').click()
    expect(page.locator('.native-change-card')).not_to_contain_text('Chưa tải được danh sách mới')
    expect(page.locator('.native-change-card')).to_contain_text('mẫu mới')
    flows.append('failed refresh is disclosed and retry completes the original real comparison')

    for width in (320,390,768,1440):
        page.set_viewport_size({'width':width,'height':900})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        page.locator('#native-evidence').evaluate('(el)=>el.scrollIntoView({block:"start"})')
        page.screenshot(path=str(out/f'evidence-{width}.png'))
        page.locator('#native-context').evaluate('(el)=>el.scrollIntoView({block:"start"})')
        page.screenshot(path=str(out/f'changes-{width}.png'))
    assert context.request.get(base+'/api/auth/me').json()['user']['id']==4
    assert not errors,errors
    result={'status':'passed','flows':flows,'javascript_errors':errors,'screenshots':str(out)}
    (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False));browser.close()
