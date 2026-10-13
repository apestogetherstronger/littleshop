"""Self-contained RTL shopping report. Bundle estimates never stack promotions."""
import json
import re
from html import escape
from pathlib import Path
from . import hebrew as he
from .planner import matches_ingredient
from .shopping import quote_item, cents


def bundle_terms(deal, regular):
    """Only explicit same-SKU public bundles with preserved eligibility metadata."""
    if not (deal.get('bundle_eligible') or deal.get('bundle_candidate')):
        return None
    desc = deal.get('promotion_description') or ''
    # Exclude asymmetric/cross-product offers rather than inferring eligibility.
    if any(t in desc for t in ('השני', 'הזול', 'שונים', 'שונות', 'מותנה', 'מעל')):
        return None
    if re.search(r'(?<!\d)1\s*\+\s*1(?!\d)', desc):
        if deal.get('min_qty') not in (None, 1, 2):
            return None
        return 2, cents(regular)
    m = re.search(r'(?<!\d)(\d+)\s*ב\s*[-־]?\s*(\d+(?:\.\d+)?)(?!\d)', desc)
    if m:
        n, price = int(m[1]), float(m[2])
        if n >= 2 and deal.get('min_qty') == n and deal.get('discounted_price') is not None and abs(deal['discounted_price']-price) < .01 and 0 < price < n*regular:
            return n, cents(price)
    return None


def purchase_options(item, product, deals):
    q = quote_item(item, product, deals)
    if not q:
        return []
    needed, purchased = q['needed_base'], q['purchased_base']
    base = dict(shop=product['chain'], name=product['name'], url=q['url'],
                needed=needed, purchased=purchased, dimension=q['base_dimension'],
                packs=q['packages'], extra=False, cost=q['cost_cents'],
                used=round(q['cost_cents']*needed/purchased),
                promo=(q['promotion'] or {}).get('promotion_description') or 'מחיר רגיל',
                regular=product['regular_price'], conditional=False)
    options = [base]
    if q['packages'] is None:
        return options
    required, size = q['packages'], q['pack_size_base']
    regular = cents(product['regular_price'])
    for deal in deals:
        terms = bundle_terms(deal, product['regular_price'])
        if not terms:
            continue
        n, price = terms
        # Exact needed packs, plus at most one rounded-up bundle.
        for packs in sorted({required, ((required+n-1)//n)*n}):
            bundles, remainder = divmod(packs, n)
            if not bundles:
                continue
            cost = bundles*price + remainder*regular
            options.append(dict(base, packs=packs, purchased=packs*size,
                                extra=packs>required, cost=cost,
                                used=round(cost*needed/(packs*size)),
                                promo=deal['promotion_description'], conditional=not deal.get('bundle_eligible',False)))
    return options


def report_data(plan, products, deals):
    promo_index = {}
    for d in deals:
        promo_index.setdefault((d['chain'], d.get('store_id'), d.get('item_code')), []).append(d)
    rows = []
    for item in plan['shopping_list']:
        options = []
        for p in products:
            if matches_ingredient(item, p):
                options.extend(purchase_options(item, p, promo_index.get((p['chain'],p.get('store_id'),p.get('item_code')), [])))
        # Only two choices per shop can win either item preference.
        winners = []
        for shop in sorted({o['shop'] for o in options}):
            for extra in (False, True):
                for confirmed in (False, True):
                    pool = [o for o in options if o['shop']==shop and (extra or not o['extra'])
                            and (confirmed or not o['conditional'])]
                    if pool:
                        winner = min(pool, key=lambda o: ((o['used'] if extra else o['cost']),o['cost'],o['name']))
                        if winner not in winners:
                            winners.append(winner)
        rows.append(dict(name=he.ingredient(item['name']), quantity=f"{item['quantity']:g} {he.unit(item['unit'])}",
                         recipes=item.get('recipes',[]), options=winners))
    policies = (plan.get('shopping_strategy') or {}).get('policies', {})
    return dict(rows=rows, policies=policies, shops={s:he.shop(s) for s in policies})


def safe_url(value):
    return escape(value if str(value).startswith(('https://','http://')) else '#', quote=True)


def render_html(plan, products, deals, errors=()):
    data = json.dumps(report_data(plan, products, deals), ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&','\\u0026')
    recipes = []
    index = []
    for day,m in enumerate(plan['meals'],1):
        title = escape(he.recipe(m['name']))
        index.append(f'<a href="#recipe-day-{day}">יום {day}: {title}</a>')
        steps = m.get('instructions_he') or m.get('instructions') or []
        method = ''.join(f'<li>{escape(step)}</li>' for step in steps)
        ingredients = ''.join(f'<li>{escape(he.ingredient(i["name"]))}: {i.get("quantity",0):g} {escape(he.unit(i.get("unit","")))}</li>' for i in m.get('ingredients',[]))
        source = m.get('source')
        attribution = f'<p><a href="{safe_url(source["url"])}">למתכון המקורי</a> · {escape(source["attribution"])} · {escape(source["license"])}</p>' if source else ''
        recipes.append(f'<article id="recipe-day-{day}"><h3>יום {day}: {title}</h3><p>{m.get("prep_minutes","?")} דקות · {m.get("servings","?")} מנות</p><ul>{ingredients}</ul><ol dir="{"rtl" if m.get("instructions_he") else "ltr"}">{method}</ol>{attribution}<p>{escape(m.get("pantry_note_he", ""))}</p><a href="#shopping">חזרה לקניות</a></article>')
    script = Path(__file__).with_name('interactive.js').read_text()
    return '''<!doctype html><html lang="he" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ליטלשופ — קניות ומתכונים</title>
<style>body{font:17px system-ui,sans-serif;background:#f4f7f5;color:#182c26;margin:0}main{max-width:1050px;margin:auto;padding:24px}h1{font-size:2rem}article,.panel{background:white;border:1px solid #d6e3dc;border-radius:14px;padding:20px;margin:16px 0}a{color:#006852}button,select,input{font:inherit}select,button{padding:10px;border-radius:8px;border:1px solid #9cafaa;background:white}label{display:block;margin:12px 0}input{width:90px;padding:6px}input[type=checkbox]{width:auto}.warn{overflow-wrap:anywhere}nav{display:flex;flex-wrap:wrap;gap:12px}small,.muted{color:#51665e}.metrics{display:flex;flex-wrap:wrap;gap:24px}.metrics strong{display:block;font-size:1.6rem}.warn{color:#843d08}li{margin:8px 0}#summary{border:2px solid #238068}article:target{outline:3px solid #c19734}p{line-height:1.7}.line{margin:7px 0}bdi{unicode-bidi:isolate}@media(max-width:600px){main{padding:12px}.metrics{gap:14px}select{max-width:100%}}@media print{select,button{display:none}}</style>
<main><h1>ליטלשופ — קניות ומתכונים</h1><p>בחרו לכל מצרך אם לקנות רק את הכמות הדרושה או לאפשר אריזות נוספות. התשלום בקופה תמיד כולל את כל האריזות; העלות לשימוש במתכונים מחלקת את המחיר לפי הכמות שנצרכת.</p>''' + f'<p class="muted">מועד נתוני המחירים: <bdi>{escape(plan.get("feed_generated_at","לא ידוע"))}</bdi>. מחירי הסניף עשויים להיות שונים באתר.</p>' + (f'<p class="warn">כיסוי חלקי: {escape(chr(59).join(errors))}</p>' if errors else '') + '''<details class="panel"><summary>משלוח ומינימום הזמנה — לבדיקה לפני הזמנה</summary><p>ערכי משלוח משוערים דורשים אישור בקופה. שדה ריק אינו אפס. חנות ללא דמי משלוח ידועים לא נכללת בהמלצה; מינימום לא ידוע מסומן לבדיקה.</p><div id="delivery"></div></details>
<section id="summary" class="panel" aria-live="polite"></section><button id="reset">איפוס בחירות</button><h2 id="shopping">רשימת קניות — בחירה לכל מצרך</h2><div id="items"></div><h2>מתכונים והוראות הכנה</h2><nav>''' + ''.join(index) + '</nav>' + ''.join(recipes) + '''<p class="muted">ההשוואה בוחנת חנות אחת ופיצולים בין חנויות. בכל שילוב נבחרת החלופה הזולה לכל מצרך לפי הבחירה שלו; זהו אומדן ולא חיפוש ממצה של כל הסלים שעשויים לעמוד במינימום. מבצעים עם תנאי קבוצה לא פתורים מחושבים רק אחרי אישורכם לכל פריט כי המבצע חל על אריזות זהות ובכמות שנבחרה. תנאים אחרים שאינם נתמכים אינם מחושבים. המבצעים הנתמכים הם אריזות זהות; אין שילוב מבצעים או חישוב מבצעים מעורבים בין שורות. מלאי ותוקף המבצע מחייבים בדיקה באתר. המזווה אינו כלול.</p></main><script id="data" type="application/json">''' + data + '</script><script>' + script + '</script></html>'
