# LittleShop weekly plan

Generated: 2026-09-23T17:23

This v1 ranks meals by matching their ingredients to active supermarket promotions. It does **not** yet use historical prices or calculate a fully optimized basket total.

## Stores used

- No supermarket feed could be loaded.

### Feed warnings

- shufersal: RuntimeError: shufersal: no branch matched city='הרצליה' name_contains=None; set store_id explicitly
- rami-levy: RuntimeError: rami-levy: no branch matched city='הרצליה' name_contains=None; set store_id explicitly
- carrefour: RuntimeError: carrefour: no branch matched city='הרצליה' name_contains=None; set store_id explicitly
- victory: PortalError: GET https://laibcatalog.co.il/webapi/api/getfiles failed after 3 attempts: timed out

## Meal plan

### Day 1: Bean & cheese quesadillas (25 min)

Promotion-match score: **0.0**

No currently published promotion matched this recipe.

### Day 2: Broccoli & ricotta pasta (30 min)

Promotion-match score: **0.0**

No currently published promotion matched this recipe.

### Day 3: Shakshuka with feta (30 min)

Promotion-match score: **0.0**

No currently published promotion matched this recipe.

### Day 4: Tofu vegetable stir-fry (30 min)

Promotion-match score: **0.0**

No currently published promotion matched this recipe.

### Day 5: Zucchini & feta frittata (35 min)

Promotion-match score: **0.0**

No currently published promotion matched this recipe.

### Day 6: Lentil & sweet-potato curry (40 min)

Promotion-match score: **0.0**

No currently published promotion matched this recipe.

### Day 7: Roasted cauliflower & chickpea tray (40 min)

Promotion-match score: **0.0**

No currently published promotion matched this recipe.

## Consolidated shopping list

- [ ] **beans** — 500 g
- [ ] **bell pepper** — 600 g
- [ ] **broccoli** — 1000 g
- [ ] **cauliflower** — 1 head
- [ ] **chickpeas** — 500 g
- [ ] **coconut milk** — 400 ml
- [ ] **corn** — 300 g
- [ ] **eggs** — 18 units
- [ ] **feta** — 450 g
- [ ] **lentils** — 400 g
- [ ] **parmesan** — 80 g
- [ ] **pasta** — 500 g
- [ ] **rice** — 800 g
- [ ] **ricotta** — 250 g
- [ ] **sweet potato** — 800 g
- [ ] **tahini** — 200 g
- [ ] **tofu** — 600 g
- [ ] **tomato sauce** — 500 g
- [ ] **tomatoes** — 1200 g
- [ ] **tortillas** — 10 units
- [ ] **yellow cheese** — 450 g
- [ ] **zucchini** — 800 g

## Highest-ranked recipe candidates

| Recipe | Deal score | Promo-matched ingredients | Prep |
|---|---:|---:|---:|
| Bean & cheese quesadillas | 0.0 | 0 | 25 min |
| Broccoli & ricotta pasta | 0.0 | 0 | 30 min |
| Shakshuka with feta | 0.0 | 0 | 30 min |
| Tofu vegetable stir-fry | 0.0 | 0 | 30 min |
| Zucchini & feta frittata | 0.0 | 0 | 35 min |
| Lentil & sweet-potato curry | 0.0 | 0 | 40 min |
| Roasted cauliflower & chickpea tray | 0.0 | 0 | 40 min |
| Roasted vegetable couscous | 0.0 | 0 | 45 min |
| Potato & broccoli cheese bake | 0.0 | 0 | 55 min |
| Spinach & ricotta lasagna | 0.0 | 0 | 60 min |

## v1 interpretation notes

- Promotion descriptions are shown as published by the retailer. Multi-buy and group promotions are not converted into a guaranteed per-unit basket price yet.
- Product matching is deterministic substring matching using aliases in config/recipes.yml; adjust aliases when a supermarket uses unexpected wording.
- Dietary filtering is recipe-tag based. Product-level allergen and kosher certification checking is not implemented in v1.
