import json
from pathlib import Path
import subprocess

from littleshop.interactive import bundle_terms, purchase_options, render_html


def item(quantity=500):
    return dict(name='rice',quantity=quantity,unit='g',search_terms=['rice'])


def product(price=10):
    return dict(chain='a',name='rice',regular_price=price,pack_quantity=500,pack_unit='g',is_weighted=False)


def offer(desc='1+1', **kwargs):
    return dict(promotion_description=desc,bundle_eligible=True,min_qty=2,**kwargs)


def test_bogo_cost_and_leftovers_are_separate():
    options=purchase_options(item(),product(),[offer()])
    extra=next(o for o in options if o['extra'])
    assert (extra['cost'],extra['used'],extra['purchased']) == (1000,500,1000)
    assert next(o for o in options if not o['extra'])['cost']==1000


def test_bundle_remainder_and_round_up():
    options=purchase_options(item(1500),product(),[offer('2ב15.90',discounted_price=15.90)])
    assert any(o['packs']==3 and o['cost']==2590 and not o['extra'] for o in options)
    assert any(o['packs']==4 and o['cost']==3180 and o['used']==2385 and o['extra'] for o in options)


def test_unknown_restrictions_and_conflicting_bundle_prices_are_rejected():
    assert bundle_terms(dict(promotion_description='1+1'),10) is None
    assert bundle_terms(offer('2ב15.90',discounted_price=7.95),10) is None
    assert bundle_terms(offer('1+1 הזול מביניהם'),10) is None
    assert bundle_terms(dict(offer(),bundle_eligible=False),10) is None


def test_simple_discount_is_not_stacked_with_bundle():
    simple=dict(simple_unit_promotion=True,discounted_price=4,promotion_description='discount')
    opts=purchase_options(item(),product(),[simple,offer()])
    assert min(o['cost'] for o in opts)==400
    assert next(o for o in opts if o['extra'])['cost']==1000


def test_weighted_item_has_no_extra_packs():
    p=dict(product(),is_weighted=True,unit_of_measure='100 גרם',unit_price=2)
    opts=purchase_options(item(),p,[offer()])
    assert len(opts)==1 and opts[0]['purchased']==500 and opts[0]['cost']==1000


def test_html_escapes_feed_and_retains_recipe_instructions():
    plan=dict(shopping_list=[],meals=[dict(name='x',instructions=['<script>bad()</script>'],ingredients=[])])
    html=render_html(plan,[],[])
    assert '<html lang="he" dir="rtl">' in html
    assert '&lt;script&gt;bad()&lt;/script&gt;' in html
    assert 'id="recipe-day-1"' in html


def test_browser_optimizer_per_item_choices_delivery_and_incomplete_data():
    script=Path(__file__).resolve().parents[1]/'src/littleshop/interactive.js'
    js=r'''
const {compare}=require(process.argv[1]);
const assert=require('node:assert/strict');
const a={shop:'a',cost:1000,used:1000,extra:false};
const bonus={shop:'a',cost:1000,used:500,extra:true};
const b={shop:'b',cost:700,used:700,extra:false};
const data={policies:{a:{fee_ils:0},b:{fee_ils:0}},rows:[{options:[a,bonus,b]},{options:[a,bonus,b]}]};
assert.equal(compare(data,[false,false]).total,1400);
let r=compare(data,[true,false]);
assert.equal(r.rows[0].extra,true);
assert.equal(r.rows[1].extra,false);
assert.equal(r.total,1700); assert.equal(r.used,1200);
bonus.conditional=true;
assert.equal(compare(data,[true,false]).total,1400);
assert.equal(compare(data,[true,false],[true,false]).total,1700);
bonus.conditional=false;
data.policies.a.fee_ils=10;
assert.equal(compare(data,[true,false]).total,1400);
data.policies.b.fee_ils=null;
assert.equal(compare(data,[false,false]).total,3000);
data.policies.a.minimum_order_ils=100;
assert.equal(compare(data,[false,false]),null);
data.policies.a.minimum_order_ils=0;
data.rows.push({options:[]});
assert.equal(compare(data,[false,false,false]),null);
'''
    subprocess.run(['node','-e',js,str(script)],check=True,capture_output=True,text=True)
