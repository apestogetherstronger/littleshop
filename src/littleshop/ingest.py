from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import re
from typing import Any

import israeli_prices as ilp


def _num(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.casefold().replace("׳", "'").replace("״", '"')
    value = re.sub(r"[^\w\u0590-\u05ff]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def resolve_store(chain: str, spec: dict[str, Any]) -> tuple[Any, str]:
    stores_file = ilp.get_stores(chain)
    stores = stores_file.stores
    if not stores:
        raise RuntimeError(f"{chain}: no stores returned")

    requested_id = str(spec.get("store_id") or "").strip()
    if requested_id:
        for store in stores:
            if str(store.store_id) == requested_id:
                return store, "explicit store_id"
        raise RuntimeError(f"{chain}: store_id {requested_id!r} not found")

    city = normalize_text(spec.get("city"))
    name_contains = normalize_text(spec.get("name_contains"))

    candidates = list(stores)
    if city:
        candidates = [
            store
            for store in candidates
            if city in normalize_text(store.city)
            or city in normalize_text(store.address)
        ]

    if name_contains:
        candidates = [
            store for store in candidates if name_contains in normalize_text(store.name)
        ]

    if not candidates:
        raise RuntimeError(
            f"{chain}: no branch matched city={spec.get('city')!r} "
            f"name_contains={spec.get('name_contains')!r}; set store_id explicitly"
        )

    candidates.sort(key=lambda store: str(store.store_id))
    reason = f"auto-selected from {len(candidates)} matching branch(es)"
    return candidates[0], reason


def _is_active(start: datetime | None, end: datetime | None, now: datetime) -> bool:
    if start and now < start:
        return False
    if end and now > end:
        return False
    return True


def fetch_chain(chain: str, spec: dict[str, Any]) -> dict[str, Any]:
    store, selection_reason = resolve_store(chain, spec)
    prices = ilp.get_prices(chain, store_id=str(store.store_id))
    promos = ilp.get_promos(chain, store_id=str(store.store_id))

    by_code = {item.item_code: item for item in prices.items}
    now = datetime.now()
    deals: list[dict[str, Any]] = []

    for promo in promos.promotions:
        if not _is_active(promo.start_time, promo.end_time, now):
            continue

        for promo_item in promo.items:
            price_item = by_code.get(promo_item.item_code)
            regular_price = _num(price_item.price) if price_item else None
            discounted_price = _num(
                promo_item.discounted_price
                if promo_item.discounted_price is not None
                else promo.discounted_price
            )
            discount_rate = _num(
                promo_item.discount_rate
                if promo_item.discount_rate is not None
                else promo.discount_rate
            )
            min_qty = _num(
                promo_item.min_qty
                if promo_item.min_qty is not None
                else promo.min_qty
            )

            deals.append(
                {
                    "chain": chain,
                    "store_id": str(store.store_id),
                    "store_name": store.name,
                    "store_city": store.city,
                    "store_address": store.address,
                    "item_code": promo_item.item_code,
                    "gtin": price_item.gtin if price_item else promo_item.gtin,
                    "name": price_item.name if price_item else None,
                    "manufacturer": price_item.manufacturer if price_item else None,
                    "regular_price": regular_price,
                    "unit_price": _num(price_item.unit_price) if price_item else None,
                    "promotion_id": promo.promotion_id,
                    "promotion_description": promo.description,
                    "discount_rate": discount_rate,
                    "discounted_price": discounted_price,
                    "min_qty": min_qty,
                    "club_id": promo.club_id,
                    "start_time": promo.start_time.isoformat() if promo.start_time else None,
                    "end_time": promo.end_time.isoformat() if promo.end_time else None,
                }
            )

    return {
        "chain": chain,
        "store": {
            "store_id": str(store.store_id),
            "name": store.name,
            "city": store.city,
            "address": store.address,
            "selection_reason": selection_reason,
        },
        "price_item_count": len(prices.items),
        "promotion_count": len(promos.promotions),
        "deals": deals,
    }
