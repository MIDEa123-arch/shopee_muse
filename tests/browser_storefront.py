"""Current commerce E2E suite. Run on an isolated DB and one bounded Chromium."""
import json
import os
import re
import uuid
from pathlib import Path
from playwright.sync_api import expect,sync_playwright

base=os.getenv('TEST_BASE_URL','http://127.0.0.1:8011')
out=Path(os.getenv('TEST_SCREENSHOT_DIR','/tmp/lumi-preview'));out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1000})
    page=context.new_page();page.set_default_timeout(30000);errors=[];flows=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    def request(method,path,data=None):
        r=context.request.fetch(base+'/api'+path,method=method,data=data,timeout=30000)
        assert r.ok,(path,r.status,r.text())
        return r.json()
    def goto(route,selector):
        page.goto(base+'/?store-check='+uuid.uuid4().hex+'#/'+route,wait_until='domcontentloaded')
        if route=='home' and selector=='#home-products .product-card':
            page.locator('.store-home').wait_for()
            if page.viewport_size['width']<=520:page.select_option('#store-home-category','')
            else:page.locator('[data-action="store-home-category"][data-value=""]').click()
        page.locator(selector).first.wait_for()
    def clean():
        text=page.locator('body').inner_text()
        assert not re.search(r'[\u3400-\u9fff]',text)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert page.locator('#debug-panel').is_hidden()
        assert all(x not in text for x in ('MUSE','P(click)','GAUC'))
    def loaded_images(selector):
        page.locator(selector).evaluate_all('(xs)=>xs.forEach(x=>x.loading="eager")')
        page.wait_for_function('(s)=>Array.from(document.querySelectorAll(s)).every(x=>x.complete&&x.naturalWidth>0)',arg=selector)
        assert not page.locator(selector).evaluate_all('(xs)=>xs.some(x=>x.src.endsWith("placeholder.svg"))')

    goto('home','#home-products .product-card')
    clean();expect(page.locator('.store-source-note')).to_contain_text('minh họa')
    assert request('GET','/auth/me')['user'] is None
    assert page.locator('#home-products .store-ai-tag').count()==0
    page.locator('#home-products .quick-add').first.click();expect(page.locator('#auth-form')).to_be_visible()
    page.locator('#modal [data-action="close-modal"]').click()
    flows.append('guest sees paired goods and disclosure; quick add opens login')
    for uid in range(1,9):
        with page.expect_response(lambda r:'/api/recommendations?limit=' in r.url and r.ok) as response:
            page.select_option('#profile-switch',str(uid))
        result=response.value.json()
        assert result['meta']['model_used'] and result['meta']['scored_catalog_count']==8192
        expect(page.locator('#home-products .store-ai-tag').first).to_be_visible()
        clean()
    flows.append('all eight profiles retain actual checkpoint inference and AI badges')
    # This scenario measures browsing pagination. A focused type can correctly
    # contain fewer than 24 unique products and hide the load-more control.
    page.locator('[data-action="store-home-category"][data-value=""]').click()
    expect(page.locator('#home-products .product-card')).to_have_count(24)
    page.locator('[data-action="native-compare-profiles"]').first.click()
    page.locator('.native-profile-columns .native-mini').first.wait_for()
    expect(page.locator('.native-profile-columns .native-mini')).to_have_count(12)
    for width in (320,390,768,1440):
        page.set_viewport_size({'width':width,'height':900})
        assert page.locator('#modal').evaluate('(x)=>x.scrollWidth<=x.clientWidth'),width
        page.screenshot(path=str(out/f'compare-{width}.png'))
    page.locator('#modal [data-action="close-modal"]').click()
    before=page.locator('#home-products .product-card-main').evaluate_all('(xs)=>xs.map(x=>x.dataset.id)')
    page.locator('[data-action="home-more"]').click()
    expect(page.locator('#home-products .product-card')).to_have_count(36)
    assert page.locator('#home-products .product-card-main').evaluate_all('(xs)=>xs.slice(0,24).map(x=>x.dataset.id)')==before
    history=request('GET','/recommendations/history?limit=1000')
    page.locator('[data-action="store-home-category"][data-value="electronics"]').click()
    expect(page.locator('#discovery .recommend-title p')).to_contain_text('Điện tử')
    assert all(x=='electronics' for x in page.locator('#home-products .store-card').evaluate_all('(xs)=>xs.map(x=>x.dataset.displayCategory)'))
    assert request('GET','/recommendations/history?limit=1000')==history
    flows.append('profile comparison, stable load more and display filtering without fake history')
    page.locator('#recommendation-explainer [data-action="ai-info"]').click()
    expect(page.locator('#modal')).to_contain_text('62,02%')
    expect(page.locator('#modal')).to_contain_text('chưa chứng minh')
    page.locator('#modal [data-action="close-modal"]').click()
    page.locator('.debug-toggle').click()
    page.locator('#debug-panel').get_by_text('CHECKPOINT LOADED').wait_for()
    expect(page.locator('#debug-panel')).to_contain_text('AUC / GAUC')
    page.locator('.debug-toggle').click();clean()
    flows.append('measured original-data quality explained; technical metrics confined to Lab')
    page.locator('[data-action="store-home-category"][data-value=""]').click()
    expect(page.locator('#discovery .recommend-title p')).to_contain_text('ưu tiên')
    pid=int(page.locator('#home-products .product-card-main').first.get_attribute('data-id'))
    before=page.locator('#home-products .product-card-main').evaluate_all('(xs)=>xs.slice(0,12).map(x=>Number(x.dataset.id))')
    with page.expect_response(lambda r:'/api/recommendations?limit=' in r.url and r.ok) as response:
        page.locator('#home-products .product-card-main').first.click()
    after=[p['id'] for p in response.value.json()['items'][:12]]
    page.locator('#similar-products .product-card').first.wait_for()
    expect(page.locator('.native-change-card')).to_contain_text('Gợi ý tiếp nối:')
    expect(page.locator('#modal')).to_contain_text('Giá mô phỏng')
    loaded_images('#modal .detail-image img')
    page.screenshot(path=str(out/'detail-desktop.png'))
    page.locator('.store-detail-secondary [data-action="favorite"]').click()
    expect(page.locator('.store-detail-secondary [data-action="favorite"]')).to_contain_text('Đã lưu')
    page.locator('#detail-quantity').fill('2')
    page.locator('#modal [data-action="add-product"]').click()
    page.get_by_text('Đã thêm sản phẩm vào giỏ hàng.',exact=True).wait_for()
    page.locator('#modal [data-action="close-modal"]').click()
    expect(page.locator('.native-change-card')).to_contain_text('gợi ý')
    assert pid not in [p['id'] for p in request('GET','/recommendations')['items']]
    flows.append('detail, SCL neighbours, favorite, quantity, cart and real interaction update')

    goto('wishlist','#app .product-card')
    assert page.locator(f'.product-card-main[data-id="{pid}"]').count()==1
    page.fill('#search','tai nghe');page.locator('#search-form button').click()
    page.locator('#catalog-products .product-card').first.wait_for()
    assert all('Tai nghe' in s for s in page.locator('#catalog-products .product-name').all_text_contents())
    goto('catalog?display_category=electronics&sort=price_asc','#catalog-products .product-card')
    expect(page.locator('.page-title')).to_contain_text('Điện tử')
    assert all(x=='electronics' for x in page.locator('#catalog-products .store-card').evaluate_all('(xs)=>xs.map(x=>x.dataset.displayCategory)'))
    page.locator('#filter-form input[name="min_price"]').fill('100000')
    page.locator('#filter-form input[name="max_price"]').fill('2000000')
    page.locator('#filter-form button[type="submit"]').click()
    page.locator('#catalog-products .product-card').first.wait_for()
    page.locator('[data-sort="relevance"]').click()
    expect(page.locator('#result-count')).to_contain_text('AI xếp hạng')
    goto('catalog?sort=relevance','#catalog-products .product-card')
    page.locator('[data-page="2"]').first.click();expect(page.locator('#pagination .active')).to_have_text('2')
    flows.append('wishlist, Vietnamese title search, category, prices, AI sorting and pagination')

    for item in request('GET','/cart')['items']:request('DELETE','/cart/'+str(item['cart_item_id']))
    request('POST','/cart',{'product_id':1,'quantity':1})
    goto('cart','.cart-line')
    page.locator('#cart-recommendations .quick-add').first.wait_for()
    page.locator('#cart-recommendations .quick-add').first.click()
    page.get_by_text('Đã thêm sản phẩm vào giỏ hàng.',exact=True).wait_for()
    assert len(request('GET','/cart')['items'])==2
    page.locator('#cart-select-all').uncheck();expect(page.locator('#app [data-action="checkout"]')).to_be_disabled()
    page.locator('#cart-select-all').check();page.locator('#app [data-action="checkout"]').click()
    page.locator('#place-order:not([disabled])').wait_for()
    page.screenshot(path=str(out/'checkout-desktop.png'))
    page.locator('#place-order').click();page.get_by_text('Đặt hàng thành công!',exact=True).wait_for()
    page.locator('#app [data-action="orders"]').click();page.locator('.order-card').first.wait_for()
    page.locator('[data-action="cancel-order"]').first.click();page.locator('#modal [data-action="confirm-cancel-order"]').click()
    page.get_by_text('Đã hủy đơn và hoàn lại quyền lợi.',exact=True).wait_for()
    flows.append('cart AI additions, selection, checkout, order and cancellation/refund')

    request('POST','/cart',{'product_id':1,'quantity':1})
    for width in (320,390,768,1440):
        page.set_viewport_size({'width':width,'height':900})
        goto('home','#home-products .product-card');clean();loaded_images('#home-products .product-image img')
        page.screenshot(path=str(out/f'home-{width}.png'))
        page.locator('#discovery').evaluate('(x)=>x.scrollIntoView({block:"start"})')
        page.screenshot(path=str(out/f'feed-{width}.png'))
        page.locator('#home-products .product-card-main').first.click();page.locator('#similar-products .product-card').first.wait_for()
        assert page.locator('#modal').evaluate('(x)=>x.scrollWidth<=x.clientWidth'),width
        page.screenshot(path=str(out/f'detail-{width}.png'))
        page.locator('#modal [data-action="close-modal"]').click()
        goto('catalog?sort=relevance','#catalog-products .product-card');clean()
        page.screenshot(path=str(out/f'catalog-{width}.png'))
        goto('cart','.cart-line');clean();page.screenshot(path=str(out/f'cart-{width}.png'))
        goto('checkout','#place-order:not([disabled])');clean();page.screenshot(path=str(out/f'checkout-{width}.png'))
    flows.append('home, feed, detail, catalog, cart and checkout fit 320/390/768/1440 without Chinese text or broken photos')

    def unavailable(route):route.fulfill(status=503,content_type='application/json',body='{"detail":"Gợi ý đang bận"}')
    page.route('**/api/recommendations?touchpoint=cart*',unavailable)
    goto('cart','.cart-line');expect(page.locator('#cart-recommendations')).to_contain_text('Gợi ý tạm thời chưa tải được')
    expect(page.locator('#app [data-action="checkout"]')).to_be_enabled()
    page.unroute('**/api/recommendations?touchpoint=cart*',unavailable)
    page.route('**/api/recommendations?touchpoint=similar*',unavailable)
    goto('home','#home-products .product-card');page.locator('#home-products .product-card-main').first.click()
    expect(page.locator('#similar-products')).to_contain_text('Chưa tải được')
    expect(page.locator('#modal [data-action="add-product"]')).to_be_enabled()
    page.locator('#modal [data-action="close-modal"]').click();page.unroute('**/api/recommendations?touchpoint=similar*',unavailable)
    page.route('**/api/recommendations?limit=*',unavailable)
    goto('home','.store-refresh-error');expect(page.locator('.store-hero')).to_be_visible()
    expect(page.locator('.store-refresh-error')).to_contain_text('mua sắm vẫn hoạt động')
    page.unroute('**/api/recommendations?limit=*',unavailable)
    page.locator('.store-refresh-error [data-action="native-refresh"]').click();page.locator('#home-products .product-card').first.wait_for()
    flows.append('503 recovery preserves home, buying and cart; retry restores recommendations')

    goto('addresses','#app [data-action="new-address"]');page.locator('#app [data-action="new-address"]').first.click()
    page.fill('#address-name','Người nhận Lumi');page.fill('#address-phone','0912345678');page.select_option('#address-province','34');page.fill('#address-detail','123 Đường kiểm thử, Phường Mẫu')
    page.locator('#address-form button[type="submit"]').click();page.get_by_text('Đã lưu địa chỉ nhận hàng.',exact=True).wait_for()
    goto('vouchers','.voucher-card');goto('account','#profile-form')
    assert page.locator('#profile-avatar option').count()==9
    flows.append('addresses, vouchers and account remain functional')
    request('POST','/auth/register',{'full_name':'Khách mới Lumi','phone':'0912345678','email':'lumi-'+uuid.uuid4().hex+'@example.test','password':'Lumi-test-2026!'})
    goto('home','#home-products .product-card');clean()
    expect(page.locator('#recommendation-explainer')).to_contain_text('bắt đầu tạo lịch sử riêng')
    assert request('GET','/recommendations')['meta']['cold_start']
    flows.append('registered customer uses actual cold-start inference')
    request('POST','/account/addresses',{'recipient_name':'Khách mới Lumi','phone':'0912345678','province_id':1,'detail':'123 Đường kiểm thử, Phường Mẫu','label':'Nhà riêng','is_default':True})
    goto('catalog?q=TB-00001','#catalog-products .product-card')
    page.locator('#catalog-products .product-card-main').first.click();page.locator('#similar-products .product-card').first.wait_for()
    page.locator('#detail-quantity').fill('3');page.locator('#modal [data-action="buy-product"]').click()
    page.locator('#place-order:not([disabled])').wait_for()
    expect(page.locator('#checkout-items')).to_contain_text('x3')
    page.locator('#place-order').click();page.get_by_text('Đặt hàng thành công!',exact=True).wait_for()
    page.locator('#app [data-action="orders"]').click();page.locator('.order-card').first.wait_for()
    page.locator('.order-card').first.locator('[data-action="advance-order"]').click()
    expect(page.locator('.order-card').first).to_contain_text('ĐANG GIAO')
    page.locator('.order-card').first.locator('[data-action="advance-order"]').click()
    expect(page.locator('.order-card').first).to_contain_text('ĐÃ GIAO')
    page.locator('.order-card').first.locator('[data-action="review"]').click()
    page.fill('#review-content','Sản phẩm trong bản trải nghiệm hiển thị rõ ràng, dễ sử dụng.')
    page.locator('#review-form button[type="submit"]').click();page.get_by_text('Cảm ơn bạn đã chia sẻ đánh giá.',exact=True).wait_for()
    page.locator('.order-card').first.locator('[data-action="product"]').first.click()
    page.locator('.store-product-reviews summary').click()
    expect(page.locator('.store-product-reviews')).to_contain_text('hiển thị rõ ràng')
    page.locator('#modal [data-action="close-modal"]').click()
    flows.append('buy now keeps quantity; simulated delivery and verified-order review appear in detail')
    assert not errors,errors
    result={'status':'passed','flows':flows,'javascript_errors':errors,'screenshots':str(out)}
    (out/'browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False));browser.close()
