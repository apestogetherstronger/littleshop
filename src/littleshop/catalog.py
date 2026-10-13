"""Resolve shared ingredient definitions and load only validated imported meals."""
from copy import deepcopy
import json
from pathlib import Path
from .config import load_yaml


def resolve_recipe(recipe, ingredients):
    result = deepcopy(recipe)
    result['ingredients'] = []
    for item in recipe.get('ingredients', []):
        if 'ingredient' in item:
            key = item['ingredient']
            if key not in ingredients:
                raise ValueError(f'Unknown ingredient: {key}')
            spec = ingredients[key]
            result['ingredients'].append({
                **{k: deepcopy(v) for k, v in spec.items() if k != 'aliases'},
                **item,
            })
        else:  # Legacy inline catalogs are still supported.
            result['ingredients'].append(deepcopy(item))
    return result


def load_catalog(root: Path):
    path = root / 'config/ingredients.yml'
    ingredients = load_yaml(path).get('ingredients', {}) if path.exists() else {}
    recipes = load_yaml(root / 'config/recipes.yml').get('recipes', [])
    for path in sorted((root / 'data/recipes').glob('*.json')):
        for recipe in json.loads(path.read_text())['recipes']:
            if recipe.get('status') == 'ready' and recipe.get('category') in {'main', 'soup'}:
                recipes.append(recipe)
    ids = [r['id'] for r in recipes]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate recipe IDs in catalog')
    return [resolve_recipe(r, ingredients) for r in recipes]
