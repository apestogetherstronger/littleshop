/* Pure basket calculation is shared by the browser and Node regression tests. */
function compare(data, extra, confirmed=[]) {
  const shops = Object.keys(data.policies).filter(s => data.policies[s].fee_ils != null);
  const candidates = [];
  for (let mask=1; mask<(1<<shops.length); mask++) {
    const selected=shops.filter((_,i)=>mask&(1<<i));
    const rows=data.rows.map((r,i)=>r.options.filter(o=>selected.includes(o.shop)&&(extra[i]||!o.extra)&&(confirmed[i]||!o.conditional))
      .sort((a,b)=>(extra[i]?a.used-b.used:a.cost-b.cost)||a.cost-b.cost||a.shop.localeCompare(b.shop))[0]||null);
    if (rows.some(r=>!r)) continue;
    const subtotals={}, usedShops=new Set(); let cost=0,used=0,objective=0;
    rows.forEach((r,i)=>{cost+=r.cost;used+=r.used;objective+=extra[i]?r.used:r.cost;usedShops.add(r.shop);subtotals[r.shop]=(subtotals[r.shop]||0)+r.cost;});
    if ([...usedShops].some(s=>data.policies[s].minimum_order_ils!=null && subtotals[s]<Math.round(data.policies[s].minimum_order_ils*100))) continue;
    const delivery=[...usedShops].reduce((n,s)=>n+Math.round(data.policies[s].fee_ils*100),0);
    candidates.push({rows,subtotals,shops:[...usedShops],cost,used,delivery,total:cost+delivery,objective:objective+delivery});
  }
  return candidates.sort((a,b)=>a.objective-b.objective||a.total-b.total||a.shops.length-b.shops.length)[0]||null;
}
if (typeof module!=='undefined') module.exports={compare};
if (typeof document!=='undefined') {
 const data=JSON.parse(document.getElementById('data').textContent);
 let extra=data.rows.map(()=>false);
 let confirmed=data.rows.map(()=>false);
 const original=JSON.parse(JSON.stringify(data.policies));
 const money=c=>(c/100).toLocaleString('he-IL',{style:'currency',currency:'ILS'});
 const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const link=u=>/^https?:\/\//.test(u||'')?esc(u):'#';
 const quantity=(n,dimension)=>`${Number(n.toFixed(1)).toLocaleString('he-IL')} ${{mass:'גרם',volume:'מ״ל',count:'יחידות'}[dimension]||''}`;
 function controls(){
  document.getElementById('delivery').innerHTML=Object.entries(data.policies).map(([s,p])=>`<fieldset><legend>${esc(data.shops[s])}</legend><label>דמי משלוח (₪) <input type="number" min="0" step="0.01" data-shop="${esc(s)}" data-field="fee_ils" value="${p.fee_ils??''}"></label><label>מינימום הזמנה (₪) <input type="number" min="0" step="0.01" data-shop="${esc(s)}" data-field="minimum_order_ils" value="${p.minimum_order_ils??''}"></label><small>${p.fee_status==='published'?'דמי משלוח ממקור שפורסם — לבדיקה בקופה':'דמי המשלוח משוערים או לא ידועים — יש לבדוק'}</small></fieldset>`).join('');
 }
 function render(){
  const result=compare(data,extra,confirmed);
  const mixed=extra.some(Boolean);
  document.getElementById('summary').innerHTML=result?`<h2>הסל המומלץ לפי הבחירות</h2><div class="metrics"><div>לתשלום כולל משלוח<strong>${money(result.total)}</strong></div><div>מוצרים<strong>${money(result.cost)}</strong></div><div>משלוח<strong>${money(result.delivery)}</strong></div><div>עלות הכמות שבמתכונים, ללא משלוח<strong>${money(result.used)}</strong></div></div><p>${result.shops.map(s=>`${esc(data.shops[s])}: ${money(result.subtotals[s])} מוצרים`).join(' · ')}</p><p>${mixed?'בפריטים שאושרו בהם אריזות נוספות, ההשוואה מעדיפה עלות נמוכה לכמות שבמתכונים. לכן הסל עשוי לעלות יותר בקופה.':'ההשוואה מעדיפה את התשלום הנמוך ביותר בין הסלים שנבדקו.'}</p>${result.shops.some(s=>data.policies[s].minimum_order_ils==null)?'<p class="warn">מינימום ההזמנה בחלק מהחנויות אינו ידוע — יש לאמת לפני הזמנה.</p>':''}`:'<h2>לא נמצא סל מלא שניתן להשוות</h2><p>בדקו פריטים ללא מחיר, דמי משלוח לא ידועים או מינימום הזמנה. המחירים הבודדים להלן אינם הזמנה מלאה.</p>';
  const groups={};
  data.rows.forEach((r,i)=>{
   const q=result?.rows[i]||r.options.filter(o=>(extra[i]||!o.extra)&&(confirmed[i]||!o.conditional)).sort((a,b)=>(extra[i]?a.used-b.used:a.cost-b.cost)||a.cost-b.cost)[0];
   const shop=q?.shop||'unknown'; (groups[shop]??=[]).push({r,i,q});
  });
  document.getElementById('items').innerHTML=Object.entries(groups).map(([shop,rows])=>`<section><h3>${esc(data.shops[shop]||'מחיר חסר')}${result?'':' — מחירים לבדיקה'}</h3>${rows.map(({r,i,q})=>`<article id="item-${i}"><h3>${esc(r.name)}</h3><p>דרוש למתכונים: ${esc(r.quantity)}</p><label>אופן הקנייה <select data-index="${i}" aria-label="אופן הקנייה של ${esc(r.name)}"><option value="0" ${!extra[i]?'selected':''}>רק הכמות הדרושה — תשלום נמוך בקופה</option><option value="1" ${extra[i]?'selected':''}>אפשר אריזות נוספות — עלות נמוכה לכמות שבמתכונים</option></select></label>${r.options.some(o=>o.conditional)?`<label class="warn"><input type="checkbox" data-confirm="${i}" ${confirmed[i]?'checked':''}> בדקתי באתר: ההצעות שלהלן חלות על אריזות זהות בכמות המוצגת, ללא תנאי נוסף</label><small>תנאי קבוצת המבצע בקובץ אינם חד־משמעיים. לפני אישור יש לבדוק את ההצעות באתר החנות.</small><ul>${r.options.filter(o=>o.conditional).map(o=>`<li><a href="${link(o.url)}" target="_blank" rel="noopener noreferrer">${esc(data.shops[o.shop])} — ${esc(o.name)}</a>: ${esc(o.promo)} · ${o.packs} אריזות · ${money(o.cost)}</li>`).join('')}</ul>`:''}${q?`<p><a href="${link(q.url)}" target="_blank" rel="noopener noreferrer">${esc(q.name)} ↗</a></p><div class="line">לקנייה: ${q.packs==null?'במשקל':q.packs+' אריזות'} · ${quantity(q.purchased,q.dimension)}</div><div class="line">נותר לאחר המתכונים: ${quantity(q.purchased-q.needed,q.dimension)}</div><div class="line"><b>לתשלום: ${money(q.cost)}</b> · עלות הכמות שבמתכונים: ${money(q.used)}</div><div class="line">מחיר השוואה: ${money(q.cost/q.purchased*(q.dimension==='count'?1:100))} ל־${q.dimension==='count'?'יחידה':quantity(100,q.dimension)}</div><div class="line">${esc(q.promo)}${q.conditional?' — חישוב לפי אישורכם לתנאים':''}</div>`:'<p class="warn">לא נמצא מוצר שניתן לתמחר ביחידות המתכון.</p>'}<nav>${r.recipes.map(ref=>`<a href="#${esc(ref.anchor)}" aria-label="למתכון ביום ${ref.day}">📖 יום ${ref.day}</a>`).join('')}</nav></article>`).join('')}</section>`).join('');
 }
 document.getElementById('items').addEventListener('change',e=>{if(e.target.dataset.confirm!=null){const i=Number(e.target.dataset.confirm);confirmed[i]=e.target.checked;render();document.querySelector(`[data-confirm="${i}"]`).focus({preventScroll:true});}else if(e.target.dataset.index!=null){const i=Number(e.target.dataset.index);extra[i]=e.target.value==='1';render();document.querySelector(`[data-index="${i}"]`).focus({preventScroll:true});}});
 document.getElementById('delivery').addEventListener('change',e=>{const {shop,field}=e.target.dataset;if(shop&&field){if(!e.target.validity.valid)return;data.policies[shop][field]=e.target.value===''?null:Number(e.target.value);render();}});
 document.getElementById('reset').addEventListener('click',()=>{extra=data.rows.map(()=>false);confirmed=data.rows.map(()=>false);data.policies=JSON.parse(JSON.stringify(original));controls();render();});
 controls();render();
}
