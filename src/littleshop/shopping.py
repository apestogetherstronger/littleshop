"""Quantity-aware shopping estimates with delivery charged per shop, not per item."""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from itertools import combinations
import re
from urllib.parse import urlencode

from .planner import matches_ingredient, normalize_text

SHOP_URLS = {
    'shufersal': 'https://www.shufersal.co.il/online/',
    'rami-levy': 'https://www.rami-levy.co.il/he',
    'carrefour': 'https://www.carrefour.co.il/',
    'victory': 'https://victory.co.il/',
}


def product_link(product):
    chain = product.get('chain')
    # Only use barcode product links for GTINs, never chain-internal produce IDs.
    barcode = str(product.get('item_code') or '') if product.get('gtin') else None
    if chain == 'carrefour' and barcode:
        return SHOP_URLS[chain] + '?' + urlencode({'product': barcode})
    if chain == 'rami-levy':
        query = {'q': product.get('name') or barcode or ''}
        if barcode:
            query['item'] = barcode
        return SHOP_URLS[chain] + '/online/search?' + urlencode(query)
    return SHOP_URLS.get(chain)


def cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def unit(value):
    value = normalize_text(str(value or ''))
    aliases = {
        'g': ('mass', 1), 'גרם': ('mass', 1), 'גר': ('mass', 1),
        'kg': ('mass', 1000), 'ק ג': ('mass', 1000), 'קילוגרם': ('mass', 1000), 'קילוגרמים': ('mass', 1000),
        'ml': ('volume', 1), 'מ ל': ('volume', 1), 'מיליליטר': ('volume', 1),
        'l': ('volume', 1000), 'ליטר': ('volume', 1000),
        'units': ('count', 1), 'יחידה': ('count', 1), 'יחידות': ('count', 1),
        'יח': ('count', 1), 'יחי': ('count', 1),
        '100 גרם': ('mass', 100), '100 מ ל': ('volume', 100),
    }
    return aliases.get(value)


def quote_item(ingredient, product, promotions=()):
    needed_unit = unit(ingredient.get('unit'))
    if ingredient.get('unit') in {'tbsp', 'tsp'} and ingredient.get('spoon_unit') == 'ml':
        needed_unit = ('volume', 15 if ingredient['unit'] == 'tbsp' else 5)
    regular = product.get('regular_price')
    if not needed_unit or not regular or regular <= 0 or ingredient.get('quantity', 0) <= 0:
        return None
    metadata_note = None
    needed = Decimal(str(ingredient['quantity'])) * needed_unit[1]
    price = Decimal(str(regular))
    selected_promo = None
    for promo in promotions:
        if not promo.get('simple_unit_promotion'):
            continue
        discounted = promo.get('discounted_price')
        rate = promo.get('discount_rate')
        candidate = None
        if discounted is not None and 0 < discounted < regular:
            candidate = Decimal(str(discounted))
        elif rate is not None and 0 < rate < 100:
            candidate = Decimal(str(regular)) * (1 - Decimal(str(rate)) / 100)
        if candidate is not None and candidate < price:
            price, selected_promo = candidate, promo
    if product.get('is_weighted'):
        measure = unit(product.get('unit_of_measure'))
        unit_price = product.get('unit_price')
        if not measure or measure[0] != needed_unit[0] or not unit_price or unit_price <= 0:
            return None
        cost = needed / measure[1] * Decimal(str(unit_price)) * price / Decimal(str(regular))
        purchase = f"{ingredient['quantity']:g} {ingredient['unit']} by weight"
        packages = None
    else:
        package_unit = unit(product.get('pack_unit'))
        quantity = product.get('pack_quantity')
        pack_label = product.get('pack_unit')
        # Repair an incompatible catalog unit only when the name explicitly states
        # one package size and its numeric quantity agrees with the catalog.
        labels = re.findall(r"(\d+(?:\.\d+)?)\s*(קילוגרם|קג|ק ג|גרם|גר|מיליליטר|מ ל|ליטר)\b",
                            normalize_text(product.get('name')))
        if len(labels) == 1 and (not package_unit or package_unit[0] != needed_unit[0]):
            label_qty, label_unit = labels[0]
            parsed_unit = unit(label_unit) or (('mass', 1000) if label_unit == 'קג' else None)
            if parsed_unit and parsed_unit[0] == needed_unit[0] and float(label_qty) == quantity:
                package_unit, quantity, pack_label = parsed_unit, float(label_qty), label_unit
                metadata_note = 'Pack unit taken from explicit product name; catalog unit disagrees'
        # Some feeds label egg packs in kg. Use only an explicit count on the product name.
        if needed_unit[0] == 'count' and (not package_unit or package_unit[0] != 'count'):
            count = re.search(r'\b(\d+)\s*יח(?:ידות|ידה)?\b', normalize_text(product.get('name')))
            if count:
                package_unit, quantity = ('count', 1), int(count[1])
        if not package_unit or package_unit[0] != needed_unit[0] or not quantity or quantity <= 0:
            return None
        size = Decimal(str(quantity)) * package_unit[1]
        # Disagreeing pack metadata otherwise produces cheap but undersized orders.
        named = re.search(r"(\d+(?:\.\d+)?)\s*(קילוגרם|קג|ק ג|גרם|גר|מיליליטר|מ ל|ליטר)\b",
                          normalize_text(product.get('name')))
        if named:
            named_unit = unit(named[2]) or (('mass', 1000) if named[2] == 'קג' else None)
            if named_unit and named_unit[0] == package_unit[0]:
                named_size = Decimal(named[1]) * named_unit[1]
                if abs(named_size - size) > size * Decimal('0.05'):
                    return None
        # A truncated numeric label on a purported kilogram pack is not enough
        # evidence to buy that pack as 1 kg (e.g. pasta labelled only "40").
        trailing = re.search(r" (\d+)$", normalize_text(product.get('name')))
        if not named and trailing and package_unit[0] == 'mass' and size >= 1000:
            if Decimal(trailing[1]) not in {size, Decimal(str(quantity))}:
                return None
        reference = unit(product.get('unit_of_measure'))
        reference_price = product.get('unit_price')
        if reference and reference[0] == package_unit[0] and reference_price and reference_price > 0:
            implied_price = size / reference[1] * Decimal(str(reference_price))
            if abs(implied_price - Decimal(str(regular))) > max(Decimal('0.2'), Decimal(str(regular)) * Decimal('0.1')):
                return None
        packages = int((needed / size).to_integral_value(rounding=ROUND_CEILING))
        cost = packages * price
        purchase = f"{packages} pack(s) × {quantity:g} {('units' if package_unit[0] == 'count' else pack_label)}"
    return {'product': product, 'cost_cents': cents(cost), 'purchase': purchase,
            'packages': packages, 'promotion': selected_promo,
            'needed_base': float(needed), 'purchased_base': float(needed if packages is None else packages * size),
            'pack_size_base': None if packages is None else float(size),
            'base_dimension': needed_unit[0],
            'pricing_basis': 'simple promotion' if selected_promo else 'shelf price',
            'url': product_link(product), 'metadata_note': metadata_note}


def compare_baskets(items, products, deals, delivery):
    """Enumerate single shops and cheapest-item splits for each shop subset.

    Comparisons always cover the SAME union of priceable ingredient lines.
    Missing lines remain unknown, never zero-cost. Fixed delivery fees are added
    once per used shop. Minimum-order shortfalls are explicit eligibility checks;
    this is a comparison of evaluated plans, not a general cart/MILP optimizer.
    """
    if not products or not delivery:
        return None
    policies = delivery.get('shops', {})
    promotions = {}
    for deal in deals:
        promotions.setdefault((deal['chain'], deal.get('store_id'), deal.get('item_code')), []).append(deal)
    choices = []
    matched_counts = []
    for item in items:
        by_shop = {}
        matched_count = 0
        for product in products:
            chain = product['chain']
            if not matches_ingredient(item, product):
                continue
            matched_count += 1
            quote = quote_item(item, product, promotions.get((chain, product.get('store_id'), product.get('item_code')), []))
            if quote is None:
                continue
            old = by_shop.get(chain)
            if old is None or (quote['cost_cents'], str(product.get('item_code'))) < (old['cost_cents'], str(old['product'].get('item_code'))):
                by_shop[chain] = quote
        choices.append(by_shop)
        matched_counts.append(matched_count)
    priceable = [i for i, choices_i in enumerate(choices) if choices_i]
    shops = sorted({shop for row in choices for shop in row})
    if len(shops) > 8:
        raise ValueError('Delivery comparison supports at most 8 shops')
    alternatives = []
    seen = set()
    for count in range(1, len(shops) + 1):
        for subset in combinations(shops, count):
            assignments = {}
            subtotals = {}
            missing = []
            for i in priceable:
                options = [(choices[i][shop]['cost_cents'], shop) for shop in subset if shop in choices[i]]
                if not options:
                    missing.append(items[i]['name'])
                    continue
                cost, shop = min(options)
                assignments[i] = shop
                subtotals[shop] = subtotals.get(shop, 0) + cost
            if not assignments:
                continue
            identity = tuple(sorted(assignments.items()))
            if identity in seen:
                continue
            seen.add(identity)
            fees = {}
            shortfalls = {}
            unknown_fees = []
            for shop, subtotal in subtotals.items():
                policy = policies.get(shop, {})
                fee = policy.get('fee_ils')
                if fee is None:
                    unknown_fees.append(shop)
                else:
                    if fee < 0:
                        raise ValueError('Delivery fees cannot be negative')
                    fees[shop] = cents(fee)
                minimum = policy.get('minimum_order_ils')
                if minimum is not None and subtotal < cents(minimum):
                    shortfalls[shop] = cents(minimum) - subtotal
            complete = not missing and not unknown_fees
            total = sum(subtotals.values()) + sum(fees.values()) if complete else None
            alternatives.append({'shops': sorted(subtotals), 'assignments': assignments,
                                 'subtotals_cents': subtotals, 'delivery_cents': fees,
                                 'items_cents': sum(subtotals.values()), 'total_cents': total,
                                 'partial_total_cents': sum(subtotals.values()) + sum(fees.values()) if not unknown_fees else None,
                                 'missing_items': missing, 'unknown_delivery': unknown_fees,
                                 'minimum_shortfalls_cents': shortfalls,
                                 'eligible': complete and not shortfalls})
    eligible = [option for option in alternatives if option['eligible']]
    # If minimums cannot be satisfied, show the best arithmetic estimate but
    # explicitly mark it as unorderable on the priced lines alone.
    comparable = eligible or [option for option in alternatives if option['total_cents'] is not None]
    best = min(comparable, key=lambda option: (option['total_cents'], len(option['shops']), option['shops'])) if comparable else None
    singles = [option for option in comparable if len(option['shops']) == 1]
    baseline = min((option['total_cents'] for option in singles), default=None)
    for option in alternatives:
        option['delivery_adjusted_deal_score_ils'] = (
            round((baseline - option['total_cents']) / 100, 2)
            if baseline is not None and option['total_cents'] is not None and option['eligible'] == bool(eligible) else None
        )
    # Keep a useful partial order even when one line needs a shop with an unknown fee.
    # Its subtotal is explicitly scoped to assigned lines, never compared as a full total.
    partials = [o for o in alternatives if not o['unknown_delivery'] and not o['minimum_shortfalls_cents']]
    recommendation = best if best and best['eligible'] else (
        min(partials, key=lambda o: (-len(o['assignments']), o['partial_total_cents'], len(o['shops']), o['shops']))
        if partials else None)
    for i, item in enumerate(items):
        item['shop'] = None
        item['quote'] = None
        item['suggested_deal'] = None
        item['check_reason'] = ('No matching product in loaded catalogs' if not matched_counts[i]
                                else 'Product found, but quantity/pack units cannot be priced reliably')
        item['order_status'] = 'needs_check'
        if recommendation and i in recommendation['assignments']:
            shop = recommendation['assignments'][i]
            item['shop'], item['quote'] = shop, choices[i][shop]
            item['suggested_deal'] = choices[i][shop]['promotion']
            item['check_reason'] = None
            item['order_status'] = 'recommended'
        elif choices[i]:
            # These are individually priced extras, not a second recommended order.
            shop = min(choices[i], key=lambda s: (choices[i][s]['cost_cents'], s))
            item['shop'], item['quote'] = shop, choices[i][shop]
            item['order_status'] = 'conditional'
            item['check_reason'] = 'Separately priced item; delivery fee/minimum must be checked before ordering'
    remaining = [items[i]['name'] for i in range(len(items))
                 if not recommendation or i not in recommendation['assignments']]
    alternatives.sort(key=lambda option: (not option['eligible'], option['total_cents'] is None,
                                           option['total_cents'] or float('inf'), option['shops']))
    return {'best': best, 'recommendation': recommendation, 'remaining_items': remaining,
            'alternatives': alternatives, 'policies': policies,
            'priceable_items': len(priceable), 'total_items': len(items),
            'unpriced_items': [items[i]['name'] for i in range(len(items)) if i not in priceable],
            'scope': 'priceable ingredient lines only; local-branch prices, not an online cart quote'}
