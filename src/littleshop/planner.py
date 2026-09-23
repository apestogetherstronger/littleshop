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
    haystack = normalize_text(
        " ".join(
            part
            for part in [
                deal.get("name"),
                deal.get("manufacturer"),
                deal.get("promotion_description"),
            ]
            if part
        )
    )
    if not haystack:
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
    return round(score, 2), matched


def build_plan(
    recipes: list[dict[str, Any]],
    deals: list[dict[str, Any]],
    *,
    days: int,
    diet: dict[str, Any],
    max_recipe_repeats: int = 1,
) -> dict[str, Any]:
    allowed = [recipe for recipe in recipes if recipe_is_allowed(recipe, diet)]
    if not allowed:
        raise RuntimeError("No recipes satisfy the configured dietary tags")

    ranked: list[dict[str, Any]] = []
    for recipe in allowed:
        score, matched = score_recipe(recipe, deals)
        ranked.append(
            {
                **recipe,
                "deal_score": score,
                "matched_deals": matched,
            }
        )

    ranked.sort(
        key=lambda recipe: (
            -recipe["deal_score"],
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
            adjusted = recipe["deal_score"] - (0.75 * overlap)
            return (-adjusted, recipe.get("prep_minutes", 9999), recipe["name"])

        chosen = min(available, key=choice_key)
        selected.append(chosen)
        repeats[chosen["id"]] += 1

    shopping: dict[tuple[str, str], dict[str, Any]] = {}
    for meal in selected:
        for ingredient in meal.get("ingredients", []):
            key = (ingredient["name"], ingredient.get("unit", ""))
            if key not in shopping:
                shopping[key] = {
                    "name": ingredient["name"],
                    "unit": ingredient.get("unit", ""),
                    "quantity": 0.0,
                    "search_terms": ingredient.get("search_terms", []),
                }
            shopping[key]["quantity"] += float(ingredient.get("quantity", 0))

    shopping_list: list[dict[str, Any]] = []
    for item in shopping.values():
        suggestion = best_deal_for_ingredient(item, deals)
        shopping_list.append(
            {
                "name": item["name"],
                "quantity": item["quantity"],
                "unit": item["unit"],
                "suggested_deal": suggestion,
            }
        )

    shopping_list.sort(key=lambda item: item["name"])

    return {
        "days": days,
        "meals": selected,
        "shopping_list": shopping_list,
        "ranked_recipes": ranked,
    }
