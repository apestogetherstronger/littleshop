from __future__ import annotations
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo
import re
from . import hebrew as he
from .shopping import SHOP_URLS, product_link


def _money(value):
    return f"₪{value:.2f}" if isinstance(value,(int,float)) else "—"


def _qty(value):
    return str(int(value)) if isinstance(value,float) and value.is_integer() else str(value)


def _promo_price(deal):
    """Only a validated simple offer can supply an unconditional unit price."""
    regular = deal.get('regular_price')
    if not deal.get('simple_unit_promotion') or not isinstance(regular, (int, float)):
        return None
    discounted, rate = deal.get('discounted_price'), deal.get('discount_rate')
    if isinstance(discounted, (int, float)) and 0 < discounted < regular:
        return discounted
    if isinstance(rate, (int, float)) and 0 < rate < 100:
        return regular * (1 - rate / 100)
    return None



def _promo_label(deal):
    price=_promo_price(deal)
    if price is not None:
        return f"מחיר במבצע ליחידה: **{_money(price)}**"
    amount,minimum=deal.get('discounted_price'),deal.get('min_qty')
    if isinstance(amount,(int,float)) and amount>0:
        if isinstance(minimum,(int,float)) and minimum>1:
            match=re.search(r'(?<![\d.])(\d+)\s*ב\s*(\d+(?:\.\d+)?)(?![\d.])',deal.get('promotion_description') or '')
            if match and int(match[1])==minimum and abs(float(match[2])-amount)<0.005:
                return f"מבצע כמות: **{minimum:g} יחידות ב־{_money(amount)} בסך הכול** ({_money(amount/minimum)} ליחידה בקניית {minimum:g}; בכפוף לתנאים)"
            return f"סכום המבצע שדווח: **{_money(amount)}** · מינימום {minimum:g} יחידות — לא מחיר מאומת ליחידה"
        return f"מחיר מבצע שפורסם: **{_money(amount)}** — מותנה; הזכאות לא אומתה"
    return 'מבצע מותנה או מבצע כמות — אין מחיר מאומת ליחידה'


def render_report(plan,chain_runs,errors):
    lines=['<div dir="rtl">','','# ליטלשופ — תפריט שבועי ורשימת קניות','',
           f"הדוח נוצר: {datetime.now(ZoneInfo('Asia/Jerusalem')).strftime('%d.%m.%Y %H:%M')} (שעון ישראל)",'',
           f"כיסוי נתונים: **{len(chain_runs)} רשתות נטענו, {len(errors)} נכשלו**.",'']
    if errors:lines+=['התוכנית מבוססת רק על הרשתות שנטענו בהצלחה.','']
    if chain_runs and not any(r['deals'] for r in chain_runs):
        lines+=['לא נמצאו מבצעים ציבוריים פעילים; בחירת המנות אינה מבוססת על מבצעים.','']
    lines+=['הדירוג מעדיף מנות שאפשר לתמחר. לאחר מכן נבחנים המבצעים, עם הפחתת נקודה לכל 15 דקות מעבר לשעה. עלות המשלוח נספרת פעם אחת לכל חנות. מחירי הסניפים עשויים להיות שונים ממחירי האתר.','']
    if plan.get('feed_generated_at'):
        lines += [f"מועד משיכת נתוני המחירים: {plan['feed_generated_at']}. ייתכן שהדוח חושב מחדש מאותם נתונים.",'']
    lines+=['## חנויות ומקורות המחירים','']
    kinds={'Stores':'רשימת סניפים','PriceFull':'מחירון מלא','PromoFull':'קובץ מבצעים מלא'}
    for run in chain_runs:
        st=run['store'];address=', '.join(v for v in [st.get('city'),st.get('address')] if v)
        lines += [f"- **{he.shop(run['chain'])}** — {st.get('name') or 'סניף ללא שם'} (סניף {st['store_id']})  ",f"  {address}"]
        for kind,source in run.get('source_files',{}).items():
            lines += [f"  - {kinds.get(kind,kind)}: {source.get('published_at') or 'מועד לא ידוע'} (שעון ישראל)"]
            if source.get('xml_store_id') and source['xml_store_id'].lstrip('0')!=str(st['store_id']).lstrip('0'):
                lines += [f"  - מזהה סניף היסטורי בקובץ: {source['xml_store_id']}; מזהה בקטלוג: {st['store_id']}."]
    if not chain_runs:lines+=['לא נטענו נתוני רשתות.']
    if errors:
        lines+=['','### תקלות בטעינת הנתונים','']
        lines += [f'- <span dir="ltr">{escape(e)}</span>' for e in errors]
    lines += ['','## התפריט השבועי','']
    lines += [f"- [יום {day}: {he.recipe(meal['name'])}](#recipe-day-{day})" for day,meal in enumerate(plan['meals'],1)]
    lines += ['']
    for day,meal in enumerate(plan['meals'],1):
        lines += [f'<a id="recipe-day-{day}"></a>',f"### יום {day}: {he.recipe(meal['name'])} ({meal.get('prep_minutes','?')} דקות)",'']
        tags=meal.get('tags',[])
        lines += [('טבעוני' if 'vegan' in tags else 'צמחוני' if 'vegetarian' in tags else '')+
                  (f" · מספר מנות במתכון: {_qty(meal['servings'])}" if meal.get('servings') else ''),'']
        if meal.get('source'):
            source=meal['source']
            lines += [f"מקור: {escape(source['attribution'])} · רישיון: {escape(source['license'])}  ",
                      f"[למקור]({source['url']}) · [המתכון המלא והוראות ההכנה במקור באנגלית](../data/recipes/{meal['id']}.json)",'']
        if meal.get('instructions_he'):
            lines+=['**אופן ההכנה:**','']+[f'{n}. {escape(step)}' for n,step in enumerate(meal['instructions_he'],1)]+['']
        elif meal.get('instructions'):
            lines+=['**אופן ההכנה — נוסח המקור באנגלית:**','','<div dir="ltr">','']
            lines+=[f'{n}. {escape(step)}' for n,step in enumerate(meal['instructions'],1)]
            lines+=['','</div>','']
        else:
            lines+=['הוראות הכנה עדיין חסרות למנה זו.','']
        if meal.get('pantry_note_he'):
            lines += [meal['pantry_note_he'],'']
        if meal.get('pantry'):
            lines+=['בדיקה במזווה — לא נכלל במחיר הסל: '+ '; '.join(he.ingredient(i['name']) for i in meal['pantry']), '']
        lines += [f"ציון מבצעים: **{meal['deal_score']}**" ]
        if meal.get('time_penalty'):
            lines += [f"הפחתה עקב זמן הכנה: {meal['time_penalty']:.2f} · ציון לאחר ההפחתה: {meal['ranking_score']:.2f}"]
        lines+=['','מצרכים:','']
        lines += [f"- {he.ingredient(i['name'])}: {_qty(i.get('quantity',0))} {he.unit(i.get('unit',''))}" for i in meal.get('ingredients',[])]
        lines+=['']
        if meal.get('matched_deals'):
            lines+=['**מבצעים שנמצאו — אלה אינם בהכרח המוצרים בהזמנה המומלצת.**','',
                    'ברשימת הקניות בהמשך מוצגים המוצרים והמחירים שנבחרו בפועל לחישוב.','']
            for match in meal['matched_deals']:
                d=match['deal']
                lines += [f"- **{he.ingredient(match['ingredient'])}**  ",
                          f"  {escape(str(d.get('name') or d.get('item_code') or 'מוצר ללא שם'))}  ",
                          f"  חנות: {he.shop(d['chain'])}  ",f"  מחיר רגיל שפורסם: **{_money(d.get('regular_price'))}**  ",
                          f"  {_promo_label(d)}  ",'  תנאי המבצע:  ',f"  {escape(d.get('promotion_description') or 'לא צוינו')}",'']
        else:lines+=['לא נמצא מבצע מתאים למצרכי המנה.','']
    lines+=render_shopping(plan)
    lines+=['','## דירוג המנות','', '| מנה | ציון דירוג | הפחתת זמן | מצרכים במבצע | זמן הכנה |','|---|---:|---:|---:|---:|']
    for r in plan['ranked_recipes']:
        lines += [f"| {he.recipe(r['name'])} | {r.get('ranking_score',r['deal_score'])} | {r.get('time_penalty',0)} | {len(r.get('matched_deals',[]))} | {r.get('prep_minutes','?')} דקות |"]
    lines+=['','## איך לקרוא את האומדן','',
            '- החישוב מעגל כלפי מעלה לאריזות שלמות. מבצעי כמות ומבצעים שתנאיהם אינם חד־משמעיים אינם מופחתים ממחיר הסל.',
            '- מצרכים ללא מחיר אינם נחשבים חינם. פריטי מזווה אינם כלולים באומדן. יש לבדוק משקל מסונן בשימורים.',
            '- התאמת המוצרים מבוססת על שמות וכללים; יש לאמת את המוצר, הכמות והמחיר באתר החנות.',
            '- הסימון צמחוני או טבעוני מתייחס למתכון. אין בדיקה אוטומטית של כשרות, אלרגנים או הרכב כל מוצר.','','</div>']
    return '\n'.join(lines)


def render_shopping(plan):
    lines=['## רשימת קניות לפי חנות','','🍽️ מעבר למתכון · 🛒 מעבר למוצר, לחיפוש או לאתר החנות','']
    strategy=plan.get('shopping_strategy')
    if strategy:
        rec=strategy.get('recommendation')
        if rec:
            lines+=['### ההזמנה המומלצת','',
                    f"**{' + '.join(he.shop(s) for s in rec['shops'])}: {_money(rec['partial_total_cents']/100)} כולל המשלוח שהוגדר**",'',
                    f"תומחרו **{len(rec['assignments'])} מתוך {strategy['total_items']} שורות מצרכים**.  ",
                    f"מוצרים: {_money(rec['items_cents']/100)} · משלוח: {_money(sum(rec['delivery_cents'].values())/100)}",'',
                    'זהו אומדן לפריטים המפורטים, ולא מחיר סופי מאומת בקופה.','']
            if strategy.get('remaining_items'):
                lines += ['נדרש להשלים בנפרד: '+', '.join(he.ingredient(n) for n in strategy['remaining_items'])+'.','']
        lines+=['### השוואת עלויות כולל משלוח','',
                f"כיסוי מחירים: **{strategy['priceable_items']} מתוך {strategy['total_items']} שורות מצרכים**. סכומים בני השוואה מכסים אותם מצרכים.",'',
                'ציון החיסכון הוא ההפרש לעומת האפשרות הזולה בחנות אחת עם אותו כיסוי. ערך חיובי מציין חיסכון.','',
                '| אפשרות | מוצרים | משלוח | סך הכול | חיסכון | מצב |','|---|---:|---:|---:|---:|---|']
        for o in strategy['alternatives']:
            status=[]
            if o['missing_items']:status += [f"חסר מחיר ל־{len(o['missing_items'])} שורות; לא ניתן להשוות"]
            if o['unknown_delivery']:status+=['דמי המשלוח אינם ידועים']
            if o['minimum_shortfalls_cents']:
                status+=['מתחת למינימום: '+', '.join(f"{he.shop(s)} — חסרים {_money(v/100)}" for s,v in o['minimum_shortfalls_cents'].items())]
            if o==strategy['best']:status.insert(0,'האומדן הזול ביותר שנבדק' if o['eligible'] else 'המינימום להזמנה לא הושג')
            fee=None if o['unknown_delivery'] else sum(o['delivery_cents'].values())/100
            lines += [f"| {' + '.join(he.shop(s) for s in o['shops'])} | {_money(o['items_cents']/100)} | {_money(fee)} | {_money(o['total_cents']/100 if o['total_cents'] is not None else None)} | {_money(o['delivery_adjusted_deal_score_ils'])} | {'; '.join(status) or 'אומדן'} |"]
        lines+=['','ההשוואה כוללת קנייה בחנות אחת ופיצול בין חנויות. היא אינה מחשבת את כל שילובי מבצעי הכמות.','']
        if not strategy['best']:lines+=['אין השוואה מלאה של כל הסל. ההמלצה לעיל, אם קיימת, מתייחסת רק לפריטים המפורטים.','']
        for s,p in strategy['policies'].items():
            if s not in {s for o in strategy['alternatives'] for s in o['shops']}:continue
            label='לא ידוע — יש לבדוק בקופה' if p.get('fee_ils') is None else 'תעריף שפורסם' if p.get('fee_status')=='published' else 'הנחה לצורך החישוב — יש לאמת בקופה'
            minimum=f"מינימום הזמנה: {_money(p['minimum_order_ils'])}" if p.get('minimum_order_ils') is not None else 'מינימום ההזמנה לא אומת'
            url=p.get('source_url') or SHOP_URLS.get(s)
            lines += [f"- **{he.shop(s)}**: משלוח {_money(p.get('fee_ils'))} ({label}); {minimum}."+(f" [פרטי משלוח]({url})" if url else '')]
        lines+=['','יש לבדוק באתר הטבות אישיות, זמינות מוצרים, מועדי משלוח והמחיר הסופי.','']
    else:lines+=['לא ניתן להשוות משלוחים ללא נתוני מוצרים ואריזות או הגדרות משלוח.','']
    for s,items in plan.get('shopping_by_shop',{}).items():
        lines += [('### מצרכים שדורשים בדיקת מחיר או חנות' if s=='unassigned' else f"### {he.shop(s)}"),'']
        if s=='unassigned':lines+=['אינם כלולים באומדן.','']
        elif SHOP_URLS.get(s):lines += [f"[🛒 פתיחת אתר החנות]({SHOP_URLS[s]})",'']
        rec=strategy.get('recommendation') if strategy else None
        if rec and s in rec['subtotals_cents']:
            lines += [f"מוצרים: {_money(rec['subtotals_cents'][s]/100)} · משלוח: {_money(rec['delivery_cents'][s]/100)}",'']
        for item in items:
            lines += [f"- [ ] **{he.ingredient(item['name'])}** — {_qty(item['quantity'])} {he.unit(item['unit'])}  "]
            q=item.get('quote');d=item.get('suggested_deal');url=None
            if q:
                p=q['product'];promo=_promo_price(q.get('promotion') or {})
                if q['packages'] is None:
                    purchase=f"{_qty(item['quantity'])} {he.unit(item['unit'])} לפי משקל"
                else:
                    purchase=q['purchase'].replace('pack(s)','אריזות').replace('units','יחידות')
                basis='ליחידת המשקל במחירון' if p.get('is_weighted') else 'לאריזה'
                lines += [f"  {escape(p['name'])}  ",f"  כמות לקנייה: {purchase}  ",f"  מחיר רגיל {basis}: **{_money(p.get('regular_price'))}**  "]
                lines += [f"  מחיר מבצע {basis} ששימש בחישוב: **{_money(promo)}**  " if promo is not None else '  מבצע שהוחל: **ללא — החישוב לפי המחיר הרגיל**  ']
                lines += [f"  **סך השורה: {_money(q['cost_cents']/100)}** לכל הכמות המפורטת  "]
                if q.get('metadata_note'):lines += ['  יחידת האריזה נלקחה מהכיתוב המפורש בשם המוצר, עקב סתירה בנתוני הקטלוג.  ']
                url=q['url']
            elif d:
                lines += [f"  {escape(str(d.get('name') or d.get('item_code')))}  "]
                url=product_link(d)
            reason=item.get('check_reason')
            if reason:
                msg=('לא נמצא מוצר מתאים בקטלוגים שנטענו' if reason.startswith('No matching') else
                     'פריט שתומחר בנפרד; יש לבדוק משלוח ומינימום הזמנה' if item.get('order_status')=='conditional' else
                     'נמצא מוצר, אך הכמות או יחידות האריזה אינן מאפשרות תמחור אמין')
                lines += [f'  {msg}  ']
            links=[]
            if url:links+=[f'[🛒 למוצר או לחנות]({url})']
            for r in item.get('recipes',[]):
                title=f"יום {r['day']}: {he.recipe(r['name'])}".replace('"',"'")
                links += [f'[🍽️{r["day"]}](#{r["anchor"]} "{title}")']
            lines+=['  '+' · '.join(links),'']
    return lines
