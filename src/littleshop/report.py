from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

from .shopping import SHOP_URLS, product_link


def _money(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"₪{value:.2f}"


def _qty(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def render_report(
    plan: dict[str, Any],
    chain_runs: list[dict[str, Any]],
    errors: list[str],
) -> str:
    lines: list[str] = []
    lines.append("# LittleShop weekly plan")
    lines.append("")
    lines.append(f"Generated: {datetime.now(ZoneInfo('Asia/Jerusalem')).isoformat(timespec='minutes')}")
    lines.append("")
    lines.append(
        f"Feed coverage: **{len(chain_runs)} loaded, {len(errors)} failed**."
    )
    if errors:
        lines.append("This plan uses only the stores loaded successfully.")
    if chain_runs and not any(run["deals"] for run in chain_runs):
        lines.append("Feeds loaded, but no active public promotions were found; meals are unranked by deals.")
    lines.append("")
    lines.append(
        "Meals are ranked by ingredient promotion matches. Shopping options are "
        "compared by estimated product cost plus delivery once per shop. "
        "Local branch prices may differ from online checkout prices."
    )
    lines.append("")

    lines.append("## Stores used")
    lines.append("")
    if chain_runs:
        for run in chain_runs:
            store = run["store"]
            location = ", ".join(
                part for part in [store.get("city"), store.get("address")] if part
            )
            lines.append(
                f"- **{run['chain']}** — {store.get('name') or 'unnamed branch'} "
                f"(store {store['store_id']})"
                + (f" — {location}" if location else "")
                + f" — {store['selection_reason']}"
            )
            for kind, source in run.get("source_files", {}).items():
                lines.append(
                    f"  - {kind} snapshot: {source['published_at'] or 'unknown date'} "
                    "(retailer time, Asia/Jerusalem)"
                )
                if source.get("xml_store_id") and source["xml_store_id"].lstrip("0") != str(store["store_id"]).lstrip("0"):
                    lines.append(
                        f"  - {kind} uses legacy XML store ID {source['xml_store_id']}; "
                        f"catalog and filename store ID: {store['store_id']}."
                    )
    else:
        lines.append("- No supermarket feed could be loaded.")

    if errors:
        lines.append("")
        lines.append("### Feed warnings")
        lines.append("")
        for error in errors:
            lines.append(f"- {error}")

    lines.append("")
    lines.append("## Meal plan")
    lines.append("")
    for index, meal in enumerate(plan["meals"], start=1):
        matched = meal.get("matched_deals", [])
        lines.append(f'<a id="recipe-day-{index}"></a>')
        lines.append(
            f"### Day {index}: {meal['name']} "
            f"({meal.get('prep_minutes', '?')} min)"
        )
        lines.append("")
        if meal.get('servings'):
            lines.append(f"Serves: {meal['servings']} · {', '.join(meal.get('tags', []))}")
            lines.append("")
        if meal.get('source'):
            source = meal['source']
            lines.append(f"Recipe: {escape(source['attribution'])} · {escape(source['license'])} · "
                         f"[Source]({source['url']}) · [Full recipe record](../data/recipes/{meal['id']}.json)")
            lines.append("")
        if meal.get('pantry'):
            lines.append("Pantry check (excluded from basket estimates): " + "; ".join(
                escape(str(i.get('quantity') or 'to taste') + ' ' + str(i.get('unit') or '') + ' ' + i['name'])
                for i in meal['pantry']))
            lines.append("")
        if meal.get('instructions'):
            lines += ["Method:", ""]
            lines += [f"{n}. {escape(step)}" for n, step in enumerate(meal['instructions'], 1)]
            lines.append("")
        lines.append(f"Promotion-match score: **{meal['deal_score']}**")
        lines.append("")
        lines.append("Ingredients: " + "; ".join(
            f"{i['name']} {_qty(i.get('quantity', 0))} {i.get('unit', '')}"
            for i in meal.get("ingredients", [])
        ))
        lines.append("")
        if matched:
            lines.append("Matched promotions (before delivery comparison):")
            for match in matched:
                deal = match["deal"]
                product = deal.get("name") or deal.get("item_code") or "unknown product"
                desc = deal.get("promotion_description") or "promotion"
                lines.append(
                    f"- **{match['ingredient']}** → {product} at "
                    f"{deal['chain']} ({_money(deal.get('regular_price'))} regular); "
                    f"{desc}"
                )
        else:
            lines.append("No currently published promotion matched this recipe.")
        lines.append("")

    lines.extend(render_shopping(plan))
    lines.append("")
    lines.append("## Highest-ranked recipe candidates")
    lines.append("")
    lines.append("| Recipe | Deal score | Promo-matched ingredients | Prep |")
    lines.append("|---|---:|---:|---:|")
    for recipe in plan["ranked_recipes"]:
        lines.append(
            f"| {recipe['name']} | {recipe['deal_score']} | "
            f"{len(recipe.get('matched_deals', []))} | "
            f"{recipe.get('prep_minutes', '?')} min |"
        )

    lines.append("")
    lines.append("## v1 interpretation notes")
    lines.append("")
    lines.append(
        "- Cost estimates round up to full packs when pack sizes are known. Ambiguous "
        "multi-buy, group and conditional offers use shelf prices instead. Unpriced "
        "ingredients are excluded from totals, not counted as free."
    )
    lines.append(
        "- Product matching is deterministic substring matching using aliases in "
        "config/recipes.yml; adjust aliases when a supermarket uses unexpected wording."
    )
    lines.append(
        "- Dietary filtering is recipe-tag based. Product-level allergen and kosher "
        "certification checking is not implemented in v1."
    )
    lines.append("")
    return "\n".join(lines)


def render_shopping(plan):
    lines = ['## Shopping by shop', '', '🍽️ links return to the recipe/day; 🛒 opens the product, search, or shop website.', '']
    strategy = plan.get('shopping_strategy')
    if strategy:
        lines += ['### Delivery-aware comparison', '',
                  f"Comparable scope: **{strategy['priceable_items']} of {strategy['total_items']} ingredient lines**. "
                  'Every comparable total covers the same lines. Other ingredients still need a price check.', '',
                  'Delivery-adjusted deal score = estimated savings versus the cheapest comparable single-shop option. '
                  'Higher is better. Delivery is charged once per used shop.', '',
                  '| Option | Products | Delivery | Total estimate | Deal score / savings | Status |',
                  '|---|---:|---:|---:|---:|---|']
        for option in strategy['alternatives']:
            status = []
            if option['missing_items']:
                status.append(f"missing {len(option['missing_items'])} priced lines; not comparable")
            if option['unknown_delivery']:
                status.append('delivery fee unknown')
            if option['minimum_shortfalls_cents']:
                status.append('below minimum: ' + ', '.join(
                    f"{shop} needs {_money(amount / 100)} more groceries"
                    for shop, amount in option['minimum_shortfalls_cents'].items()))
            if option is strategy['best']:
                status.insert(0, 'best evaluated estimate' if option['eligible'] else 'lowest estimate; minimum not met')
            total = option['total_cents']
            fee = sum(option['delivery_cents'].values()) if not option['unknown_delivery'] else None
            lines.append(f"| {' + '.join(option['shops'])} | {_money(option['items_cents'] / 100)} | "
                         f"{_money(fee / 100 if fee is not None else None)} | "
                         f"{_money(total / 100 if total is not None else None)} | "
                         f"{_money(option['delivery_adjusted_deal_score_ils'])} | {'; '.join(status) or 'estimate'} |")
        lines += ['', 'Estimates compare single shops and cheapest-item splits for shop combinations. '
                  'They are not guaranteed checkout totals or a complete multi-buy optimizer.', '']
        if not strategy['best']:
            lines += ['No delivery-adjusted recommendation is available with the current prices and fees.', '']
        for shop, policy in strategy['policies'].items():
            if shop not in {s for option in strategy['alternatives'] for s in option['shops']}:
                continue
            fee = _money(policy.get('fee_ils'))
            source = policy.get('source_url') or SHOP_URLS.get(shop)
            label = 'published fee' if policy.get('fee_status') == 'published' else 'assumed fee—confirm at checkout'
            minimum = policy.get('minimum_order_ils')
            lines.append(f"- **{shop}**: {fee} per delivery ({label}); "
                         + (f"minimum {_money(minimum)}" if minimum is not None else 'minimum order unverified')
                         + (f". [Delivery details]({source})" if source else '.'))
        lines += ['', 'Account benefits, free-delivery promotions, service fees and available delivery slots must be checked on the retailer website.', '']
    else:
        lines += ['Delivery comparison unavailable: full product/pack data or delivery settings are missing. '
                  'These groups show promotion matches only.', '']
    groups = plan.get('shopping_by_shop', {})
    for shop, items in groups.items():
        if shop == 'unassigned':
            lines += ['### Needs a price / shop check', '', 'Not included in the delivered-cost estimate.', '']
        else:
            url = SHOP_URLS.get(shop)
            lines += [f"### {shop}" + (f" — [🛒 Open shop]({url})" if url else ''), '']
            best = strategy.get('best') if strategy else None
            if best and shop in best['subtotals_cents']:
                lines += [f"Products: {_money(best['subtotals_cents'][shop] / 100)} · "
                          f"Delivery: {_money(best['delivery_cents'][shop] / 100)}", '']
        for item in items:
            text = f"- [ ] **{item['name']}** — {_qty(item['quantity'])} {item['unit']}"
            quote = item.get('quote')
            deal = item.get('suggested_deal')
            if quote:
                text += f" — {quote['product']['name']}; {quote['purchase']}; {_money(quote['cost_cents'] / 100)} ({quote['pricing_basis']})"
                url = quote['url']
            elif deal:
                text += f" — possible match: {deal.get('name') or deal.get('item_code')} ({deal.get('promotion_description') or 'promotion'})"
                url = product_link(deal)
            else:
                url = None
            if url:
                text += f' [🛒]({url} "Open retailer product, search or shop")'
            for recipe in item.get('recipes', []):
                title = f"Day {recipe['day']}: {recipe['name']}".replace('"', "'")
                text += f' [🍽️{recipe["day"]}](#{recipe["anchor"]} "{title}")'
            lines.append(text)
        lines.append('')
    return lines
