"""Offline-first, conservative recipe import. No model or external service needed."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
from .config import load_yaml


def canonical_url(url):
    p = urlsplit(url)
    if p.scheme not in {'http', 'https'} or not p.hostname or p.username or p.password:
        raise ValueError('A public HTTP(S) source URL is required')
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', p.query, ''))


def norm(text):
    return re.sub(r'\s+', ' ', str(text).casefold()).strip()


class RecipeHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.active = False; self.buffer = []; self.documents = []
    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('type', '').lower() == 'application/ld+json':
            self.active = True; self.buffer = []
    def handle_data(self, data):
        if self.active: self.buffer.append(data)
    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.active = False
            try: self.documents.append(json.loads(''.join(self.buffer)))
            except json.JSONDecodeError: pass


def recipe_nodes(value):
    if isinstance(value, list):
        for v in value: yield from recipe_nodes(v)
    elif isinstance(value, dict):
        types = value.get('@type', [])
        if isinstance(types, str): types = [types]
        if any(str(t).rsplit('/', 1)[-1] == 'Recipe' for t in types):
            yield value
        else:
            for v in value.values(): yield from recipe_nodes(v)


def extract(text):
    try: docs = json.loads(text)
    except json.JSONDecodeError:
        parser = RecipeHTML(); parser.feed(text); docs = parser.documents
    return list(recipe_nodes(docs))


def minutes(value):
    m = re.fullmatch(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?', str(value or ''))
    if not m or not any(m.groups()): return None
    d,h,mi,s = [int(n or 0) for n in m.groups()]
    return math.ceil(d*1440+h*60+mi+s/60)


def steps(value):
    if isinstance(value, str): return [value] if value.strip() else []
    if isinstance(value, list): return [s for v in value for s in steps(v)]
    if isinstance(value, dict): return steps(value.get('itemListElement') or value.get('text', ''))
    return []


def servings(value):
    if isinstance(value, list): value = value[0] if value else None
    m = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(?:servings?|people|persons?)?', str(value or ''), re.I)
    return float(m[1]) if m and float(m[1]) > 0 else None


UNITS = {'g':'g','grams':'g','gram':'g','kg':'kg','ml':'ml','l':'l',
         'piece':'units','pieces':'units','unit':'units','units':'units',
         'tsp':'tsp','teaspoon':'tsp','teaspoons':'tsp',
         'tbsp':'tbsp','tablespoon':'tbsp','tablespoons':'tbsp',
         'clove':'clove','cloves':'clove','pinch':'pinch','sprig':'sprig','slice':'slice'}


def parse_line(line):
    # Unsupported ranges, cups and can sizes remain explicit review items.
    line = str(line).strip().replace('½',' 1/2').replace('¼',' 1/4').replace('¾',' 3/4').strip()
    m = re.fullmatch(r'(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)\s+(.+)', line)
    if not m: return {'name':line, 'quantity':None, 'unit':None}
    try: qty = float(sum(Fraction(n) for n in m[1].split()))
    except (ValueError, ZeroDivisionError): return {'name':line,'quantity':None,'unit':None}
    tail=m[2]; first, _, rest=tail.partition(' ')
    if first.casefold() in UNITS: return {'name':rest,'quantity':qty,'unit':UNITS[first.casefold()]}
    return {'name':tail,'quantity':qty,'unit':'units'}


def alias_index(dictionary):
    index={}
    for key, spec in dictionary.items():
        for alias in [spec['name'], *spec.get('aliases', [])]:
            n=norm(alias)
            if n in index and index[n] != key: raise ValueError(f'Ambiguous alias: {alias}')
            index[n]=key
    return index


ANIMAL = re.compile(r'\b(chicken|beef|pork|bacon|lard|fish|tuna|crayfish|gelatine|gelatin|rennet|shrimp|anchov\w*)\b', re.I)
DAIRY_EGG = re.compile(r'\b(milk|cream|butter|ghee|cheese|eggs?|yolks?|honey|yoghurt|yogurt|kefir|parmesan|feta)\b', re.I)


def normalize(record, dictionary, source):
    index=alias_index(dictionary); issues=[]; ingredients=[]; pantry=[]
    if not record.get('servings'): issues.append('Missing or ambiguous servings')
    if not record.get('prep_minutes'): issues.append('Missing total time')
    if not record.get('instructions'): issues.append('Missing instructions')
    if not record.get('raw_ingredients'): issues.append('Missing ingredients')
    tags=record.get('tags', [])
    if not set(tags)&{'vegan','vegetarian'}: issues.append('Diet not established')
    for raw in record.get('raw_ingredients', []):
        name=raw['name']; key=index.get(norm(name)); spec=dictionary.get(key,{})
        if norm(name) in {'chickpeas', 'red beans', 'black beans', 'white beans', 'red kidney beans'}:
            issues.append(f'Dry/cooked state needs review: {name}')
        if ANIMAL.search(name): issues.append(f'Diet conflict: {name}')
        elif 'vegan' in tags and DAIRY_EGG.search(name) and not spec.get('vegan', False):
            issues.append(f'Check vegan claim: {name}')
        if not key:
            issues.append(f'Unmapped ingredient: {name}'); continue
        if spec.get('pantry'):
            pantry.append(raw); continue
        qty=raw.get('quantity'); unit=UNITS.get(raw.get('unit'),raw.get('unit'))
        if not isinstance(qty,(int,float)) or isinstance(qty,bool) or not math.isfinite(qty) or qty<=0 or unit not in set(UNITS.values()):
            issues.append(f'Unresolved quantity/unit: {name}');continue
        if unit == 'kg': qty*=1000;unit='g'
        if unit == 'l': qty*=1000;unit='ml'
        ingredients.append({'ingredient':key,'quantity':qty,'unit':unit,'note':raw.get('note')})
    if not ingredients: issues.append('No priced ingredients')
    if 'vegan' in tags and 'vegetarian' not in tags: tags=[*tags,'vegetarian']
    identity=source['url']+'#'+record.get('source_id',record['name'])
    signature=json.dumps(sorted((norm(r['name']),str(r.get('quantity')),str(r.get('unit'))) for r in record.get('raw_ingredients',[])))
    fingerprint=hashlib.sha256((norm(record['name'])+signature).encode()).hexdigest()
    return {**record,'id':'import_'+hashlib.sha256(identity.encode()).hexdigest()[:16],
            'tags':tags,'ingredients':ingredients,'pantry':pantry,'source':source,
            'fingerprint':fingerprint,'status':'needs_review' if issues else 'ready',
            'review_issues':sorted(set(issues))}


def from_schema(node):
    diets=node.get('suitableForDiet',[])
    if isinstance(diets,str): diets=[diets]
    tags=[]
    if any(str(d).endswith('VeganDiet') for d in diets): tags=['vegan','vegetarian']
    elif any(str(d).endswith('VegetarianDiet') for d in diets): tags=['vegetarian']
    total=minutes(node.get('totalTime'))
    if total is None:
        prep,cook=minutes(node.get('prepTime')),minutes(node.get('cookTime'))
        if prep is not None and cook is not None: total=prep+cook
    raw=node.get('recipeIngredient',[])
    if not isinstance(raw,list): raw=[raw]
    category=str(node.get('recipeCategory','')).casefold()
    category={'main course':'main','dinner':'main','lunch':'main','soups':'soup'}.get(category,category)
    return {'name':str(node.get('name','Untitled recipe')),'source_id':str(node.get('@id') or node.get('name','')),
            'servings':servings(node.get('recipeYield')),'prep_minutes':total,
            'category':category,'tags':tags,'instructions':steps(node.get('recipeInstructions')),
            'raw_ingredients':[parse_line(line) for line in raw]}


def save_batch(records, out):
    out.mkdir(parents=True,exist_ok=True)
    seen_ids=set();seen_fingerprints=set();added=0;duplicates=0
    for p in out.glob('*.json'):
        for r in json.loads(p.read_text()).get('recipes',[]):
            seen_ids.add(r['id']);seen_fingerprints.add(r['fingerprint'])
    for r in records:
        if r['id'] in seen_ids or r['fingerprint'] in seen_fingerprints:
            duplicates+=1;continue
        seen_ids.add(r['id']);seen_fingerprints.add(r['fingerprint'])
        (out/(r['id']+'.json')).write_text(json.dumps({'recipes':[r]},ensure_ascii=False,indent=2)+'\n')
        added+=1
    return {'added':added,'duplicates':duplicates}


def revalidate(out, dictionary):
    counts={'ready':0,'needs_review':0}
    for path in sorted(out.glob('*.json')):
        doc=json.loads(path.read_text())
        doc['recipes']=[normalize(r,dictionary,r['source']) for r in doc['recipes']]
        for r in doc['recipes']: counts[r['status']]+=1
        path.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
    return counts


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--file',type=Path,help='Saved HTML or JSON; avoids a network request')
    p.add_argument('--revalidate',action='store_true',help='Recheck the existing bank after dictionary edits')
    p.add_argument('--url',help='Source URL, also fetched when --file is absent')
    p.add_argument('--license',help='Verified content license or permission reference')
    p.add_argument('--attribution')
    p.add_argument('--dictionary',type=Path,default=Path('config/ingredients.yml'))
    p.add_argument('--output',type=Path,default=Path('data/recipes'))
    args=p.parse_args()
    dictionary=load_yaml(args.dictionary)['ingredients']
    if args.revalidate:
        print(json.dumps(revalidate(args.output,dictionary))); return
    if not all([args.url,args.license,args.attribution]):
        p.error('--url, --license and --attribution are required for import')
    url=canonical_url(args.url)
    if args.file: text=args.file.read_text()
    else:
        request=Request(url,headers={'User-Agent':'LittleShop recipe importer (single requested URL)'})
        with urlopen(request,timeout=30) as response:
            payload=response.read(5_000_001)
            if len(payload)>5_000_000: raise ValueError('Recipe page exceeds 5 MB')
            text=payload.decode('utf-8')
    nodes=extract(text)
    if not nodes: raise SystemExit('No supported Recipe JSON-LD found; no files changed')
    dictionary=load_yaml(args.dictionary)['ingredients']
    source={'url':url,'license':args.license,'attribution':args.attribution,
            'retrieved_at':datetime.now(timezone.utc).isoformat()}
    records=[normalize(from_schema(node),dictionary,source) for node in nodes]
    print(json.dumps(save_batch(records,args.output)))
    print(f'Ready: {sum(r["status"]=="ready" for r in records)}; review: {sum(r["status"]!="ready" for r in records)}')


if __name__=='__main__': main()
