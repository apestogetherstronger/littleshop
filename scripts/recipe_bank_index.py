"""Build a readable recipe bank index, with a separate review queue."""
import json
from pathlib import Path
from littleshop.catalog import load_catalog
from littleshop.config import load_yaml

root=Path(__file__).resolve().parents[1]
records=[r for p in (root/'data/recipes').glob('*.json') for r in json.loads(p.read_text())['recipes']]
ready=[r for r in records if r['status']=='ready']
original_count=len(load_yaml(root/'config/recipes.yml')['recipes'])
lines=['# Recipe bank','',f'{len(records)} imported recipes plus {original_count} original meal templates. '
       f'{len(ready)} imported recipes pass structural and ingredient checks; '
       f'{len(load_catalog(root))} total mains/soups/templates are eligible for weekly planning.','',
       'Imported recipe data: [UniTools — theunitools.com](https://theunitools.com/en/data), '
       '[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). '
       'Adapted into English records with shared ingredient IDs and validation notes. Photos are not included. '
       'Each record retains its pinned source revision and full instructions.','',
       '“Ready” means usable structure, quantities and ingredient mappings; it does not promise retailer coverage '
       'or independent culinary testing. Only ready mains and soups enter the weekly planner. '
       'Other categories are retained for browsing. Diet tags below are source claims; conflicts stay in review.','',
       '[Original meal templates](../config/recipes.yml) · [Shared ingredient dictionary](../config/ingredients.yml)','']
for title,items in [('Validated imports',ready),('Needs review',[r for r in records if r['status']!='ready'])]:
 lines += ['## '+title,'','| Recipe / full record | Category | Source diet tags | Minutes | Review notes |','|---|---|---|---:|---|']
 for r in sorted(items,key=lambda r:r['name']):
  notes='; '.join(r['review_issues']).replace('|',' / ')
  lines.append(f"| [{r['name']}](../data/recipes/{r['id']}.json) | {r['category']} | {', '.join(r['tags'])} | {r['prep_minutes']} | {notes or '—'} |")
 lines.append('')
(root/'docs/recipe-bank.md').write_text('\n'.join(lines))
