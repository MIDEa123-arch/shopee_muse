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
                    for pid in (17438, 20739, 17150):
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
