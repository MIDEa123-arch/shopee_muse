"""Read-only search dismissal regression. Requires an already running server.

TEST_BASE_URL=http://127.0.0.1:8000 .venv/bin/python tests/browser_search.py
Suggestion responses are mocked; no model process, DB copy or writes are needed.
"""
import asyncio
import json
import os
import re
from urllib.parse import parse_qs, urlsplit

from playwright.async_api import async_playwright, expect

BASE_URL = os.getenv('TEST_BASE_URL', 'http://127.0.0.1:8011')


async def main():
    errors = []
    flows = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)

        async def check(viewport, touch=False):
            context = await browser.new_context(viewport=viewport, has_touch=touch)
            page = await context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            started = asyncio.Event()

            async def suggestions(route):
                query = parse_qs(urlsplit(route.request.url).query).get('q', [''])[0]
                if query == 'slow':
                    started.set()
                    await asyncio.sleep(0.5)
                await route.fulfill(json={
                    'history': ['Mục đã xem'], 'trending': ['Tai nghe'],
                    'personalized': [], 'products': [],
                    'autocomplete': [f'Kết quả {query}'] if query else [],
                })

            await page.route('**/api/search/suggestions?*', suggestions)
            await page.goto(BASE_URL, wait_until='networkidle')
            await expect(page.locator('#home-products .product-card').first).to_be_visible()
            search = page.locator('#search')
            dropdown = page.locator('#search-dropdown')
            outside = page.locator('footer .footer-brand strong')
            click = 'tap' if touch else 'click'

            await getattr(search, click)()
            await expect(dropdown).to_be_visible()
            await expect(search).to_have_attribute('aria-expanded', 'true')
            await getattr(outside, click)()
            await expect(dropdown).to_be_hidden()
            await expect(search).to_have_attribute('aria-expanded', 'false')
            flows.append(f'{viewport["width"]}px: outside plain text closes suggestions')

            await getattr(search, click)()
            await expect(dropdown).to_be_visible()
            await search.press('Escape')
            await expect(dropdown).to_be_hidden()
            await search.click()
            await expect(dropdown).to_be_visible()
            await search.press('Tab')  # Search submit button stays inside.
            await expect(dropdown).to_be_visible()
            await page.keyboard.press('Tab')  # Suggestion controls stay inside.
            await expect(dropdown).to_be_visible()
            await page.locator('.brand').focus()
            await expect(dropdown).to_be_hidden()
            flows.append(f'{viewport["width"]}px: reopen, Escape and focus outside work')

            await search.fill('slow')
            await asyncio.wait_for(started.wait(), timeout=5)
            await getattr(outside, click)()
            await page.wait_for_timeout(700)
            await expect(dropdown).to_be_hidden()
            flows.append(f'{viewport["width"]}px: late response cannot reopen dismissed suggestions')

            started.clear()
            await search.click()
            await asyncio.wait_for(started.wait(), timeout=5)
            await search.fill('fast')
            await expect(dropdown).to_contain_text('Kết quả fast')
            await page.wait_for_timeout(700)
            await expect(dropdown).not_to_contain_text('Kết quả slow')
            flows.append(f'{viewport["width"]}px: stale query cannot overwrite newer query')

            await search.fill('debounce')
            await getattr(outside, click)()
            await page.wait_for_timeout(350)
            await expect(dropdown).to_be_hidden()
            flows.append(f'{viewport["width"]}px: outside click cancels pending debounce')

            await search.click()
            await expect(dropdown).to_be_visible()
            # History uses a non-focusable span; closing on blur must not swallow its click.
            await page.locator('[data-search-pick="Mục đã xem"]').click()
            await expect(page).to_have_url(re.compile(r'.*#/catalog\?q='))
            await expect(dropdown).to_be_hidden()
            flows.append(f'{viewport["width"]}px: history item remains selectable')

            await search.fill('tai nghe')
            await expect(dropdown).to_be_visible()
            await search.press('Enter')
            await expect(dropdown).to_be_hidden()
            flows.append(f'{viewport["width"]}px: submitting search closes suggestions')
            await context.close()

        try:
            await check({'width': 1440, 'height': 900})
            await check({'width': 390, 'height': 844}, touch=True)
            assert not errors, errors
            print(json.dumps({'status': 'passed', 'flows': flows, 'javascript_errors': errors}, ensure_ascii=False, indent=2))
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
