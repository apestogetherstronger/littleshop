import json
from pathlib import Path
import pytest
from littleshop.recipe_import import (extract, from_schema, normalize, parse_line,
                                     save_batch, canonical_url, alias_index)
from littleshop.catalog import load_catalog
from littleshop.config import load_yaml

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def dictionary():
    return load_yaml(ROOT/'config/ingredients.yml')['ingredients']


def node(**changes):
    return {'@type':['Thing','Recipe'],'name':'Rice bowl','recipeYield':'4 servings',
            'totalTime':'PT30M','recipeCategory':'main course',
            'suitableForDiet':'https://schema.org/VeganDiet',
            'recipeIngredient':['400 g rice','200 g spinach'],
            'recipeInstructions':[{'@type':'HowToSection','itemListElement':[{'@type':'HowToStep','text':'Cook rice.'}]}],**changes}


def imported(dictionary,**changes):
    return normalize(from_schema(node(**changes)),dictionary,{'url':'https://example.com/rice','license':'CC0','attribution':'Example'})


def test_graph_and_array_jsonld():
    text='<script type="application/ld+json">'+json.dumps({'@graph':[{'@type':'Person'},node()]})+'</script>'
    result=extract(text)
    assert len(result)==1
    assert from_schema(result[0])['instructions']==['Cook rice.']


def test_structured_ready_recipe(dictionary):
    r=imported(dictionary)
    assert r['status']=='ready'
    assert r['servings']==4 and r['prep_minutes']==30
    assert r['ingredients'][0]['ingredient']=='rice'


@pytest.mark.parametrize('line',['1-2 cups rice','1 can tomatoes','rice to taste','1 400g can tomatoes'])
def test_ambiguous_quantities_never_ready(dictionary,line):
    assert imported(dictionary,recipeIngredient=[line])['status']=='needs_review'


def test_mixed_and_unicode_fractions():
    assert parse_line('1 1/2 kg rice')['quantity']==1.5
    assert parse_line('½ kg rice')['quantity']==0.5


def test_diet_conflicts_override_source_claim(dictionary):
    r=imported(dictionary,recipeIngredient=['400 g rice','200 g butter'])
    assert any('vegan claim' in i for i in r['review_issues'])
    r=imported(dictionary,recipeIngredient=['400 g rice','200 g chicken'])
    assert any('Diet conflict' in i for i in r['review_issues'])


def test_missing_metadata_and_dry_cooked_ambiguity(dictionary):
    r=imported(dictionary,recipeYield='4-6 servings',recipeIngredient=['400 g chickpeas'])
    assert r['status']=='needs_review'
    assert any('Dry/cooked' in i for i in r['review_issues'])
    assert imported(dictionary,totalTime=None,prepTime='PT10M')['status']=='needs_review'


def test_duplicate_import_is_idempotent(tmp_path,dictionary):
    r=imported(dictionary)
    assert save_batch([r,r],tmp_path)=={'added':1,'duplicates':1}
    assert save_batch([r],tmp_path)=={'added':0,'duplicates':1}
    r2={**r,'id':'different_source_same_content'}
    assert save_batch([r2],tmp_path)=={'added':0,'duplicates':1}


def test_catalog_includes_only_ready_meals(dictionary):
    recipes=load_catalog(ROOT)
    assert len(recipes)>18
    for r in recipes:
        assert r['ingredients']
        if 'source' in r:
            assert r['status']=='ready' and r['category'] in {'main','soup'}
        assert all('name' in i and i['search_terms'] for i in r['ingredients'])
    assert alias_index(dictionary)


def test_pantry_is_explicit_and_does_not_become_zero_price(dictionary):
    r=imported(dictionary,recipeIngredient=['400 g rice','salt'])
    assert r['status']=='ready'
    assert r['pantry'][0]['name']=='salt'
    assert len(r['ingredients'])==1


def test_url_credentials_rejected():
    with pytest.raises(ValueError):canonical_url('https://name:password@example.com/recipe')


def test_revalidate_promotes_only_resolved_records(tmp_path,dictionary):
    from littleshop.recipe_import import revalidate
    r=imported(dictionary,recipeIngredient=['400 g test rice'])
    save_batch([r],tmp_path)
    assert revalidate(tmp_path,dictionary)['needs_review']==1
    dictionary['rice']['aliases'].append('test rice')
    assert revalidate(tmp_path,dictionary)=={'ready':1,'needs_review':0}
    saved=json.loads(next(tmp_path.glob('*.json')).read_text())['recipes'][0]
    assert saved['id']==r['id'] and saved['source']==r['source']


def test_report_retains_source_instructions_and_servings(dictionary):
    from littleshop.catalog import resolve_recipe
    from littleshop.planner import build_plan
    from littleshop.report import render_report
    r=resolve_recipe(imported(dictionary),dictionary)
    plan=build_plan([r],[],days=1,diet={'required_recipe_tags':['vegan']})
    report=render_report(plan,[],[])
    assert 'מספר מנות במתכון: 4' in report and 'הוראות ההכנה במקור באנגלית' in report
    assert '[למקור](https://example.com/rice)' in report
    assert 'CC0' in report
