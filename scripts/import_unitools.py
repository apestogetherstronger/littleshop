"""Import the vegetarian subset from a pinned local UniTools JSON snapshot."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from littleshop.config import load_yaml
from littleshop.recipe_import import normalize, save_batch

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('dataset',type=Path)
p.add_argument('--revision',required=True)
p.add_argument('--output',type=Path,default=Path('data/recipes'))
a=p.parse_args()
payload=a.dataset.read_bytes();data=json.loads(payload)
if data.get('license')!='CC BY-SA 4.0':raise SystemExit('Unexpected dataset license')
dictionary=load_yaml('config/ingredients.yml')['ingredients']
source={'url':data['homepage'],'attribution':data['attribution'],'license':'CC-BY-SA-4.0',
        'license_url':data['licenseUrl'],'revision':a.revision,
        'dataset_url':f'https://github.com/farcrak/unitools-recipes/blob/{a.revision}/unitools-recipes-v1.json',
        'sha256':hashlib.sha256(payload).hexdigest(),
        'changes':'English subset; shared ingredient IDs; units normalized; dietary and completeness checks. No photos.'}
records=[]
for r in data['recipes']:
    if not set(r['diets'])&{'vegetarian','vegan'}:continue
    record={'name':r['name']['en'],'source_id':r['slug'],'servings':r['baseServings'],
            'prep_minutes':r['prepMinutes']+r['cookMinutes'],'category':r['category'],
            'tags':r['diets'],'instructions':[s['text']['en'] for s in r['steps']],
            'raw_ingredients':[{'name':i['name']['en'],'quantity':i['quantity'],'unit':i['unit'],
                                'note':(i.get('note') or {}).get('en')} for i in r['ingredients']]}
    records.append(normalize(record,dictionary,source))
print(save_batch(records,a.output))
print('Status:',dict(Counter(r['status'] for r in records)))
print('Ready meal categories:',dict(Counter(r['category'] for r in records if r['status']=='ready')))
