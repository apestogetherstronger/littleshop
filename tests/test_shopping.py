from copy import deepcopy

from littleshop.planner import build_plan
from littleshop.report import render_report
from littleshop.shopping import compare_baskets, product_link, quote_item


def ingredient(name='rice', quantity=1000, unit='g'):
    return {'name': name, 'quantity': quantity, 'unit': unit, 'search_terms': [name]}


def product(shop, name='rice', price=10, **extra):
    return {'chain': shop, 'store_id': '1', 'item_code': name, 'name': name,
            'regular_price': price, 'pack_quantity': 1000, 'pack_unit': 'g',
            'is_weighted': False, **extra}


def policy(**fees):
    return {'shops': {shop: {'fee_ils': fee} for shop, fee in fees.items()}}


def test_delivery_makes_one_shop_cheaper_than_split():
    items = [ingredient('rice'), ingredient('beans')]
    products = [product('a', 'rice', 8), product('a', 'beans', 10),
                product('b', 'rice', 10), product('b', 'beans', 8)]
    result = compare_baskets(items, products, [], policy(a=5, b=5))
    assert result['best']['shops'] == ['a']
    assert result['best']['total_cents'] == 2300
    split = next(option for option in result['alternatives'] if len(option['shops']) == 2)
    assert split['total_cents'] == 2600
    assert split['delivery_adjusted_deal_score_ils'] == -3
    assert {item['shop'] for item in items} == {'a'}


def test_split_wins_when_savings_exceed_extra_delivery():
    items = [ingredient('rice'), ingredient('beans')]
    products = [product('a', 'rice', 5), product('a', 'beans', 50),
                product('b', 'rice', 50), product('b', 'beans', 5)]
    result = compare_baskets(items, products, [], policy(a=10, b=10))
    assert result['best']['shops'] == ['a', 'b']
    assert result['best']['total_cents'] == 3000
    assert result['best']['delivery_adjusted_deal_score_ils'] == 35


def test_delivery_charged_once_per_used_shop_not_per_item():
    items = [ingredient('rice'), ingredient('beans')]
    result = compare_baskets(items, [product('a'), product('a', 'beans')], [], policy(a=35.9))
    assert result['best']['delivery_cents'] == {'a': 3590}
    assert result['best']['total_cents'] == 5590


def test_unknown_ingredient_is_not_treated_as_free():
    items = [ingredient('rice'), ingredient('unavailable')]
    result = compare_baskets(items, [product('a')], [], policy(a=5))
    assert result['priceable_items'] == 1
    assert result['total_items'] == 2
    assert result['unpriced_items'] == ['unavailable']
    assert items[1]['shop'] is None


def test_incomplete_single_shop_never_beats_complete_split_by_omission():
    items = [ingredient('rice'), ingredient('beans')]
    result = compare_baskets(items, [product('a'), product('b', 'beans')], [], policy(a=1, b=1))
    assert result['best']['shops'] == ['a', 'b']
    assert all(option['total_cents'] is None for option in result['alternatives'] if len(option['shops']) == 1)


def test_unknown_delivery_fee_never_defaults_to_zero():
    items = [ingredient()]
    result = compare_baskets(items, [product('a')], [], policy(a=None))
    assert result['best'] is None
    assert items[0]['shop'] is None


def test_minimum_shortfalls_are_reported_and_orderable_candidate_preferred():
    items = [ingredient()]
    policies = policy(a=1, b=2)
    policies['shops']['a']['minimum_order_ils'] = 200
    result = compare_baskets(items, [product('a'), product('b')], [], policies)
    assert result['best']['shops'] == ['b']
    a = next(option for option in result['alternatives'] if option['shops'] == ['a'])
    assert a['minimum_shortfalls_cents'] == {'a': 19000}
    assert not a['eligible']
    assert a['delivery_adjusted_deal_score_ils'] is None


def test_pack_rounding_and_mass_conversion():
    quote = quote_item(ingredient(quantity=1200), product('a', price=10, pack_quantity=.5, pack_unit='קילוגרם'))
    assert quote['packages'] == 3
    assert quote['cost_cents'] == 3000


def test_incompatible_or_unknown_units_are_not_guessed():
    assert quote_item(ingredient(unit='head'), product('a')) is None
    assert quote_item(ingredient(unit='ml'), product('a')) is None
    assert quote_item(ingredient(), product('a', pack_quantity=None)) is None


def test_weighted_price_uses_reference_unit():
    quote = quote_item(ingredient(quantity=600), product('a', is_weighted=True, unit_of_measure='קילוגרם', unit_price=15))
    assert quote['cost_cents'] == 900
    assert quote['packages'] is None


def test_only_explicitly_simple_discounts_change_estimates():
    p = product('a', price=10)
    conditional = {'discounted_price': 1, 'simple_unit_promotion': False}
    safe = {'discounted_price': 8, 'simple_unit_promotion': True}
    quote = quote_item(ingredient(), p, [conditional, safe])
    assert quote['cost_cents'] == 800
    assert quote['promotion'] == safe
    assert quote_item(ingredient(), p, [conditional])['cost_cents'] == 1000


def test_grocery_links_do_not_invent_barcode_for_internal_sku():
    assert product_link({'chain': 'carrefour', 'item_code': '123', 'gtin': None}) == 'https://www.carrefour.co.il/'
    assert product_link({'chain': 'carrefour', 'item_code': '7290000000001', 'gtin': '07290000000001'}).endswith('?product=7290000000001')
    assert 'q=' in product_link({'chain': 'rami-levy', 'name': 'אורז'})


def test_grouped_shopping_keeps_all_recipe_links_and_delivery_report():
    recipes = [{'id': 'one', 'name': 'Rice bowl', 'ingredients': [ingredient(quantity=500)], 'tags': []},
               {'id': 'two', 'name': 'More rice', 'ingredients': [ingredient(quantity=500)], 'tags': []}]
    plan = build_plan(recipes, [], days=2, diet={}, products=[product('a')], delivery=policy(a=5))
    item = plan['shopping_by_shop']['a'][0]
    assert item['quantity'] == 1000
    assert [recipe['day'] for recipe in item['recipes']] == [1, 2]
    assert plan['shopping_strategy']['best']['delivery_cents'] == {'a': 500}
    report = render_report(plan, [], [])
    for day in [1, 2]:
        assert f'<a id="recipe-day-{day}"></a>' in report
        assert f'](#recipe-day-{day} ' in report
    assert 'Shopping by shop' in report
    assert 'Delivery-aware comparison' in report
    assert '₪15.00' in report
