"""Run against a local Vite server with Playwright available on PYTHONPATH.

All API requests are intercepted; registration is verified without writing data.
Usage: python tests/randomExamples.browser.py [http://127.0.0.1:5184]
"""
import json
import sys
from playwright.sync_api import sync_playwright, expect

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:5184'
REQUIREMENT_ID = '11111111-1111-4111-8111-111111111111'

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel='chrome', headless=True)
    for width in [1440, 390]:
        context = browser.new_context(viewport={'width': width, 'height': 1000})
        page = context.new_page()
        writes, errors, dialogs = [], [], []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def api(route):
            request = route.request
            if request.method != 'GET':
                writes.append({'url': request.url, 'method': request.method, 'body': request.post_data_json})
            if request.method == 'POST' and request.url.endswith('/api/requirements'):
                body = {**request.post_data_json, 'id': REQUIREMENT_ID, 'status': 'DRAFT', 'createdAt': '2026-10-26T00:00:00Z'}
                route.fulfill(status=201, json=body)
            elif request.url.endswith('/dashboard/summary'):
                route.fulfill(json={'queriedAt': '2026-10-26T00:00:00Z', 'requirements': [], 'cases': [], 'counts': {}, 'basis': 'synthetic'})
            elif request.url.endswith('/analysis-jobs'):
                route.fulfill(json=[] if '/requirements/' in request.url else {'running': 0, 'queued': 0, 'succeeded': 0, 'failed': 0, 'jobs': []})
            else:
                route.fulfill(status=404, json={'message': 'No saved data in isolated UI test'})

        context.route('**/api/**', api)
        context.route('**/actuator/health', lambda route: route.fulfill(json={'status': 'UP'}))
        context.route('**/ai-health/health', lambda route: route.fulfill(json={'status': 'UP'}))
        page.goto(BASE + '/#requirements', wait_until='networkidle')
        examples = page.evaluate("async () => (await import('/src/requirementExamples.ts')).requirementExamples")
        button = page.get_by_role('button', name='랜덤 예제 불러오기', exact=True)
        title = page.locator('#requirement-title-input')
        description = page.locator('#requirement-description')

        def check(example):
            expect(title).to_have_value(example['title'])
            expect(description).to_have_value(example['description'])
            expect(page.get_by_text(f"예제 {example['id']}/5 · {example['title']}", exact=True)).to_be_visible()
            count = page.evaluate('(value) => value.length.toLocaleString()', example['description'])
            expect(page.get_by_text(f'{count} / 10,000', exact=True)).to_be_visible()

        # Each first-click interval reaches its corresponding example.
        for index, example in enumerate(examples):
            if index:
                page.reload(wait_until='networkidle')
            page.evaluate('(value) => { Math.random = () => value }', (index + 0.5) / 5)
            button.click()
            check(example)

        # Repeated clicks exclude the current example, without confirmation.
        def reject_dialog(dialog):
            dialogs.append(dialog.message)
            dialog.dismiss()

        page.on('dialog', reject_dialog)
        current = examples[-1]
        for _ in range(12):
            page.evaluate('Math.random = () => 0')
            expected = next(example for example in examples if example['id'] != current['id'])
            button.click()
            check(expected)
            current = expected
        assert not dialogs

        # Cancel preserves manually edited content and selected identity.
        description.fill('직접 작성한 문장입니다.')
        button.click()
        assert len(dialogs) == 1
        expect(description).to_have_value('직접 작성한 문장입니다.')
        expect(title).to_have_value(current['title'])
        page.remove_listener('dialog', reject_dialog)
        page.once('dialog', lambda dialog: dialog.accept())
        button.click()
        current = next(example for example in examples if example['id'] != current['id'])
        check(current)

        # A title-only edit must also be confirmed; cancelling changes neither field.
        title.fill('직접 작성 제목')
        page.once('dialog', lambda dialog: dialog.dismiss())
        button.click()
        expect(title).to_have_value('직접 작성 제목')
        expect(description).to_have_value(current['description'])
        assert writes == [], writes  # No save, analysis Job, generation, or execution.

        for locator in [button, title, description]:
            expect(locator).to_be_visible()
            box = locator.bounding_box()
            assert box and box['x'] >= 0 and box['x'] + box['width'] <= width + 1, box

        # Explicit save still submits the complete pair through the existing API.
        page.get_by_role('button', name='변경 요청 저장', exact=True).click()
        expect(page.locator('.requirement-result h3')).to_have_text('직접 작성 제목')
        assert len(writes) == 1 and writes[0]['url'].endswith('/api/requirements'), writes
        assert writes[0]['body'] == {'title': '직접 작성 제목', 'description': current['description']}
        expect(title).to_have_value('')
        expect(description).to_have_value('')
        assert not errors, errors
        print(json.dumps({'width': width, 'result': 'PASS', 'examples': 5, 'repeatClicks': 12, 'writesBeforeSave': 0, 'explicitSaves': 1}))
        context.close()
    browser.close()
