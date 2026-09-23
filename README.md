# littleshop

A backend-free weekly meal planner that uses Israel's public supermarket price-transparency feeds.

## v1

- Fetch prices and promotions from configured supermarket branches.
- Match promoted products to a small curated recipe catalog.
- Build a deterministic 7- or 14-day vegetarian meal plan.
- Generate an ingredient-level shopping list plus exact promoted-product suggestions.
- Run manually or on a schedule in GitHub Actions.
- Publish the latest Markdown plan into `docs/latest.md`.

No LLM or external application backend is required.

The current implementation uses the `israeli-prices` Python package for the government-mandated retailer feeds. Some retailer portals may reject GitHub-hosted runners because of geo restrictions; those chains are reported as warnings while the remaining chains continue.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m littleshop.main
```

Configuration lives in `config/settings.yml`. Recipes and ingredient aliases live in `config/recipes.yml`.

## GitHub Actions

Use **Actions → Weekly meal plan → Run workflow** for an immediate run.

The workflow is also scheduled weekly. It runs tests, fetches the current supermarket data, generates `docs/latest.md` and `output/*.json`, uploads them as an artifact, and commits changed generated files back to the repository.

## Current limitations

This first iteration intentionally does not:

- use an LLM;
- verify kosher certification from product packaging;
- create a retailer shopping cart;
- model every multi-buy promotion exactly;
- optimize nutrition;
- maintain long-term historical prices.

Those are natural follow-up iterations once the basic feed → deal → recipe loop is working.
