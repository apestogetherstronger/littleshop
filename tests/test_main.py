import json
from pathlib import Path

import pytest
import yaml

from littleshop import main as app


@pytest.fixture
def project(tmp_path, monkeypatch):
    config = tmp_path / 'config'
    config.mkdir()
    (config / 'settings.yml').write_text(yaml.safe_dump({
        'chains': [{'slug': 'good'}, {'slug': 'broken'}],
        'plan': {'days': 1},
    }))
    recipes = Path(__file__).resolve().parents[1] / 'config/recipes.yml'
    (config / 'recipes.yml').write_text(recipes.read_text())
    (config / 'ingredients.yml').write_text((recipes.parent / 'ingredients.yml').read_text())
    monkeypatch.setattr(app, 'ROOT', tmp_path)
    return tmp_path


def success(slug, deals=None):
    return {
        'chain': slug,
        'store': {'store_id': '7', 'name': 'Local', 'city': 'הרצליה', 'selection_reason': 'explicit store_id'},
        'price_item_count': 10,
        'promotion_count': 0,
        'deals': deals or [],
    }


def read_status(project):
    return json.loads((project / 'output/run-status.json').read_text())


def test_total_failure_preserves_all_previous_outputs(project, monkeypatch):
    paths = ['docs/latest.md', 'output/plan.json', 'output/deals.json']
    for name in paths:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'previous successful output')

    def fail(*args):
        raise TimeoutError('portal unavailable')

    monkeypatch.setattr(app, 'fetch_chain', fail)
    assert app.main() == 1
    assert all((project / name).read_bytes() == b'previous successful output' for name in paths)
    status = read_status(project)
    assert status['status'] == 'failed'
    assert not status['plan_published']
    assert len(status['errors']) == 2
    assert status['loaded_chains'] == []


def test_partial_failure_still_generates_plan_and_diagnostics(project, monkeypatch):
    def fetch(slug, spec):
        if slug == 'broken':
            raise RuntimeError('missing full snapshot')
        return success(slug)

    monkeypatch.setattr(app, 'fetch_chain', fetch)
    assert app.main() == 0
    status = read_status(project)
    assert status['status'] == 'partial'
    assert status['plan_published']
    assert status['loaded_chains'] == ['good']
    report = (project / 'docs/latest.md').read_text()
    assert '1 loaded, 1 failed' in report
    assert 'no active public promotions' in report
    assert 'missing full snapshot' in report
    assert len(json.loads((project / 'output/plan.json').read_text())['plan']['meals']) == 1


def test_valid_empty_promotion_feeds_are_successful(project, monkeypatch):
    monkeypatch.setattr(app, 'fetch_chain', lambda slug, spec: success(slug))
    assert app.main() == 0
    status = read_status(project)
    assert status['status'] == 'ok'
    assert status['plan_published']
    assert status['active_promotion_rows'] == 0


def test_no_enabled_chains_fails_without_creating_plan(project, monkeypatch):
    (project / 'config/settings.yml').write_text('chains:\n  - slug: disabled\n    enabled: false\n')
    def unexpected(*args):
        pytest.fail('disabled feed must not be fetched')
    monkeypatch.setattr(app, 'fetch_chain', unexpected)
    assert app.main() == 1
    assert not (project / 'docs/latest.md').exists()
    assert read_status(project)['configured_chains'] == []


def test_equal_deals_are_sorted_before_planning(project, monkeypatch):
    deals = [{'chain': 'good', 'store_id': '7', 'item_code': code,
              'promotion_id': 'promo', 'name': 'ברוקולי', 'discount_rate': 20,
              'regular_price': 10} for code in ['2', '1']]
    monkeypatch.setattr(app, 'fetch_chain', lambda slug, spec: success(slug, deals if slug == 'good' else []))
    assert app.main() == 0
    saved = json.loads((project / 'output/deals.json').read_text())
    assert [deal['item_code'] for deal in saved] == ['1', '2']
    plan = json.loads((project / 'output/plan.json').read_text())['plan']
    broccoli = next(item for item in plan['shopping_list'] if item['name'] == 'broccoli')
    assert broccoli['suggested_deal']['item_code'] == '1'
