from __future__ import annotations

from datetime import datetime
from typing import Any


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
    lines.append(f"Generated: {datetime.now().isoformat(timespec='minutes')}")
    lines.append("")
    lines.append(
        "This v1 ranks meals by matching their ingredients to active supermarket "
        "promotions. It does **not** yet use historical prices or calculate a fully "
        "optimized basket total."
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
        lines.append(
            f"### Day {index}: {meal['name']} "
            f"({meal.get('prep_minutes', '?')} min)"
        )
        lines.append("")
        lines.append(f"Promotion-match score: **{meal['deal_score']}**")
        lines.append("")
        if matched:
            lines.append("Matched promotions:")
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

    lines.append("## Consolidated shopping list")
    lines.append("")
    for item in plan["shopping_list"]:
        deal = item.get("suggested_deal")
        base = (
            f"- [ ] **{item['name']}** — "
            f"{_qty(item['quantity'])} {item['unit']}"
        ).rstrip()
        if deal:
            product = deal.get("name") or deal.get("item_code") or "matched product"
            desc = deal.get("promotion_description") or "promotion"
            base += f" — suggested: {product} @ {deal['chain']} ({desc})"
        lines.append(base)

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
        "- Promotion descriptions are shown as published by the retailer. Multi-buy "
        "and group promotions are not converted into a guaranteed per-unit basket price yet."
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
