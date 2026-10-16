"""Native Taobao end-to-end checks. Run only against an isolated test database."""
import json
import os
import re
import uuid
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

base=os.getenv('TEST_BASE_URL','http://127.0.0.1:8011')
output=Path(os.getenv('TEST_SCREENSHOT_DIR','/tmp/taobao-preview'));output.mkdir(parents=True,exist_ok=True)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1050})
    page=context.new_page();page.set_default_timeout(30000)
    errors=[];flows=[]
    page.on('pageerror',lambda error:errors.append(str(error)))

    def request(method,path,data=None):
        r=context.request.fetch(base+'/api'+path,method=method,data=data,timeout=30000)
        assert r.ok,(path,r.status,r.text())
        return r.json()

    def goto(route,selector):
        page.goto(base+'/?native-check='+uuid.uuid4().hex+'#/'+route,wait_until='domcontentloaded')
        page.locator(selector).first.wait_for()

    def clean_view():
        assert not re.search(r'[\u3400-\u9fff]',page.locator('body').inner_text())
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert page.locator('#debug-panel').is_hidden()
        text=page.locator('body').inner_text()
        assert 'MUSE' not in text and 'P(click)' not in text and 'GAUC' not in text

    goto('home','#home-products .product-card')
    assert request('GET','/auth/me')['user'] is None
    expect(page.locator('#recommendation-explainer')).to_contain_text('Đăng nhập để AI')
    assert page.locator('#home-products .ai-product-badge').count()==0
    clean_view();flows.append('guest remains logged out and sees source disclosure')
    page.screenshot(path=str(output/'native-guest-desktop.png'))

    for uid in range(1,9):
        with page.expect_response(lambda r:'/api/recommendations?limit=' in r.url and r.ok) as rec:
            page.select_option('#profile-switch',str(uid))
        result=rec.value.json()
        assert result['meta']['model_used'] and result['meta']['scored_catalog_count']==8192
        assert result['meta']['history_length']==1000
        expect(page.locator('#recommendation-explainer')).to_contain_text('AI gợi ý cho bạn')
        expect(page.locator('#home-products .ai-product-badge').first).to_be_visible()
        clean_view()
    flows.append('eight original profiles use checkpoint scores across all complete candidates')

    before=page.locator('#home-products .product-card-main').evaluate_all('(xs)=>xs.map(x=>x.dataset.id)')
    with page.expect_response(lambda r:'/api/recommendations?limit=36' in r.url and r.ok):
        page.locator('[data-action="home-more"]').click()
    expect(page.locator('#home-products .product-card')).to_have_count(36)
    after=page.locator('#home-products .product-card-main').evaluate_all('(xs)=>xs.map(x=>x.dataset.id)')
    assert after[:24]==before
    flows.append('load more has a stable prefix')

    history_before=request('GET','/recommendations/history?limit=1000')
    group=request('GET','/catalog')['categories'][0]['id']
    with page.expect_response(lambda r:'category_id='+str(group) in r.url and '/recommendations?' in r.url and r.ok):
        page.select_option('#native-home-group',str(group))
    expect(page.locator('#home-products .product-card').first).to_have_attribute('data-category',str(group))
    assert all(int(x)==group for x in page.locator('#home-products .product-card').evaluate_all('(xs)=>xs.map(x=>x.dataset.category)'))
    assert request('GET','/recommendations/history?limit=1000')==history_before
    flows.append('original-group filter updates visible results without synthetic clicks')

    page.locator('#recommendation-explainer [data-action="ai-info"]').click()
    expect(page.locator('#modal')).to_contain_text('không có nghĩa')
    expect(page.locator('#modal')).to_contain_text('không cung cấp tên hoặc ảnh gốc')
    expect(page.locator('#modal')).to_contain_text('62,02%')
    page.locator('#modal [data-action="close-modal"]').click()
    page.locator('.debug-toggle').click()
    page.locator('#debug-panel').get_by_text('CHECKPOINT LOADED').wait_for()
    expect(page.locator('#debug-panel .lab-evaluation')).to_contain_text('AUC / GAUC')
    expect(page.locator('#debug-panel .lab-results')).to_contain_text('Thứ tự giảm dần theo điểm checkpoint')
    page.screenshot(path=str(output/'native-lab.png'))
    page.locator('.debug-toggle').click();clean_view()
    flows.append('measured quality is explained accurately; technical details stay inside Lab')

    # A true view, save and purchase interaction exercise history invalidation.
    pid=int(page.locator('#home-products .product-card-main').first.get_attribute('data-id'))
    page.locator('#home-products .product-card-main').first.click()
    page.locator('#similar-products .product-card').first.wait_for()
    expect(page.locator('#modal')).to_contain_text('không phải ảnh hàng hóa')
    expect(page.locator('#similar-products')).to_contain_text('Gần nhau theo đặc trưng AI')
    if 'Đã lưu' in page.locator('.native-detail-actions [data-action="favorite"]').inner_text():
        page.locator('.native-detail-actions [data-action="favorite"]').click()
        expect(page.locator('.native-detail-actions [data-action="favorite"]')).to_contain_text('Lưu mẫu')
    page.locator('.native-detail-actions [data-action="favorite"]').click()
    expect(page.locator('.native-detail-actions [data-action="favorite"]')).to_contain_text('Đã lưu')
    assert request('GET','/recommendations/history?limit=2')[0]['action_type']=='favorite'
    page.locator('.native-try-buy summary').click()
    page.locator('#detail-quantity').fill('2')
    page.locator('#modal [data-action="add-product"]').click()
    page.get_by_text('Đã thêm sản phẩm vào giỏ hàng.',exact=True).wait_for()
    page.locator('#modal [data-action="close-modal"]').click()
    flows.append('detail, learned SCL neighbours, save and add-to-cart work with original IDs')

    goto('wishlist','#app .product-card')
    assert page.locator(f'#app .product-card-main[data-id="{pid}"]').count()==1
    page.fill('#search','Nhóm 001');page.locator('#search-form button').click()
    page.locator('#catalog-products .product-card').first.wait_for()
    expect(page.locator('.page-title')).to_contain_text('Nhóm 001')
    assert all(int(x)==10001 for x in page.locator('#catalog-products .product-card').evaluate_all('(xs)=>xs.map(x=>x.dataset.category)'))
    goto('catalog?sort=relevance&page=6','#catalog-products .product-card')
    expect(page.locator('#catalog-products .product-card')).to_have_count(24)
    page.locator('[data-sort="popular"]').click()
    expect(page.locator('#result-count')).not_to_contain_text('Đã xếp hạng bằng AI')
    flows.append('saved list, group search and paginated AI catalog work')

    # Checkout uses the current simulated catalog, preserving quoting and refund invariants.
    for item in request('GET','/cart')['items']:
        request('DELETE','/cart/'+str(item['cart_item_id']))
    request('POST','/cart',{'product_id':1,'quantity':1})
    goto('cart','.cart-line')
    page.locator('#cart-recommendations .quick-add').first.wait_for()
    page.locator('#cart-recommendations .quick-add').first.click()
    page.get_by_text('Đã thêm sản phẩm vào giỏ hàng.',exact=True).wait_for()
    assert len(request('GET','/cart')['items'])==2
    page.locator('#cart-select-all').uncheck()
    expect(page.locator('#app [data-action="checkout"]')).to_be_disabled()
    page.locator('#cart-select-all').check()
    page.locator('#app [data-action="checkout"]').click()
    page.locator('#place-order:not([disabled])').wait_for()
    expect(page.locator('#app')).to_contain_text('không phát sinh thanh toán thật')
    page.screenshot(path=str(output/'native-checkout.png'))
    page.locator('#place-order').click()
    page.get_by_text('Đặt hàng thành công!',exact=True).wait_for()
    page.locator('#app [data-action="orders"]').click()
    page.locator('.order-card').first.wait_for()
    page.locator('[data-action="cancel-order"]').first.click()
    page.locator('#modal [data-action="confirm-cancel-order"]').click()
    page.get_by_text('Đã hủy đơn và hoàn lại quyền lợi.',exact=True).wait_for()
    flows.append('cart recommendations, selection, checkout, order and cancellation/refund')

    request('POST','/cart',{'product_id':1,'quantity':1})
    for width in (320,390,768,1440):
        page.set_viewport_size({'width':width,'height':900})
        goto('home','#home-products .product-card');clean_view()
        page.screenshot(path=str(output/f'native-home-{width}.png'))
        page.locator('#discovery').evaluate('(el)=>el.scrollIntoView({block:"start"})')
        page.screenshot(path=str(output/f'native-feed-{width}.png'))
        page.locator('#home-products .product-card-main').first.click()
        page.locator('#similar-products .product-card').first.wait_for()
        assert page.locator('#modal').evaluate('(el)=>el.scrollWidth<=el.clientWidth'),width
        page.screenshot(path=str(output/f'native-detail-{width}.png'))
        page.locator('#modal [data-action="close-modal"]').click()
        goto('catalog?sort=relevance','#catalog-products .product-card');clean_view()
        page.screenshot(path=str(output/f'native-catalog-{width}.png'))
        goto('cart','.cart-line');clean_view()
        page.screenshot(path=str(output/f'native-cart-{width}.png'))
        goto('checkout','#place-order:not([disabled])');clean_view()
        page.screenshot(path=str(output/f'native-checkout-{width}.png'))
    flows.append('home, feed, details, catalog, cart and checkout fit 320, 390, 768 and 1440px without Chinese text')

    def unavailable(route):
        route.fulfill(status=503,content_type='application/json',body='{"detail":"Gợi ý đang bận"}')
    page.route('**/api/recommendations?touchpoint=cart*',unavailable)
    goto('cart','.cart-line')
    expect(page.locator('#cart-recommendations')).to_contain_text('Gợi ý tạm thời chưa tải được')
    expect(page.locator('#app [data-action="checkout"]')).to_be_enabled()
    page.unroute('**/api/recommendations?touchpoint=cart*',unavailable)
    page.route('**/api/recommendations?touchpoint=complementary*',unavailable)
    goto('orders','.order-card')
    expect(page.locator('#order-recommendations')).to_contain_text('Gợi ý tạm thời chưa tải được')
    assert page.locator('.order-card').count()>0
    goto('checkout','#place-order:not([disabled])')
    page.locator('#place-order').click()
    page.get_by_text('Đặt hàng thành công!',exact=True).wait_for()
    page.locator('#app [data-action="orders"]').click()
    page.locator('.order-card').first.wait_for()
    page.unroute('**/api/recommendations?touchpoint=complementary*',unavailable)
    flows.append('recommendation endpoint failure preserves cart, orders and immediate navigation after purchase')

    goto('account','#profile-form')
    assert page.locator('#profile-avatar option').count()==9
    goto('addresses','#app [data-action="new-address"]')
    page.locator('#app [data-action="new-address"]').first.click()
    page.fill('#address-name','Người nhận trải nghiệm');page.fill('#address-phone','0912345678')
    page.select_option('#address-province','34');page.fill('#address-detail','123 Đường trải nghiệm, Phường kiểm thử')
    page.locator('#address-form button[type="submit"]').click()
    page.get_by_text('Đã lưu địa chỉ nhận hàng.',exact=True).wait_for()
    flows.append('account and address form remain functional')

    def fallback(route):
        response=route.fetch();data=response.json();data['meta']['model_used']=False;data['quality']={'available':False}
        for item in data['items']:
            item.pop('p_click',None);item['recommendation_source']='catalog'
        route.fulfill(response=response,json=data)
    page.route('**/api/recommendations?**',fallback)
    goto('home','#home-products .product-card')
    expect(page.locator('#recommendation-explainer')).to_contain_text('Gợi ý AI hiện chưa khả dụng')
    assert page.locator('#home-products .ai-product-badge').count()==0
    assert page.locator('.ai-quality-summary').count()==0
    page.unroute('**/api/recommendations?**',fallback)
    flows.append('AI failure is disclosed without scores or AI badges')

    request('POST','/auth/register',{'full_name':'Khách mới Taobao','phone':'0912345678',
        'email':'native-'+uuid.uuid4().hex+'@example.test','password':'Native-test-2026!'})
    goto('home','#home-products .product-card');clean_view()
    expect(page.locator('#recommendation-explainer')).to_contain_text('Gợi ý khởi đầu')
    assert request('GET','/recommendations')['meta']['cold_start']
    assert request('GET','/auth/me')['user']['raw_user_id'] is None
    flows.append('new account receives a real cold-start context without borrowed Taobao identity')
    assert not errors,errors
    result={'status':'passed','flows':flows,'javascript_errors':errors,'screenshots':str(output)}
    (output/'browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False));browser.close()
