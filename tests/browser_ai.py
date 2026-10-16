"""AI disclosure, failure states and profile isolation. Use an isolated test DB."""
import json
import os
import uuid
from pathlib import Path

from playwright.sync_api import expect,sync_playwright

base=os.getenv('TEST_BASE_URL','http://127.0.0.1:8011')
output=Path(os.getenv('TEST_SCREENSHOT_DIR','/tmp/shopee-muse-preview'))
output.mkdir(parents=True,exist_ok=True)

with sync_playwright() as playwright:
    browser=playwright.chromium.launch(headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1050})
    page=context.new_page();errors=[];flows=[]
    page.on('pageerror',lambda error:errors.append(str(error)))

    def home():
        # A unique document URL also clears any simulated failure response.
        page.goto(base+'/?ai-check='+uuid.uuid4().hex+'#/home',wait_until='domcontentloaded')
        page.locator('#home-products .product-card').first.wait_for()

    def customer_view():
        assert page.locator('#debug-panel').is_hidden()
        text=page.locator('body').inner_text()
        for technical in ('MUSE','P(click)','SCL COVERAGE','INFERENCE / SERVICE','RAW TAOBAO ID','GAUC'):
            assert technical not in text,technical
        assert page.locator('#home-products .product-score').count()==0
        badges=page.locator('#home-products .ai-product-badge').all_text_contents()
        assert all('%' not in text for text in badges),badges

    home();customer_view()
    assert context.request.get(base+'/api/auth/me').json()['user'] is None
    expect(page.locator('#recommendation-explainer')).to_contain_text('Đăng nhập để AI')
    assert page.locator('#home-products .ai-product-badge').count()==0
    page.reload();page.locator('#home-products .product-card').first.wait_for()
    assert context.request.get(base+'/api/auth/me').json()['user'] is None
    flows.append('guest stays logged out; popular suggestions have no AI badges')

    for user_id in range(1,9):
        with page.expect_response(lambda r:'/api/recommendations?limit=' in r.url and r.ok) as response:
            page.select_option('#profile-switch',str(user_id))
        result=response.value.json()
        assert result['meta']['model_used'],result['meta']
        assert result['meta']['history_length']==1000
        expect(page.locator('#home-products .ai-product-badge').first).to_be_visible()
        expect(page.locator('#recommendation-explainer')).to_contain_text('AI gợi ý cho bạn')
        assert context.request.get(base+'/api/auth/me').json()['user']['id']==user_id
        customer_view()
    flows.append('all eight profiles use real checkpoint inference and disclose AI')
    assert page.locator('#toasts .toast').count()<=3
    if page.locator('#toasts .toast').count():page.locator('#toasts .toast').last.wait_for(state='hidden')

    before=page.locator('#home-products .product-card-main').evaluate_all('(cards)=>cards.map(x=>x.dataset.id)')
    with page.expect_response(lambda r:'/api/recommendations?limit=36' in r.url and r.ok):
        page.locator('[data-action="home-more"]').click()
    expect(page.locator('#home-products .product-card')).to_have_count(36)
    after=page.locator('#home-products .product-card-main').evaluate_all('(cards)=>cards.map(x=>x.dataset.id)')
    assert after[:len(before)]==before
    flows.append('load more preserves previous recommendation order')

    page.locator('#recommendation-explainer [data-action="ai-info"]').click()
    expect(page.locator('#modal')).to_contain_text('không có nghĩa')
    expect(page.locator('#modal')).to_contain_text('Chưa có nhãn phản hồi mua sắm tiếng Việt')
    page.locator('#modal [data-action="close-modal"]').click()
    page.screenshot(path=str(output/'ai-customer-desktop.png'))
    page.locator('#discovery').evaluate('(el)=>el.scrollIntoView({block:"start"})')
    page.screenshot(path=str(output/'ai-feed-desktop.png'))

    page.locator('.debug-toggle').click()
    page.locator('#debug-panel').get_by_text('CHECKPOINT LOADED').wait_for()
    expect(page.locator('#debug-panel .lab-evaluation')).to_contain_text('AUC / GAUC')
    expect(page.locator('#debug-panel .lab-evaluation')).to_contain_text('NO-CLICK BASELINE')
    page.screenshot(path=str(output/'ai-lab-evaluation.png'))
    page.locator('.debug-toggle').click();customer_view()
    flows.append('quality explanation is readable; metrics exist only inside Lab')

    page.goto(base+'/#/catalog?sort=relevance&page=6',wait_until='domcontentloaded')
    page.locator('#catalog-products .product-card').first.wait_for()
    expect(page.locator('#catalog-products .product-card')).to_have_count(24)
    flows.append('personalized catalog has nonempty pages after the first 120 candidates')

    response=context.request.post(base+'/api/auth/register',data={
        'full_name':'Khách AI mới','email':'ai-'+uuid.uuid4().hex+'@example.test',
        'phone':'0912345678','password':'Test-AI-2026!'})
    assert response.ok,response.text()
    home();customer_view()
    expect(page.locator('#recommendation-explainer')).to_contain_text('AI gợi ý cho bạn')
    assert context.request.get(base+'/api/recommendations').json()['meta']['cold_start']
    flows.append('new account receives cold-start recommendations without borrowing a demo identity')

    def fallback(route):
        response=route.fetch();data=response.json()
        data['meta'].update(model_used=False,engine='Catalog fallback')
        data['quality']={'available':False,'reason':'model_not_used'}
        for item in data['items']:
            item.pop('p_click',None);item.pop('similarity',None)
            item['recommendation_source']='catalog'
        route.fulfill(response=response,json=data)

    page.route('**/api/recommendations?**',fallback)
    page.reload()
    page.locator('#home-products .product-card').first.wait_for()
    expect(page.locator('#recommendation-explainer')).to_contain_text('Gợi ý AI hiện chưa khả dụng')
    assert page.locator('#home-products .ai-product-badge').count()==0
    assert page.locator('.ai-quality-summary').count()==0
    flows.append('simulated inference failure removes AI badges and measured percentage')
    page.unroute('**/api/recommendations?**',fallback)

    for width in (320,390,768):
        page.set_viewport_size({'width':width,'height':900});home();customer_view()
        expect(page.locator('#recommendation-explainer [data-ai-used="true"]')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        page.locator('#recommendation-explainer [data-action="ai-info"]').click()
        assert page.locator('#modal').evaluate('(el)=>el.scrollWidth<=el.clientWidth'),width
        page.evaluate('document.querySelector("#modal [data-action=\\"close-modal\\"]").click()')
        page.screenshot(path=str(output/f'ai-customer-{width}.png'))
        page.screenshot(path=str(output/f'ai-customer-{width}-viewport.png'))
        assert page.locator('#discovery').bounding_box()['y']<page.locator('.category-list').bounding_box()['y']
    flows.append('AI explanation and customer layout fit 320, 390 and 768px screens')
    assert not errors,errors
    print(json.dumps({'status':'passed','flows':flows,'javascript_errors':errors,'screenshots':str(output)},ensure_ascii=False))
    browser.close()
