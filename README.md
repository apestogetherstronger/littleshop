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

The workflow is also scheduled weekly. It runs tests, fetches the current supermarket data, generates `docs/latest.md` and `output/*.json`, and uploads the plan and deals as an artifact. Scheduled and manual runs on `main` commit the latest Markdown report; JSON outputs remain in the artifacts. Pull requests run offline regression tests only.

## Feed health and failure handling

- A failed chain is reported while the remaining chains continue. Reports show how many chains loaded and whether coverage is partial.
- If **all chains fail** (or none are enabled), the command exits with code 1 and leaves the existing report, plan JSON and deals JSON unchanged. An existing report still carries its original generation date; it is not a fresh plan.
- `output/run-status.json` records the run timestamp, configured and loaded chains, active promotion count, feed errors and whether a new plan was generated. GitHub Actions includes this in the job summary and a separate `littleshop-feed-health` artifact even on failure.
- A valid feed with no active public promotions is allowed. This is different from failing to load a feed.
- A configured `name_contains` must match a branch name or address; it never falls back to an unrelated branch. Name matching takes precedence over city matching because some retailer catalogs contain city codes instead of city names. Use an explicit `store_id` to disambiguate branches. Numeric IDs tolerate leading zeros.
- Price and promotion XML must identify the selected store; empty price snapshots are rejected. Promotion validity and report timestamps use `Asia/Jerusalem`.
- Carrefour's landing page resets its listing each Israeli calendar day. If a branch has not published today's full files yet, the adapter checks the two preceding dated listings, newest first. It never substitutes another branch or an incremental file. Snapshot publication dates are shown in the report and retained in the JSON outputs.
- Carrefour Neve Amirim uses transparency ID `461` in its catalog, filenames and promotions, but its price XML uses `413`, corresponding to catalog legacy code `(4130)`. An explicit adapter mapping accepts this verified price-only pair only when the selected catalog entry still contains `(4130)`. Both IDs are retained in diagnostics, and other mismatches still fail. This mapping is based on the retailer's live files, not a documented universal conversion rule.
- Shufersal uses a 45-second per-request timeout with up to two attempts because its healthy listing was observed taking 29 seconds. Requests filter the branch on the server and sort newest first, with a 20-page safety limit instead of an unbounded scan of every branch.

The listing compatibility fixes live in `src/littleshop/adapters.py`; the pinned `israeli-prices` dependency still handles downloads and XML parsing. Public diagnostics retain filenames and publication dates, never expiring signed download URLs. Full snapshots can predate later incremental changes; check the reported snapshot time when interpreting a deal.

For an unavailable portal, inspect the feed-health artifact first. A `FileNotFound` means the adapter did not find the requested full snapshot or store catalog; an incremental `Price` file is **not** a safe replacement for `PriceFull`. Timeouts can reflect portal outages or runner network restrictions. The same local command above can be run from an Israeli connection to distinguish these cases. These safeguards do not remove retailer access restrictions.

## Current limitations

This first iteration intentionally does not:

- use an LLM;
- verify kosher certification from product packaging;
- create a retailer shopping cart;
- model every multi-buy promotion exactly;
- optimize nutrition;
- maintain long-term historical prices.

Those are natural follow-up iterations once the basic feed → deal → recipe loop is working.
