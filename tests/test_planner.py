from littleshop.planner import build_plan, deal_strength, matches_ingredient


def fake_deal(name: str, rate: float = 20.0):
    return {
        "name": name,
        "manufacturer": None,
        "promotion_description": "מבצע",
        "discount_rate": rate,
        "regular_price": 10.0,
        "discounted_price": None,
        "chain": "test",
    }


def test_matches_hebrew_alias():
    ingredient = {"name": "broccoli", "search_terms": ["ברוקולי"]}
    assert matches_ingredient(ingredient, fake_deal("ברוקולי קפוא 800 גרם"))


def test_discount_rate_is_strength():
    assert deal_strength(fake_deal("x", 25)) == 25


def test_recipe_with_matching_deal_ranks_first():
    recipes = [
        {
            "id": "a",
            "name": "Broccoli meal",
            "prep_minutes": 30,
            "tags": ["vegetarian"],
            "ingredients": [
                {
                    "name": "broccoli",
                    "quantity": 500,
                    "unit": "g",
                    "search_terms": ["ברוקולי"],
                }
            ],
        },
        {
            "id": "b",
            "name": "Rice meal",
            "prep_minutes": 20,
            "tags": ["vegetarian"],
            "ingredients": [
                {
                    "name": "rice",
                    "quantity": 500,
                    "unit": "g",
                    "search_terms": ["אורז"],
                }
            ],
        },
    ]

    plan = build_plan(
        recipes,
        [fake_deal("ברוקולי טרי")],
        days=1,
        diet={"required_recipe_tags": ["vegetarian"]},
        max_recipe_repeats=1,
    )

    assert plan["meals"][0]["id"] == "a"
    assert plan["shopping_list"][0]["name"] == "broccoli"


def test_exclusion_blocks_egg_noodles():
    ingredient = {
        "name": "eggs",
        "search_terms": ["ביצים"],
        "exclude_terms": ["אטריות", "נודלס"],
    }
    assert not matches_ingredient(ingredient, fake_deal("נודלס ביצים 500 גרם"))


def test_product_name_wins_over_broad_promotion_description():
    ingredient = {"name": "cauliflower", "search_terms": ["כרובית"]}
    deal = fake_deal("תפרחות ברוקולי")
    deal["promotion_description"] = "כרובית/ברוקולי/תרד 800 גרם"
    assert not matches_ingredient(ingredient, deal)
