"""Static Hebrew display strings; no translation service is used at runtime."""
from pathlib import Path
from .config import load_yaml

SHOPS={'carrefour':'קרפור','rami-levy':'רמי לוי','shufersal':'שופרסל','victory':'ויקטורי'}
UNITS={'g':'גרם','kg':'ק״ג','ml':'מ״ל','l':'ליטר','units':'יחידות','head':'ראש',
       'tbsp':'כפות','tsp':'כפיות','clove':'שיני שום','pinch':'קורט','sprig':'ענפים','slice':'פרוסות','toTaste':'לפי הטעם'}
RECIPE_NAMES=dict(zip([
'Broccoli & ricotta pasta','Lentil & sweet-potato curry','Roasted cauliflower & chickpea tray','Shakshuka with feta',
'Tofu vegetable stir-fry','Zucchini & feta frittata','Spinach & ricotta lasagna','Roasted vegetable couscous',
'Bean & cheese quesadillas','Potato & broccoli cheese bake','Mujaddara (lentils, rice & onions)','Lentil bolognese pasta',
'Chickpea shakshuka','Tofu & broccoli coconut curry','Sweet-potato & bean tahini bowls','Chickpea & spinach rice',
'Pea & tomato pasta','Roasted tofu, potato & zucchini tray','Melanzane alla parmigiana','Sabich','Ghapama','Draniki',
'Bhuna khichuri','Tarator','Misir wat','Šaltibarščiai','Gemista','Pizza margherita','Kulajda','Byrek me spinaq',
'Flia','Palak paneer','Dal tadka','Spanakopita','Spanish tortilla','Kholodnik','Ratatouille'],[
'פסטה עם ברוקולי וריקוטה','קארי עדשים ובטטה','כרובית וחומוס בתנור','שקשוקה עם פטה',
'טופו מוקפץ עם ירקות','פריטטה עם קישואים ופטה','לזניה עם תרד וריקוטה','קוסקוס עם ירקות צלויים',
'קסדיות שעועית וגבינה','מאפה תפוחי אדמה וברוקולי עם גבינה','מג׳דרה','פסטה בולונז עדשים',
'שקשוקת חומוס','קארי טופו וברוקולי בחלב קוקוס','קערות בטטה ושעועית עם טחינה','אורז עם חומוס ותרד',
'פסטה עם אפונה ועגבניות','טופו, תפוחי אדמה וקישואים בתנור','חצילים בפרמזן','סביח','דלעת ממולאת באורז ופירות יבשים','לביבות תפוחי אדמה',
'אורז ועדשים בנוסח בנגלי','מרק יוגורט ומלפפונים קר','תבשיל עדשים אתיופי','מרק סלק ליטאי קר','ירקות ממולאים באורז',
'פיצה מרגריטה','מרק פטריות ותפוחי אדמה','בורקס תרד אלבני','פליה — מאפה שכבות אלבני','תרד עם גבינת פניר',
'דאל עדשים מתובל','מאפה פילו ותרד יווני','טורטייה ספרדית עם תפוחי אדמה','מרק סלק וקפיר קר','רטטוי']))

def ingredient_names():
    path=Path(__file__).resolve().parents[2]/'config/ingredients.yml'
    return {spec['name']:spec.get('name_he') or (spec.get('search_terms') or [spec['name']])[0]
            for spec in load_yaml(path)['ingredients'].values()}

INGREDIENTS=ingredient_names()
INGREDIENTS.update({'cooked beans':'שעועית מבושלת','green peas':'אפונה ירוקה','tomato sauce':'רוטב עגבניות',
    'corn':'גרגרי תירס','soured cream':'שמנת חמוצה','short grain rice':'אורז עגול','vegetable oil':'שמן צמחי',
    'coconut milk':'חלב קוקוס','yellow cheese':'גבינה צהובה','salt and pepper':'מלח ופלפל','water':'מים'})

def recipe(name):return RECIPE_NAMES.get(name,name)
def ingredient(name):return INGREDIENTS.get(name,name)
def shop(name):return SHOPS.get(name,name)
def unit(name):return UNITS.get(name,name)
