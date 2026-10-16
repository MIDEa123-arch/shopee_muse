"""Focused commerce behaviour on a disposable database, one Chromium process."""
import json
import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

base=os.getenv('TEST_BASE_URL','http://127.0.0.1:8011')
out=Path(os.getenv('TEST_SCREENSHOT_DIR','/tmp/lumi-context-preview'));out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(args=['--no-sandbox']);context=browser.new_context(viewport={'width':1440,'height':1000})
    page=context.new_page();page.set_default_timeout(30000);errors=[];flows=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    def request(path):
        response=context.request.get(base+'/api'+path);assert response.ok,(path,response.status)
        return response.json()
    def assert_clean():
        assert not re.search(r'\bSKU\b|TB-\d{4,}|[\u3400-\u9fff]',page.locator('body').inner_text())
        assert 'MUSE' not in page.locator('body').inner_text()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    def choose(query,kind):
        page.fill('#search',query);page.locator('#search-form button').click()
        page.locator('#catalog-products .store-card').first.wait_for()
        page.locator('#catalog-products .product-card-main').first.click()
        page.locator('#similar-products .store-card').first.wait_for()
        kinds=page.locator('#similar-products .store-card').evaluate_all('(xs)=>xs.map(x=>x.dataset.productType)')
        assert all(x==kind for x in kinds),(query,kinds)
        assert_clean();page.locator('#modal [data-action="close-modal"]').click()
        page.locator('.brand').click();page.locator('#store-focus strong').wait_for()
        page.locator('#home-products .store-card').first.wait_for()
        assert all(x==kind for x in page.locator('#home-products .store-card').evaluate_all('(xs)=>xs.map(x=>x.dataset.productType)'))
        templates=page.locator('#home-products .store-card').evaluate_all('(xs)=>xs.map(x=>x.dataset.templateId)')
        assert len(templates)==len(set(templates))
        assert_clean()
    page.goto(base);page.locator('#home-products .store-card').first.wait_for()
    assert request('/auth/me')['user'] is None
    choose('iPhone','smartphones')
    expect(page.locator('#store-focus')).to_contain_text('Điện thoại')
    assert request('/auth/me')['user'] is None
    flows.append('guest sees phone-only related and continuation lists without login or fake history')
    page.locator('#store-focus [data-action="store-all-categories"]').click()
    expect(page.locator('#store-focus')).to_be_empty()
    assert len(set(page.locator('#home-products .store-card').evaluate_all('(xs)=>xs.map(x=>x.dataset.productType)')))>1
    flows.append('clear focus restores broad discovery with unique photographs')

    page.select_option('#profile-switch','1');expect(page.locator('#profile-switch')).to_be_enabled();page.locator('#home-products .store-card').first.wait_for()
    choose('iPhone','smartphones')
    meta=request('/recommendations?presentation_policy=contextual')['meta']
    assert meta['model_used'] and meta['merchandise_context']['source']=='recent_web_action'
    page.reload();page.locator('#store-focus strong').wait_for();expect(page.locator('#store-focus')).to_contain_text('Điện thoại')
    assert all(x=='smartphones' for x in page.locator('#home-products .store-card').evaluate_all('(xs)=>xs.map(x=>x.dataset.productType)'))
    flows.append('authenticated phone interest persists across reload using a real recorded action')
    page.locator('.debug-toggle').click()
    page.locator('#debug-panel').get_by_text('CHECKPOINT LOADED').wait_for()
    page.locator('#debug-panel [data-action="muse-info"]').click()
    page.locator('#modal [data-action="store-original-ranking"]').click()
    expect(page.locator('#modal')).to_contain_text('Trước lớp lọc commerce')
    expect(page.locator('#modal .lab-score-table tbody tr')).to_have_count(24)
    page.locator('#modal [data-action="close-modal"]').click();page.locator('.debug-toggle').click()
    flows.append('raw IDs and unfiltered checkpoint ranks are available only in Lab')
    for width in (320,390,768,1440):
        page.set_viewport_size({'width':width,'height':900})
        page.locator('#discovery').evaluate('(x)=>x.scrollIntoView({block:"start"})');assert_clean()
        page.screenshot(path=str(out/f'focused-feed-{width}.png'))
    page.set_viewport_size({'width':1440,'height':1000})
    def fallback(route):
        response=route.fetch();data=response.json();data['meta']['model_used']=False;data['quality']={'available':False}
        for item in data['items']:item['recommendation_source']='catalog';item.pop('p_click',None)
        route.fulfill(response=response,json=data)
    page.route('**/api/recommendations?limit=*',fallback)
    page.reload();page.locator('#home-products .store-card').first.wait_for()
    expect(page.locator('#recommendation-explainer')).to_contain_text('AI tạm thời chưa khả dụng')
    assert page.locator('#home-products .store-ai-tag').count()==0
    assert all(x=='smartphones' for x in page.locator('#home-products .store-card').evaluate_all('(xs)=>xs.map(x=>x.dataset.productType)'))
    page.unroute('**/api/recommendations?limit=*',fallback)
    flows.append('model fallback keeps topic constraints and removes the AI badge')
    page.locator('[data-action="store-home-category"][data-value="beauty"]').click()
    expect(page.locator('#discovery .recommend-title p')).to_contain_text('Làm đẹp')
    assert all(x=='beauty' for x in page.locator('#home-products .store-card').evaluate_all('(xs)=>xs.map(x=>x.dataset.displayCategory)'))
    flows.append('manual category overrides automatic focus without unrelated filling')
    choose('Laptop','laptops')
    expect(page.locator('.native-change-card')).to_contain_text('Gợi ý tiếp nối:')
    flows.append('a new product type switches focus and explicitly explains the scope change')

    # Duplicate names/photos do not make many pages of the same item.
    page.fill('#search','tai nghe');page.locator('#search-form button').click()
    page.locator('#catalog-products .store-card').first.wait_for()
    cards=page.locator('#catalog-products .store-card').evaluate_all('(xs)=>xs.map(x=>x.dataset.templateId)')
    assert len(cards)==len(set(cards))==3,cards
    flows.append('search exposes three distinct headphone products and no product codes')
    # A singleton type produces a clear empty state rather than unrelated products.
    page.fill('#search','ốp iPhone');page.locator('#search-form button').click()
    page.locator('#catalog-products .product-card-main').first.click()
    expect(page.locator('#similar-products')).to_contain_text('Chưa có lựa chọn khác cùng loại')
    assert page.locator('#similar-products .store-card').count()==0
    page.locator('#modal [data-action="close-modal"]').click();page.locator('.brand').click()
    expect(page.locator('#home-products')).to_contain_text('Chưa có sản phẩm khác')
    page.locator('#home-products [data-action="store-all-categories"]').click()
    page.locator('#home-products .store-card').first.wait_for();assert_clean()
    flows.append('singleton type stays empty and offers an explicit route back to all products')
    assert not errors,errors
    result={'status':'passed','flows':flows,'javascript_errors':errors}
    (out/'context-browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False));browser.close()
