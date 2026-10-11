from datetime import date
import json
from types import SimpleNamespace

import pytest
from israeli_prices.exceptions import FileNotFound, PortalError
from israeli_prices.models import FileType

from littleshop.adapters import CarrefourAdapter, ShufersalAdapter


def listing(day, names):
    return f"const path = '{day}'; const files = {json.dumps([{'name': n} for n in names])};"


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        key = params.get('date', params.get('page'))
        return SimpleNamespace(text=self.pages[key])


def carrefour(pages):
    client = FakeClient(pages)
    adapter = CarrefourAdapter(client)
    adapter.today = date(2026, 10, 12)
    return adapter, client


def test_carrefour_midnight_falls_back_to_full_snapshot_and_caches_listing():
    full = 'PriceFull7290055700007-001-461-20261011-051016.gz'
    promo = 'PromoFull7290055700007-001-461-20261011-051122.gz'
    adapter, client = carrefour({
        '20261012': listing('20261012', ['Price7290055700007-001-461-20261012-010000.gz']),
        '20261011': listing('20261011', [full, promo]),
    })
    ref = adapter.latest(FileType.PRICE_FULL, '461')
    assert ref.name == full
    assert ref.url == f'https://prices.carrefour.co.il/20261011/{full}'
    assert adapter.latest(FileType.PROMO_FULL, '0461').name == promo
    assert len(client.calls) == 2  # shared cached listings, no repeated HTTP calls
    assert adapter.selected_files['PriceFull']['published_at'] == '2026-10-11T05:10:16'
    assert 'url' not in adapter.selected_files['PriceFull']


def test_carrefour_prefers_newest_of_multiple_today_snapshots():
    old = 'PriceFull7290055700007-001-461-20261012-010000.gz'
    new = 'PriceFull7290055700007-001-461-20261012-020000.gz'
    adapter, client = carrefour({'20261012': listing('20261012', [old, new])})
    assert adapter.latest(FileType.PRICE_FULL, '461').name == new
    assert len(client.calls) == 1


def test_carrefour_never_substitutes_incremental_wrong_store_or_old_file():
    names = ['Price7290055700007-001-461-20261012-010000.gz',
             'PriceFull7290055700007-001-416-20261012-010000.gz',
             'PriceFull7290055700007-001-461-20260901-010000.gz']
    adapter, client = carrefour({
        '20261012': listing('20261012', names),
        '20261011': listing('20261011', []),
        '20261010': listing('20261010', []),
    })
    with pytest.raises(FileNotFound, match='checked 3 calendar days'):
        adapter.latest(FileType.PRICE_FULL, '461')
    assert len(client.calls) == 3


@pytest.mark.parametrize('page', ['<html>outage</html>', listing('20261011', [])])
def test_carrefour_rejects_missing_or_wrong_dated_listing(page):
    adapter, _ = carrefour({'20261012': page})
    with pytest.raises(PortalError):
        adapter.latest(FileType.STORES)


def link(name):
    return f'<a href="https://example.blob.core.windows.net/{name}?a=1&amp;b=2">download</a>'


def test_shufersal_filters_on_server_and_client_and_preserves_signed_url():
    correct = 'PriceFull7290027600007-001-042-20261012-020000.gz'
    wrong = 'PriceFull7290027600007-001-043-20261012-030000.gz'
    client = FakeClient({1: link(wrong) + link(correct)})
    adapter = ShufersalAdapter(client)
    ref = adapter.latest(FileType.PRICE_FULL, '042')
    assert ref.name == correct
    assert ref.url.endswith('?a=1&b=2')
    assert client.calls[0][1] == {'catID': 2, 'storeId': 42, 'page': 1, 'sort': 'Time', 'sortdir': 'DESC'}
    assert 'url' not in adapter.selected_files['PriceFull']


def test_shufersal_stores_request_uses_all_stores():
    name = 'Stores7290027600007-000-20261012-020.gz'
    client = FakeClient({1: link(name)})
    assert ShufersalAdapter(client).latest(FileType.STORES).name == name
    assert client.calls[0][1]['catID'] == 5
    assert client.calls[0][1]['storeId'] == 0


def test_shufersal_repeated_page_stops_instead_of_looping():
    wrong = link('PriceFull7290027600007-001-043-20261012-030000.gz')
    client = FakeClient({1: wrong, 2: wrong})
    with pytest.raises(FileNotFound):
        ShufersalAdapter(client).latest(FileType.PRICE_FULL, '42')
    assert len(client.calls) == 2


def test_shufersal_can_find_requested_store_on_next_page():
    wrong = link('PriceFull7290027600007-001-043-20261012-030000.gz')
    correct = 'PriceFull7290027600007-001-042-20261012-020000.gz'
    client = FakeClient({1: wrong, 2: link(correct)})
    assert ShufersalAdapter(client).latest(FileType.PRICE_FULL, '42').name == correct
    assert len(client.calls) == 2


def test_shufersal_page_limit_is_bounded():
    pages = {i: link(f'PriceFull7290027600007-001-043-20261012-{i:02d}0000.gz') for i in range(1, 21)}
    client = FakeClient(pages)
    with pytest.raises(PortalError, match='exceeded 20 pages'):
        ShufersalAdapter(client).latest(FileType.PRICE_FULL, '42')
    assert len(client.calls) == 20


def test_carrefour_legacy_price_alias_requires_catalog_evidence():
    from israeli_prices.models import Store
    adapter, _ = carrefour({})
    assert not adapter.accepts_store_alias(FileType.PRICE_FULL, '461', '413')
    adapter.configure_store(Store(store_id='461', name='נווה אמירים (4130)'))
    assert adapter.accepts_store_alias(FileType.PRICE_FULL, '461', '413')
    assert not adapter.accepts_store_alias(FileType.PROMO_FULL, '461', '413')
    assert not adapter.accepts_store_alias(FileType.PRICE_FULL, '461', '414')
    assert not adapter.accepts_store_alias(FileType.PRICE_FULL, '413', '127')
    adapter.configure_store(Store(store_id='461', name='Different branch (9990)'))
    assert not adapter.accepts_store_alias(FileType.PRICE_FULL, '461', '413')


def test_verified_alias_preserves_raw_xml_and_records_both_ids(monkeypatch):
    from israeli_prices.models import Store, PriceFile
    from littleshop import ingest
    full = 'PriceFull7290055700007-001-461-20261012-051016.gz'
    adapter, _ = carrefour({'20261012': listing('20261012', [full])})
    adapter.configure_store(Store(store_id='461', name='נווה אמירים (4130)'))
    monkeypatch.setattr(adapter, 'download', lambda ref: b'xml')
    monkeypatch.setattr(ingest.ilp, 'parse', lambda payload: PriceFile(store_id='413'))
    parsed = ingest._load_file(adapter, FileType.PRICE_FULL, '461')
    assert parsed.store_id == '413'  # preserve source identity
    source = adapter.selected_files['PriceFull']
    assert source['store_id'] == '461'
    assert source['xml_store_id'] == '413'
