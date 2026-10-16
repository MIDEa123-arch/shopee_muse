"""Commerce regression checks. Run only against a server using an isolated database."""
import json
import os
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

base=os.getenv('TEST_BASE_URL','http://127.0.0.1:8011')
output=Path(os.getenv('TEST_SCREENSHOT_DIR','/tmp/shopee-muse-preview'))
output.mkdir(parents=True,exist_ok=True)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    context=browser.new_context(viewport={'width':1440,'height':1050})
    page=context.new_page();errors=[];flows=[]
    page.on('pageerror',lambda error:errors.append(str(error)))

    def request(method,path,data=None):
        response=context.request.fetch(base+'/api'+path,method=method,data=data)
        assert response.ok,(path,response.status,response.text())
        return response.json()

    def clear_cart():
        for item in request('GET','/cart')['items']:
            request('DELETE','/cart/'+str(item['cart_item_id']))

    def goto(route,selector):
        page.goto(base+'/#/'+route,wait_until='domcontentloaded')
        page.locator(selector).first.wait_for()

    def no_overflow(label):
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),label
        if page.locator('#modal').evaluate('(el)=>el.open'):
            assert page.locator('#modal').evaluate('(el)=>el.scrollWidth<=el.clientWidth'),label+' modal'

    request('POST','/auth/demo-login',{'user_id':1});clear_cart()
    request('POST','/cart',{'product_id':1,'quantity':2})
    request('POST','/auth/logout')
    goto('home','#home-products .product-card')
    card=page.locator('#home-products .product-card-main:not([data-id="1"])').first
    product_id=int(card.get_attribute('data-id'))
    card.click();page.locator('#detail-quantity').fill('2')
    page.locator('[data-action="buy-product"]').click()
    page.locator('#modal [data-action="demo-login"][data-id="1"]').click()
    page.wait_for_url('**/checkout?*')
    page.locator('#place-order:not([disabled])').wait_for()
    assert page.locator('#checkout-items .order-item').count()==1
    expect(page.locator('#checkout-items')).to_contain_text('x2')
    assert [(i['id'],i['quantity']) for i in request('GET','/cart')['items']]==[(1,2)]
    flows.append('guest buy-now resumes after login and isolates cart')

    page.locator('[data-action="new-address"]').click()
    page.fill('#address-name','Địa chỉ mua ngay kiểm thử')
    page.fill('#address-phone','0912345678')
    page.select_option('#address-province','1')
    page.fill('#address-detail','123 Đường mới, Phường kiểm thử')
    page.locator('#address-form button[type="submit"]').click()
    page.locator('#place-order:not([disabled])').wait_for()
    selected=page.locator('input[name="checkout_address"]:checked')
    expect(selected.locator('..')).to_contain_text('Địa chỉ mua ngay kiểm thử')
    flows.append('checkout selects newly added address')
    page.locator('#place-order').click()
    page.get_by_text('Đặt hàng thành công!',exact=True).wait_for()
    assert page.url.endswith('#/orders')
    page.reload();page.locator('.order-card').first.wait_for()
    order=request('GET','/orders')[0]
    assert [(i['product_id'],i['quantity']) for i in order['items']]==[(product_id,2)]
    request('POST',f"/orders/{order['id']}/cancel")
    flows.append('success refresh opens orders without duplicate purchase')

    goto('cart','#cart-recommendations .quick-add')
    page.locator('#cart-recommendations .quick-add').first.click()
    page.get_by_text('Đã thêm sản phẩm vào giỏ hàng.',exact=True).wait_for()
    expected_shop=request('GET','/products/1')['shop_name']
    assert all(i['shop_name']==expected_shop for i in request('GET','/cart')['items'])
    flows.append('same-shop cart suggestions support quick add')
    page.locator('#cart-select-all').uncheck()
    expect(page.locator('#app [data-action="checkout"]')).to_be_disabled()
    page.locator('#cart-select-all').check()
    expect(page.locator('#app [data-action="checkout"]')).to_be_enabled()
    flows.append('bulk cart selection')

    page.locator('#app [data-action="checkout"]').click()
    page.locator('#place-order:not([disabled])').wait_for()
    count_before=len(request('GET','/orders'))
    request('POST','/cart',{'product_id':2,'quantity':1})
    with page.expect_response(lambda r:r.url.endswith('/api/orders') and r.request.method=='POST') as rejected:
        page.locator('#place-order').click()
    assert rejected.value.status==409
    page.locator('#place-order:not([disabled])').wait_for()
    expect(page.locator('#checkout-items')).to_contain_text(request('GET','/products/2')['shop_name'])
    assert len(request('GET','/orders'))==count_before
    flows.append('stale cart quote requires review and refreshes visible items')

    address_id=int(page.locator('input[name="checkout_address"]:checked').input_value())
    address=next(a for a in request('GET','/account/addresses') if a['id']==address_id)
    changed_detail='456 Địa chỉ cập nhật từ tab khác '+uuid.uuid4().hex[:8]
    request('PUT','/account/addresses/'+str(address_id),{**address,'detail':changed_detail})
    with page.expect_response(lambda r:r.url.endswith('/api/orders') and r.request.method=='POST') as rejected:
        page.locator('#place-order').click()
    assert rejected.value.status==409,(rejected.value.status,rejected.value.text())
    page.locator('#place-order:not([disabled])').wait_for()
    expect(page.locator('input[name="checkout_address"]:checked').locator('..')).to_contain_text(changed_detail)
    assert len(request('GET','/orders'))==count_before
    flows.append('stale address quote refreshes recipient details')

    page.locator('#place-order').click()
    page.get_by_text('Đặt hàng thành công!',exact=True).wait_for()
    order=request('GET','/orders')[0];request('POST',f"/orders/{order['id']}/cancel")
    clear_cart();request('POST','/cart',{'product_id':1,'quantity':1})

    for width in (320,390,768,1440):
        page.set_viewport_size({'width':width,'height':900})
        goto('home','#home-products .product-card');no_overflow(f'home {width}')
        if page.locator('#toasts .toast').count():
            page.locator('#toasts .toast').last.wait_for(state='hidden')
        assert page.locator('#discovery').bounding_box()['y']<page.locator('.flash').bounding_box()['y']
        page.screenshot(path=str(output/f'audit-home-{width}.png'),full_page=width==1440)
        page.locator('#home-products .product-card-main').first.click()
        page.locator('#similar-products .product-card').first.wait_for();no_overflow(f'product {width}')
        page.locator('#modal [data-action="close-modal"]').click()
        goto('cart','#cart-recommendations .product-card');no_overflow(f'cart {width}')
        if width==390:page.screenshot(path=str(output/'audit-cart-mobile.png'),full_page=True)
        goto('checkout','#place-order:not([disabled])');no_overflow(f'checkout {width}')
        if width==390:page.screenshot(path=str(output/'audit-checkout-mobile.png'),full_page=True)
        flows.append(f'home, product, cart and checkout layout at {width}px')
    assert not errors,errors
    print(json.dumps({'status':'passed','flows':flows,'javascript_errors':errors,'screenshots':str(output)},ensure_ascii=False))
    browser.close()
