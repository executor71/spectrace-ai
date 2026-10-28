"""Read-only smoke checks against the running workspace. Never starts jobs.

Requires Playwright + Chrome. Screenshots are saved in the OS temp directory.
Usage: python tests/enterpriseUi.browser.py [http://127.0.0.1:5173]
"""
import json
import sys
import tempfile
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

base = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5173'
output = Path(tempfile.gettempdir()) / 'spectrace-enterprise-ui'
output.mkdir(exist_ok=True)
with urllib.request.urlopen(base + '/api/dashboard/summary', timeout=30) as response:
    summary = json.load(response)
requirements = sorted(summary['requirements'], key=lambda row: (row['hasAnalysis'], row['counts']['total']), reverse=True)
assert requirements, 'A saved synthetic requirement is needed for detail checks'
requirement = requirements[0]
results = []

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel='chrome', headless=True)
    for width in [1440, 1024, 390]:
        context = browser.new_context(viewport={'width': width, 'height': 1000}, reduced_motion='reduce')
        page = context.new_page()
        errors, writes = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def prevent_writes(route):
            if route.request.method not in ['GET', 'HEAD', 'OPTIONS']:
                writes.append(route.request.url)
                route.abort()
            else:
                route.continue_()

        context.route('**/api/**', prevent_writes)
        page.goto(base + '/#requirements', wait_until='networkidle')
        page.locator('#requirement-id').fill(requirement['id'])
        page.get_by_role('button', name='조회', exact=True).click()
        expect(page.locator('.requirement-result h3')).to_have_text(requirement['title'])
        for screen in ['dashboard', 'requirements', 'analysis', 'testcases', 'review', 'execution', 'evaluation', 'graph']:
            page.evaluate('(screen) => { location.hash = screen }', screen)
            page.wait_for_function('(screen) => location.hash === "#" + screen', arg=screen)
            page.wait_for_timeout(600)
            expect(page.locator('main h1')).to_be_visible()
            expect(page.get_by_role('navigation', name='검증 업무 단계')).to_be_visible()
            assert page.locator('.process-navigation button').count() == 4
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (width, screen, page.evaluate('document.documentElement.scrollWidth'))
            assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--color-brand').trim()") == '#0013d7'
            page.screenshot(path=str(output / f'{screen}-{width}.png'), full_page=True)
            if screen == 'dashboard':
                page.screenshot(path=str(output / f'dashboard-viewport-{width}.png'))
            results.append({'width': width, 'screen': screen, 'result': 'PASS'})

        if width == 390:
            page.get_by_role('button', name='메뉴 열기', exact=True).click()
            expect(page.locator('#app-sidebar')).to_be_visible()
            page.keyboard.press('Escape')
            expect(page.get_by_role('button', name='메뉴 열기', exact=True)).to_be_focused()
        assert not errors, errors
        assert not writes, writes
        context.close()
    browser.close()

(output / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps({'screensChecked': len(results), 'pageErrors': 0, 'mutationRequests': 0, 'screenshots': str(output)}))
