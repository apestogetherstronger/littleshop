"""Rebuild a report from the last successful local feed snapshot, without downloads."""
import json
from pathlib import Path
from littleshop.catalog import load_catalog
from littleshop.config import load_yaml
from littleshop.planner import build_plan
from littleshop.report import render_report

root=Path(__file__).resolve().parents[1]
settings=load_yaml(root/'config/settings.yml')
old=json.loads((root/'output/plan.json').read_text())
status=json.loads((root/'output/run-status.json').read_text())
if not status.get('plan_published'):
    raise SystemExit('Latest feed status is not a published successful snapshot; refusing to mislabel cached data')
deals=json.loads((root/'output/deals.json').read_text())
products=json.loads((root/'output/products.json').read_text())
plan=build_plan(load_catalog(root),deals,days=settings['plan']['days'],diet=settings['diet'],
                max_recipe_repeats=settings['plan']['max_recipe_repeats'],products=products,delivery=settings['delivery'])
plan['feed_generated_at']=status['generated_at']
runs=[{'chain':s['chain'],'store':s,'source_files':s.get('source_files',{}),
       'deals':[d for d in deals if d['chain']==s['chain']]} for s in old['stores']]
(root/'docs/latest.md').write_text(render_report(plan,runs,old['errors']))
(root/'output/plan.json').write_text(json.dumps({**old,'plan':plan},ensure_ascii=False,indent=2))
s=plan['shopping_strategy']; rec=s['recommendation']
print(json.dumps({'meals':[m['name'] for m in plan['meals']], 'priced':s['priceable_items'],
 'total':s['total_items'],'unpriced':s['unpriced_items'],'remaining':s['remaining_items'],
 'recommended_shops':rec['shops'] if rec else None,'subtotal_with_delivery':rec['partial_total_cents']/100 if rec else None},ensure_ascii=False))
