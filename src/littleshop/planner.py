from __future__ import annotations

from collections import defaultdict
import re
from typing import Any


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = value.casefold().replace("׳", "'").replace("״", '"')
    value = re.sub(r"[^\w\u0590-\u05ff]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def deal_strength(deal: dict[str, Any]) -> float:
    rate = deal.get("discount_rate")
    if isinstance(rate, (int, float)) and rate > 0:
        return min(float(rate), 100.0)

    regular = deal.get("regular_price")
    discounted = deal.get("discounted_price")
    if (
        isinstance(regular, (int, float))
        and isinstance(discounted, (int, float))
        and regular > 0
        and 0 < discounted < regular
    ):
        return min((1.0 - discounted / regular) * 100.0, 100.0)

    return 5.0


def matches_ingredient(ingredient: dict[str, Any], deal: dict[str, Any]) -> bool:
    # Prefer the actual SKU name. Promotion descriptions often mention several
    # unrelated products ("cauliflower/broccoli/spinach") and produce false hits.
    product_name = normalize_text(deal.get("name"))
    if not product_name:
        return False
    haystack = product_name

    patterns = ingredient.get("match_patterns", [])
    if patterns and not any(re.search(pattern, haystack) for pattern in patterns):
        return False

    required = ingredient.get("require_any_terms", [])
    if required and not any(normalize_text(str(term)) in haystack for term in required):
        return False

    for term in ingredient.get("exclude_terms", []):
        needle = normalize_text(str(term))
        if needle and needle in haystack:
            return False

    for term in ingredient.get("search_terms", []):
        needle = normalize_text(str(term))
        if needle and needle in haystack:
            return True
    return False


def best_deal_for_ingredient(
    ingredient: dict[str, Any], deals: list[dict[str, Any]]
) -> dict[str, Any] | None:
    candidates = [deal for deal in deals if matches_ingredient(ingredient, deal)]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda deal: (
            deal_strength(deal),
            -(deal.get("regular_price") or float("inf")),
        ),
    )


def recipe_is_allowed(recipe: dict[str, Any], diet: dict[str, Any]) -> bool:
    tags = set(recipe.get("tags", []))
    required = set(diet.get("required_recipe_tags", []))
    excluded = set(diet.get("excluded_recipe_tags", []))
    return required.issubset(tags) and not (tags & excluded)


def score_recipe(
    recipe: dict[str, Any], deals: list[dict[str, Any]]
) -> tuple[float, list[dict[str, Any]]]:
    matched: list[dict[str, Any]] = []
    score = 0.0
    for ingredient in recipe.get("ingredients", []):
        deal = best_deal_for_ingredient(ingredient, deals)
        if deal:
            strength = deal_strength(deal)
            score += 1.0 + min(strength, 50.0) / 10.0
            matched.append(
                {
                    "ingredient": ingredient["name"],
                    "deal": deal,
                    "strength": round(strength, 2),
                }
            )
    return round(score / max(1, len(recipe.get("ingredients", []))), 2), matched


def build_plan(
    recipes: list[dict[str, Any]],
    deals: list[dict[str, Any]],
    *,
    days: int,
    diet: dict[str, Any],
    max_recipe_repeats: int = 1,
    products: list[dict[str, Any]] | None = None,
    delivery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    allowed = [recipe for recipe in recipes if recipe_is_allowed(recipe, diet)]
    if not allowed:
        raise RuntimeError("No recipes satisfy the configured dietary tags")

    # Price availability outranks promotions: a discount cannot rescue an unbuyable meal.
    from .shopping import quote_item
    candidate_cache = {}
    def coverage(recipe):
        if not products:
            return 1.0
        known = {shop for shop, policy in (delivery or {}).get('shops', {}).items()
                 if policy.get('fee_ils') is not None}
        count = 0
        for ingredient in recipe.get('ingredients', []):
            key = ingredient['name']
            if key not in candidate_cache:
                candidate_cache[key] = [p for p in products if (not known or p['chain'] in known)
                                        and matches_ingredient(ingredient, p)]
            if any(quote_item(ingredient, p) for p in candidate_cache[key]):
                count += 1
        return count / max(1, len(recipe.get('ingredients', [])))

    ranked: list[dict[str, Any]] = []
    for recipe in allowed:
        score, matched = score_recipe(recipe, deals)
        time_penalty = round(max(0, (recipe.get("prep_minutes") or 60) - 60) / 15, 2)
        ranked.append(
            {
                **recipe,
                "price_coverage": coverage(recipe),
                "deal_score": score,
                "time_penalty": time_penalty,
                "ranking_score": round(score - time_penalty, 2),
                "matched_deals": matched,
            }
        )

    ranked.sort(
        key=lambda recipe: (
            -recipe["price_coverage"],
            -recipe["ranking_score"],
            recipe.get("prep_minutes", 9999),
            recipe["name"],
        )
    )

    selected: list[dict[str, Any]] = []
    repeats: dict[str, int] = defaultdict(int)

    while len(selected) < days:
        available = [
            recipe
            for recipe in ranked
            if repeats[recipe["id"]] < max_recipe_repeats
        ]
        if not available:
            max_recipe_repeats += 1
            continue

        previous_ingredients = (
            {i["name"] for i in selected[-1].get("ingredients", [])}
            if selected
            else set()
        )

        def choice_key(recipe: dict[str, Any]) -> tuple[float, int, str]:
            ingredients = {i["name"] for i in recipe.get("ingredients", [])}
            overlap = len(previous_ingredients & ingredients)
            adjusted = recipe["ranking_score"] - (0.75 * overlap)
            return (-recipe["price_coverage"], -adjusted, recipe.get("prep_minutes", 9999), recipe["name"])

        chosen = min(available, key=choice_key)
        selected.append(chosen)
        repeats[chosen["id"]] += 1

    shopping: dict[tuple[str, str], dict[str, Any]] = {}
    for day, meal in enumerate(selected, start=1):
        for ingredient in meal.get("ingredients", []):
            key = (ingredient["name"], ingredient.get("unit", ""))
            if key not in shopping:
                shopping[key] = {
                    "name": ingredient["name"],
                    "unit": ingredient.get("unit", ""),
                    "quantity": 0.0,
                    "search_terms": ingredient.get("search_terms", []),
                    "exclude_terms": ingredient.get("exclude_terms", []),
                    "require_any_terms": ingredient.get("require_any_terms", []),
                    "match_patterns": ingredient.get("match_patterns", []),
                    "spoon_unit": ingredient.get("spoon_unit"),
                    "recipes": [],
                }
            shopping[key]["quantity"] += float(ingredient.get("quantity", 0))
            shopping[key]["recipes"].append({"day": day, "name": meal["name"], "anchor": f"recipe-day-{day}"})

    shopping_list: list[dict[str, Any]] = []
    for item in shopping.values():
        suggestion = best_deal_for_ingredient(item, deals)
        shopping_list.append(
            {
                "name": item["name"],
                "quantity": item["quantity"],
                "unit": item["unit"],
                "suggested_deal": suggestion,
                "search_terms": item["search_terms"],
                "exclude_terms": item["exclude_terms"],
                "require_any_terms": item["require_any_terms"],
                "match_patterns": item["match_patterns"],
                "spoon_unit": item["spoon_unit"],
                "recipes": item["recipes"],
                "shop": suggestion["chain"] if suggestion else None,
            }
        )

    shopping_list.sort(key=lambda item: item["name"])
    from .shopping import compare_baskets
    strategy = compare_baskets(shopping_list, products or [], deals, delivery or {})
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in shopping_list:
        grouped[item.get("shop") or "unassigned"].append(item)

    return {
        "days": days,
        "meals": selected,
        "shopping_list": shopping_list,
        "ranked_recipes": ranked,
        "shopping_by_shop": dict(sorted(grouped.items())),
        "shopping_strategy": strategy,
    }
