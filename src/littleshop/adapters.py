"""Small compatibility adapters for the pinned israeli-prices 0.2.0 client.

Verified against the retailers' public portals. Keep downloads and XML parsing
in israeli-prices; fix only listing discovery and record snapshot provenance.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import html
import json
import re
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo

import israeli_prices as ilp
from israeli_prices.chains.base import ChainAdapter, parse_filename, same_store
from israeli_prices.chains.carrefour import INFO as CARREFOUR_INFO
from israeli_prices.chains.shufersal import INFO as SHUFERSAL_INFO
from israeli_prices.exceptions import FileNotFound, PortalError
from israeli_prices.models import FileRef, FileType


ISRAEL_TZ = ZoneInfo('Asia/Jerusalem')


class SnapshotAdapter(ChainAdapter):
    def __init__(self, client=None):
        super().__init__(client=client)
        self.selected_files = {}

    def latest(self, file_type, store_id=None):
        ref = super().latest(file_type, store_id)
        # Signed download URLs must not be persisted in public reports/artifacts.
        self.selected_files[file_type.value] = {
            'name': ref.name,
            'published_at': ref.published_at.isoformat() if ref.published_at else None,
        }
        return ref


class CarrefourAdapter(SnapshotAdapter):
    info = CARREFOUR_INFO
    # Today and two preceding Israeli calendar days, including weekend rollover.
    LOOKBACK_DAYS = 3

    def __init__(self, client=None):
        super().__init__(client=client)
        self.today = datetime.now(ISRAEL_TZ).date()
        self._listings = {}
        self._price_store_alias = None

    def configure_store(self, store):
        # Observed in the official 2026-10-11 feeds: filenames/promotions use
        # transparency ID 461, while price XML uses 413 for legacy branch 4130.
        # Other sampled branches also use truncated legacy IDs in price XML.
        # Do NOT infer aliases for arbitrary branches: require the verified
        # pair and the catalog's legacy code, and preserve both IDs in outputs.
        self._price_store_alias = None
        if same_store(str(store.store_id), '461') and re.search(r'\(4130\)\s*$', store.name or ''):
            self._price_store_alias = ('461', '413')

    def accepts_store_alias(self, file_type, expected, actual):
        return (file_type == FileType.PRICE_FULL
                and self._price_store_alias == ('461', '413')
                and same_store(expected, '461') and same_store(actual, '413'))

    def _listing(self, day):
        if day in self._listings:
            return self._listings[day]
        stamp = day.strftime('%Y%m%d')
        page = self.client.get(self.info.portal_url + '/', params={'date': stamp}).text
        path_match = re.search(r"const\s+path\s*=\s*['\"](\d{8})['\"]", page)
        files_match = re.search(r'const\s+files\s*=\s*(\[.*?\])\s*;', page, re.S)
        if not path_match or not files_match:
            raise PortalError('carrefour: dated file listing not found')
        if path_match.group(1) != stamp:
            raise PortalError(f'carrefour: portal returned a different date than {stamp}')
        try:
            rows = json.loads(files_match.group(1))
        except ValueError as exc:
            raise PortalError('carrefour: invalid file listing JSON') from exc
        refs = []
        for row in rows:
            name = row.get('name', '').strip()
            kind, store, published = parse_filename(name)
            # Do not accept undated/stale files or construct paths from arbitrary
            # row values. Each fallback must contain a dated full snapshot.
            if not kind or not published or published.date() != day or '/' in name or '\\' in name:
                continue
            refs.append(FileRef(chain=self.info.slug, name=name, file_type=kind,
                                store_id=store, published_at=published,
                                url=f'{self.info.portal_url}/{stamp}/{quote(name)}'))
        refs.sort(key=lambda ref: (ref.published_at, ref.name), reverse=True)
        self._listings[day] = refs
        return refs

    def iter_files(self, file_type=None, store_id=None):
        for offset in range(self.LOOKBACK_DAYS):
            for ref in self._listing(self.today - timedelta(days=offset)):
                if file_type is not None and ref.file_type != file_type:
                    continue
                if store_id is not None and not same_store(ref.store_id, store_id):
                    continue
                yield ref

    def latest(self, file_type, store_id=None):
        try:
            return super().latest(file_type, store_id)
        except FileNotFound as exc:
            raise FileNotFound(f'{exc}; checked {self.LOOKBACK_DAYS} calendar days') from exc


class ShufersalAdapter(SnapshotAdapter):
    info = SHUFERSAL_INFO
    CATEGORY_IDS = {None: 0, FileType.PRICE: 1, FileType.PRICE_FULL: 2,
                    FileType.PROMO: 3, FileType.PROMO_FULL: 4, FileType.STORES: 5}
    MAX_PAGES = 20

    def iter_files(self, file_type=None, store_id=None):
        seen = set()
        for page in range(1, self.MAX_PAGES + 1):
            response = self.client.get(self.info.portal_url + '/FileObject/UpdateCategory',
                                       params={'catID': self.CATEGORY_IDS[file_type],
                                               'storeId': int(store_id) if store_id else 0,
                                               'page': page, 'sort': 'Time', 'sortdir': 'DESC'})
            links = re.findall(r'href=[\"\'](https://[^\"\']+?\.gz[^\"\']*)[\"\']', response.text)
            refs = []
            new = 0
            for link in links:
                url = html.unescape(link)
                name = urlsplit(url).path.rsplit('/', 1)[-1]
                if name in seen:
                    continue
                seen.add(name)
                new += 1
                kind, store, published = parse_filename(name)
                if not kind or (file_type is not None and kind != file_type):
                    continue
                # Keep client-side validation too: the portal may ignore filters.
                if store_id is not None and not same_store(store, store_id):
                    continue
                refs.append(FileRef(chain=self.info.slug, name=name, file_type=kind,
                                    store_id=store, published_at=published, url=url))
            refs.sort(key=lambda ref: (ref.published_at or datetime.min, ref.name), reverse=True)
            yield from refs
            if new == 0:
                return
        raise PortalError(f'shufersal: listing exceeded {self.MAX_PAGES} pages')


def get_adapter(chain, client):
    if chain == 'carrefour':
        return CarrefourAdapter(client=client)
    if chain == 'shufersal':
        return ShufersalAdapter(client=client)
    return ilp.get_adapter(chain, client=client)
