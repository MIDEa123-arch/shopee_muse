"""Focused visual demo check. Run against a server backed by an isolated database."""
import json
import os
from pathlib import Path

from playwright.sync_api import expect,sync_playwright


base=os.getenv('TEST_BASE_URL','http://127.0.0.1:8011')
output=Path(os.getenv('TEST_SCREENSHOT_DIR','/tmp/shopee-muse-preview'))
output.mkdir(parents=True,exist_ok=True)

with sync_playwright() as playwright:
    browser=playwright.chromium.launch(headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1050})
    page=context.new_page();errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))

    response=context.request.post(base+'/api/auth/demo-login',data={'user_id':1})
    assert response.ok,response.text()

    page.goto(base,wait_until='domcontentloaded')
    page.locator('#home-products .product-card').first.wait_for()
    context.request.delete(base+'/api/recommendations/demo-interest')
    page.reload(wait_until='domcontentloaded')
    page.locator('#demo-journey').wait_for()
    page.locator('#home-products .product-card').first.wait_for()

    customer_text=page.locator('#app').inner_text()
    for technical in ('P(click)','SCL COVERAGE','INFERENCE / SERVICE','RAW TAOBAO ID'):
        assert technical not in customer_text,technical
    assert page.locator('#debug-panel').is_hidden()
    assert page.locator('#home-products .product-score').count()==0

    before=page.locator('#home-products .product-card-main').evaluate_all(
        "cards => cards.slice(0,12).map(card => Number(card.dataset.id))")
    with page.expect_response(lambda response:'/api/recommendations?limit=' in response.url and response.ok):
        page.locator('.interest-chip[data-category="7"]').click()
    page.locator('.demo-result.success').wait_for()
    expect(page.locator('.demo-result.success')).to_contain_text('Đã cập nhật gợi ý cho bạn')
    expect(page.locator('#discovery .recommend-title')).to_contain_text('Ưu tiên Mỹ Phẩm & Sắc Đẹp')
    after=page.locator('#home-products .product-card-main').evaluate_all(
        "cards => cards.slice(0,12).map(card => Number(card.dataset.id))")
    assert before!=after,(before,after)
    categories=page.locator('#home-products .product-card').evaluate_all(
        "cards => cards.slice(0,3).map(card => Number(card.dataset.category))")
    assert categories==[7,7,7],categories
    assert page.locator('#home-products .recommendation-new').count()>0
    page.screenshot(path=str(output/'professor-demo-result.png'),full_page=True)

    page.locator('.debug-toggle').click()
    page.locator('#debug-panel').get_by_text('CHECKPOINT LOADED').wait_for()
    page.locator('#debug-panel .product-score').first.wait_for()
    expect(page.locator('#debug-panel')).to_contain_text('INFERENCE / SERVICE')
    page.locator('.debug-toggle').click()
    page.locator('#debug-panel').wait_for(state='hidden')
    assert page.locator('#home-products .product-score').count()==0

    page.set_viewport_size({'width':390,'height':844})
    page.reload(wait_until='domcontentloaded')
    page.locator('#demo-journey').wait_for()
    page.locator('#home-products .product-card').first.wait_for()
    page.locator('#recommendation-explainer [data-ai-used="true"]').wait_for()
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(output/'professor-demo-mobile.png'),full_page=True)
    assert not errors,errors
    print(json.dumps({'status':'passed','before':before,'after':after,'top_categories':categories,
                      'screenshots':str(output),'javascript_errors':errors},ensure_ascii=False))
    browser.close()
