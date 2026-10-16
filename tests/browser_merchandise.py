"""Use an existing server; never create orders/cart/behavior or copy its DB.

Guest details are read-only. Demo logins create temporary sessions (logged out
after each case); home requests may create ordinary recommendation logs.
TEST_BASE_URL=http://127.0.0.1:8000 .venv/bin/python tests/browser_merchandise.py
"""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

from app.database import connection
from app.recommender.merchandise import identity, kind, purchase_context, is_complement


BASE = os.getenv('TEST_BASE_URL', 'http://127.0.0.1:8000')
OUTPUT = Path(os.getenv('TEST_SCREENSHOT_DIR', '/tmp/lumi-merchandise-preview'))


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    errors, flows = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for uid in (None, 1, 2):
                context = browser.new_context(viewport={'width': 1440, 'height': 900})
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                if uid:
                    assert context.request.post(BASE+'/api/auth/demo-login', data={'user_id': uid}).ok
                with page.expect_response(lambda r: urlsplit(r.url).path == '/api/recommendations' and r.ok) as response:
                    page.goto(BASE, wait_until='domcontentloaded')
                result = response.value.json()
                cards = page.locator('#home-products .product-card')
                expect(cards).to_have_count(len(result['items']))
                assert result['items']
                ids = page.locator('#home-products .product-card-main').evaluate_all(
                    'cards => cards.map(c=>Number(c.dataset.id))')
                assert ids == [i['id'] for i in result['items']]
                assert len(result['items']) == len({identity(i) for i in result['items']})
                expect(page.locator('#debug-panel')).to_be_hidden()
                text = page.locator('#app').inner_text()
                for term in ('P(click)', '128D', 'MUSE', 'vector', 'Mã ID:'):
                    assert term not in text, term
                if uid:
                    with connection() as db:
                        owned = purchase_context(db, uid)
                    assert all(identity(i) not in owned['keys'] and kind(i) not in owned['recent_kinds']
                               for i in result['items'])
                    assert result['meta']['model_used'], result['meta']
                    page.locator('.debug-toggle').click()
                    expect(page.locator('#debug-toggle')).to_be_checked()
                    expect(page.locator('#debug-panel')).to_contain_text('CHECKPOINT LOADED')
                    expect(page.locator('#home-products .lab-item-badge').first).to_be_visible()
                    page.locator('.debug-toggle').click()
                    expect(page.locator('#debug-panel')).to_be_hidden()
                    flows.append(f'profile {uid}: rendered IDs match API; no owned models/recent durable types; Lab toggles')
                else:
                    page.goto(BASE+'/#/catalog?q=chuot',wait_until='domcontentloaded')
                    expect(page.locator('#catalog-products .product-card')).to_have_count(7)
                    names=page.locator('#catalog-products .product-name').all_inner_texts()
                    assert len(names)==len(set(names))
                    assert '−0%' not in page.locator('#catalog-products').inner_text()
                    expect(page.locator('#catalog-products')).to_contain_text('Chưa có đánh giá')
                    page.goto(BASE,wait_until='domcontentloaded')
                    expect(page.locator('#home-products .product-card').first).to_be_visible()
                    flows.append('guest: mouse catalog has seven distinct models, not repeated color/ID rows')
                    for pid in (17438, 20739, 17150, 157):
                        focus = context.request.get(f'{BASE}/api/products/{pid}').json()
                        # Runs the same function as the product-card click, as a guest.
                        page.evaluate('(id)=>openProduct(id)', pid)
                        expect(page.locator('#modal .detail-description').first).to_contain_text('Ảnh minh họa loại sản phẩm')
                        for selector, touchpoint in (('#similar-products','similar'), ('#complementary-products','complementary')):
                            items = context.request.get(f'{BASE}/api/recommendations?touchpoint={touchpoint}&product_id={pid}&limit=6').json()['items']
                            expect(page.locator(selector+' .product-card')).to_have_count(len(items))
                            assert items
                            assert all(kind(i)==kind(focus) and identity(i)!=identity(focus)
                                       if touchpoint=='similar' else is_complement(i,focus) for i in items)
                        if pid == 17150:
                            page.screenshot(path=str(OUTPUT/'guest-sunscreen-detail.png'))
                        if pid == 157:
                            assert len(context.request.get(f'{BASE}/api/recommendations?touchpoint=similar&product_id=157&limit=6').json()['items'])>=6
                            page.locator('#similar-products').scroll_into_view_if_needed()
                            page.screenshot(path=str(OUTPUT/'guest-mouse-alternatives.png'))
                        page.locator('#modal [data-action="close-modal"]').click()
                    flows.append('guest: phone/laptop/sunscreen detail placements match merchandise types and API')
                    failure_url='**/api/recommendations?touchpoint=complementary&product_id=17438&limit=6'
                    page.route(failure_url, lambda route: route.fulfill(status=503, json={'detail':'Test unavailable'}))
                    page.evaluate('(id)=>openProduct(id)',17438)
                    expect(page.locator('#complementary-products [role="alert"]')).to_contain_text('Chưa tải được sản phẩm')
                    expect(page.locator('#complementary-products .spinner')).to_have_count(0)
                    expect(page.locator('#similar-products .product-card').first).to_be_visible()
                    page.unroute(failure_url)
                    page.locator('#complementary-products [data-action="product"]').click()
                    expect(page.locator('#complementary-products .product-card').first).to_be_visible()
                    page.locator('#modal [data-action="close-modal"]').click()
                    flows.append('guest: failed add-ons show retry; similar placement stays usable; retry recovers')
                page.locator('#discovery').scroll_into_view_if_needed()
                page.screenshot(path=str(OUTPUT/f'home-{uid or "guest"}.png'))
                for width in (390, 1440):
                    page.set_viewport_size({'width': width, 'height': 844})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                page.set_viewport_size({'width': 390, 'height': 844})
                page.screenshot(path=str(OUTPUT/f'mobile-{uid or "guest"}.png'))
                flows.append(f'{uid or "guest"}: desktop/mobile have no horizontal overflow')
                if uid:
                    zero=context.request.get(BASE+'/api/search/suggestions?q=').json()
                    offers=context.request.get(BASE+'/api/offers').json()
                    for product in zero['products']+offers['items']:
                        assert identity(product) not in owned['keys'] and kind(product) not in owned['recent_kinds']
                    typed=context.request.get(BASE+'/api/search/suggestions?q=chuot').json()
                    assert len(typed['products'])>=4
                    assert all(kind(product)=='mouse' for product in typed['products'])
                    flows.append(f'{uid}: zero-query suggestions/offers use purchase rules; explicit mouse search retains distinct models')
                if uid==1:
                    # Existing orders only: no checkout/cart/behavior mutations.
                    orders=context.request.get(BASE+'/api/orders').json()
                    laptop=next(o for o in orders if o['order_status']!='Đã hủy' and any('Laptop' in (i['product_name'] or '') for i in o['items']))
                    shoes=next(o for o in orders if o['order_status']!='Đã hủy' and all('Giày' in (i['product_name'] or '') for i in o['items']))
                    page.set_viewport_size({'width':1440,'height':900})
                    with page.expect_response(lambda r: '/api/recommendations?' in r.url and 'category_id=1' in r.url and r.ok) as tab_response:
                        page.locator('[data-action="home-cat-tab"][data-category-id="1"]').click()
                    tab=tab_response.value.json()
                    assert all(kind(product)!='laptop' for product in tab['items'])
                    purchased_pid=laptop['items'][0]['product_id']
                    similar=context.request.get(f'{BASE}/api/recommendations?touchpoint=similar&product_id={purchased_pid}').json()
                    assert similar['items']==[]
                    await_behavior='**/api/recommendations/behavior/*'
                    page.route(await_behavior,lambda route:route.fulfill(json={'ok':True}))
                    page.evaluate('(id)=>openProduct(id)',purchased_pid)
                    expect(page.locator('#similar-products').locator('..')).to_be_hidden()
                    expect(page.locator('#complementary-products .product-card').first).to_be_visible()
                    page.locator('#modal [data-action="close-modal"]').click()
                    page.unroute(await_behavior)
                    page.goto(BASE+'/#/orders',wait_until='domcontentloaded')
                    expect(page.locator('#order-recommendations .product-card').first).to_be_visible()
                    with page.expect_response(lambda r:f'order_id={shoes["id"]}' in r.url and r.ok) as order_response:
                        page.locator(f'[data-action="order-suggestions"][data-id="{shoes["id"]}"]').click()
                    ordered=order_response.value.json()
                    expect(page.locator('#order-recommendations')).to_have_attribute('data-order-id',str(shoes['id']))
                    expect(page.locator('#order-recs-context')).to_contain_text(shoes['order_code'])
                    assert ordered['items']
                    assert len(ordered['items'])>=6
                    assert all(kind(product) in {'socks','bottle','shoe-insole','shoe-cleaner','shoe-bag','shoelaces','shoe-deodorizer'} for product in ordered['items'])
                    page.locator('#order-recs-section').scroll_into_view_if_needed()
                    page.screenshot(path=str(OUTPUT/'sports-order-addons.png'))
                    page.set_viewport_size({'width':390,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.get_by_role('button',name='Đã hủy',exact=True).click()
                    expect(page.locator('#order-recs-section')).to_have_count(0)
                    # Exercise success renderer against an existing owned order.
                    page.evaluate('''async order=>{state.route='success';state.routeVersion++;document.querySelector('#app').innerHTML='<div id="success-recs"></div>';await loadSuccessRecommendations(order,state.routeVersion,state.user.id);}''',laptop)
                    expect(page.locator('#success-recs .product-card').first).to_be_visible()
                    actual=context.request.get(f'{BASE}/api/recommendations?touchpoint=post_purchase&order_id={laptop["id"]}&limit=12').json()
                    assert all(kind(product) in {'keyboard','mouse','monitor','laptop-bag','headphones','earbuds','charger'} for product in actual['items'])
                    flows.append('profile 1: laptop tab obeys cooldown; selected sports order stays relevant; cancelled tab has no borrowed context; success uses exact order')
                if uid:
                    assert context.request.post(BASE+'/api/auth/logout').ok
                context.close()
            assert not errors, errors
            print(json.dumps({'status':'passed', 'flows':flows, 'javascript_errors':errors,
                              'screenshots':str(OUTPUT)}, ensure_ascii=False, indent=2))
        finally:
            for context in browser.contexts:
                context.request.post(BASE+'/api/auth/logout')
            browser.close()


if __name__ == '__main__':
    main()
