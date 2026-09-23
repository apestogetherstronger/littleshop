from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import load_yaml
from .ingest import fetch_chain
from .planner import build_plan
from .report import render_report


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    settings = load_yaml(ROOT / "config/settings.yml")
    recipes_doc = load_yaml(ROOT / "config/recipes.yml")
    recipes = recipes_doc.get("recipes", [])

    chain_runs: list[dict[str, Any]] = []
    errors: list[str] = []
    all_deals: list[dict[str, Any]] = []

    default_city = settings.get("location", {}).get("city")

    for chain_spec in settings.get("chains", []):
        if not chain_spec.get("enabled", True):
            continue

        spec = dict(chain_spec)
        if not spec.get("city"):
            spec["city"] = default_city

        slug = spec["slug"]
        try:
            result = fetch_chain(slug, spec)
        except Exception as exc:
            errors.append(f"{slug}: {type(exc).__name__}: {exc}")
            continue

        chain_runs.append(result)
        all_deals.extend(result["deals"])

    plan_cfg = settings.get("plan", {})
    plan = build_plan(
        recipes,
        all_deals,
        days=int(plan_cfg.get("days", 7)),
        diet=settings.get("diet", {}),
        max_recipe_repeats=int(plan_cfg.get("max_recipe_repeats", 1)),
    )

    output_cfg = settings.get("output", {})
    report_path = ROOT / output_cfg.get("report_path", "docs/latest.md")
    plan_json_path = ROOT / output_cfg.get("plan_json_path", "output/plan.json")
    deals_json_path = ROOT / output_cfg.get("deals_json_path", "output/deals.json")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_report(plan, chain_runs, errors),
        encoding="utf-8",
    )

    _write_json(
        plan_json_path,
        {
            "stores": [
                run["store"] | {"chain": run["chain"]}
                for run in chain_runs
            ],
            "errors": errors,
            "plan": plan,
        },
    )
    _write_json(deals_json_path, all_deals)

    print(f"Generated {report_path.relative_to(ROOT)}")
    print(f"Loaded {len(all_deals)} active promotion-product rows")
    if errors:
        print(f"{len(errors)} chain(s) had feed warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
