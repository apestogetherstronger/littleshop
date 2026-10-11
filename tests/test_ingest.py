from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from israeli_prices.models import FileType, PriceFile, Store, StoresFile

from littleshop import ingest
from littleshop.ingest import _is_active, _is_general_public_promo, _load_file, resolve_store


def test_missing_named_branch_never_falls_back():
    stores = StoresFile(stores=[Store(store_id='1', name='Other branch', city='הרצליה')])
    with pytest.raises(RuntimeError, match='no branch matched'):
        resolve_store(stores, 'test', {'name_contains': 'סוקולוב', 'city': 'הרצליה'})


def test_named_branch_can_use_numeric_city_code():
    store = Store(store_id='715', name='סוקולוב הרצליה', city='6400')
    selected, _ = resolve_store(StoresFile(stores=[store]), 'test',
                                {'name_contains': 'סוקולוב', 'city': 'הרצליה'})
    assert selected == store


def test_explicit_store_id_accepts_leading_zeros():
    store = Store(store_id='007', name='Requested')
    selected, reason = resolve_store(StoresFile(stores=[store]), 'test', {'store_id': '7'})
    assert selected == store
    assert reason == 'explicit store_id'


@pytest.mark.parametrize('now, expected', [
    (datetime(2026, 7, 1, 20, 59, tzinfo=timezone.utc), True),
    (datetime(2026, 7, 1, 21, 1, tzinfo=timezone.utc), False),
    (datetime(2026, 1, 1, 21, 1, tzinfo=timezone.utc), True),
    (datetime(2026, 1, 1, 22, 1, tzinfo=timezone.utc), False),
])
def test_naive_promotion_expiry_uses_israeli_summer_and_winter_time(now, expected):
    end = datetime(now.year, now.month, 1, 23, 59)
    assert _is_active(None, end, now) is expected


def test_aware_promotion_bounds_and_naive_now_are_supported():
    start = datetime(2026, 7, 1, 21, 0, tzinfo=timezone.utc)
    assert not _is_active(start, None, datetime(2026, 7, 1, 23, 59))
    assert _is_active(start, None, datetime(2026, 7, 2, 0, 0))


def test_structured_coupon_flag_excludes_generic_description():
    promo = SimpleNamespace(is_coupon=True, description='מבצע', club_id='0')
    assert not _is_general_public_promo(promo)


@pytest.mark.parametrize('store_id', ['8', None])
def test_mismatched_or_missing_xml_store_id_is_rejected(monkeypatch, store_id):
    adapter = SimpleNamespace(latest=lambda *args, **kwargs: 'ref', download=lambda ref: b'xml')
    monkeypatch.setattr(ingest.ilp, 'parse', lambda payload: PriceFile(store_id=store_id))
    with pytest.raises(RuntimeError, match='expected store 7'):
        _load_file(adapter, FileType.PRICE_FULL, '7')


def test_xml_store_id_accepts_zero_padding(monkeypatch):
    adapter = SimpleNamespace(latest=lambda *args, **kwargs: 'ref', download=lambda ref: b'xml')
    expected = PriceFile(store_id='007')
    monkeypatch.setattr(ingest.ilp, 'parse', lambda payload: expected)
    assert _load_file(adapter, FileType.PRICE_FULL, '7') is expected


def test_empty_price_snapshot_is_rejected_and_client_closed(monkeypatch):
    closed = []
    monkeypatch.setattr(ingest, 'HttpClient', lambda **kwargs: SimpleNamespace(close=lambda: closed.append(True)))
    monkeypatch.setattr(ingest.ilp, 'get_adapter', lambda *args, **kwargs: object())
    stores = StoresFile(stores=[Store(store_id='7', name='Local', city='הרצליה')])
    monkeypatch.setattr(ingest, '_load_file', lambda adapter, kind, *args:
                        stores if kind == FileType.STORES else PriceFile(store_id='7'))
    with pytest.raises(RuntimeError, match='empty price snapshot'):
        ingest.fetch_chain('test', {'city': 'הרצליה'})
    assert closed == [True]


@pytest.mark.parametrize('chain, timeout, retries', [
    ('shufersal', 45.0, 2), ('carrefour', 12.0, 1), ('rami-levy', 12.0, 1),
])
def test_retailer_request_budgets_stay_bounded(monkeypatch, chain, timeout, retries):
    budgets = []
    closed = []
    monkeypatch.setattr(ingest, 'HttpClient', lambda **kwargs:
                        budgets.append(kwargs) or SimpleNamespace(close=lambda: closed.append(True)))
    monkeypatch.setattr(ingest, 'get_adapter', lambda *args: object())
    def unavailable(*args):
        raise RuntimeError('unavailable')
    monkeypatch.setattr(ingest, '_load_file', unavailable)
    with pytest.raises(RuntimeError, match='unavailable'):
        ingest.fetch_chain(chain, {})
    assert budgets == [{'timeout': timeout, 'retries': retries}]
    assert closed == [True]
