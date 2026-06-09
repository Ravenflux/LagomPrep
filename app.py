import os, sys, json, sqlite3, threading, webbrowser, requests, math
from flask import Flask, request, jsonify, render_template

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    TMPL_DIR = os.path.join(sys._MEIPASS, 'templates')
    STAT_DIR = os.path.join(sys._MEIPASS, 'static')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TMPL_DIR = os.path.join(BASE_DIR, 'templates')
    STAT_DIR = os.path.join(BASE_DIR, 'static')

DB_PATH = os.path.join(BASE_DIR, 'recipevault.db')
app = Flask(__name__, template_folder=TMPL_DIR, static_folder=STAT_DIR)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, meal_type TEXT NOT NULL,
            cook_time TEXT, servings INTEGER DEFAULT 1,
            description TEXT, notes TEXT,
            calories_per_serving REAL, calories_total REAL,
            protein_per_serving REAL,  protein_total REAL,
            carbs_per_serving REAL,    carbs_total REAL,
            fat_per_serving REAL,      fat_total REAL,
            fiber_per_serving REAL,    fiber_total REAL,
            net_carbs_per_serving REAL,net_carbs_total REAL,
            sodium_per_serving REAL,   sodium_total REAL,
            is_retired INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL, name TEXT NOT NULL,
            qty TEXT, store_section TEXT DEFAULT 'pantry', sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL, step_number INTEGER NOT NULL,
            title TEXT, content TEXT NOT NULL, timer_seconds INTEGER,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL, tag_type TEXT NOT NULL, tag_value TEXT NOT NULL,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS cook_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL, cooked_on DATE NOT NULL,
            notes TEXT, rating INTEGER,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, age INTEGER, sex TEXT,
            height_in REAL, weight_lb REAL, activity_level TEXT,
            goal TEXT DEFAULT 'maintain',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS meal_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_date DATE NOT NULL, user_id INTEGER NOT NULL,
            recipe_id INTEGER NOT NULL, meal_slot TEXT NOT NULL,
            servings_override REAL DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS pantry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            have_it INTEGER DEFAULT 1,
            status TEXT DEFAULT 'stocked',
            quantity TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS custom_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT DEFAULT '#e8a838',
            icon TEXT DEFAULT '🏷',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT
        );
    ''')
    conn.commit(); conn.close()
    # Migrate existing pantry table if columns missing
    conn2=get_db(); c2=conn2.cursor()
    cols=[r[1] for r in c2.execute("PRAGMA table_info(pantry)").fetchall()]
    if 'status' not in cols: c2.execute("ALTER TABLE pantry ADD COLUMN status TEXT DEFAULT 'stocked'")
    if 'quantity' not in cols: c2.execute("ALTER TABLE pantry ADD COLUMN quantity TEXT DEFAULT ''")
    conn2.commit(); conn2.close()

SEED_RECIPES = [
    {"name":"Morning Protein Shake","meal_type":"breakfast","cook_time":"5 min","servings":1,"description":"Quick high-protein breakfast shake.","notes":"Add flaxseed for omega-3s.","calories_per_serving":280,"protein_per_serving":32,"carbs_per_serving":28,"fat_per_serving":5,"fiber_per_serving":3,"net_carbs_per_serving":25,"sodium_per_serving":180,"tags":[],"ingredients":[{"name":"2% milk","qty":"1 cup","store_section":"dairy"},{"name":"banana cream whey protein powder","qty":"1 scoop","store_section":"pantry"},{"name":"banana","qty":"½ medium","store_section":"produce"},{"name":"ground flaxseed meal","qty":"1 tbsp","store_section":"pantry"},{"name":"ice","qty":"½ cup","store_section":"other"}],"steps":[{"step_number":1,"title":"Blend","content":"Add all ingredients to blender. Blend 30 seconds until smooth.","timer_seconds":30}]},
    {"name":"Greek Yogurt Parfait","meal_type":"breakfast","cook_time":"5 min","servings":1,"description":"Quick high-protein parfait.","notes":"Skip honey to reduce sugar. Omit honey for children under 1 year.","calories_per_serving":240,"protein_per_serving":18,"carbs_per_serving":34,"fat_per_serving":2,"fiber_per_serving":4,"net_carbs_per_serving":30,"sodium_per_serving":75,"tags":[],"ingredients":[{"name":"Friendly Farms Nonfat Vanilla Greek Yogurt","qty":"1 cup","store_section":"dairy"},{"name":"mixed berries (fresh or frozen)","qty":"½ cup","store_section":"produce"},{"name":"rolled oats","qty":"2 tbsp","store_section":"pantry"},{"name":"ground flaxseed meal","qty":"1 tsp","store_section":"pantry"},{"name":"honey (optional)","qty":"1 tsp","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Layer","content":"Add yogurt to bowl. Top with berries, oats, flaxseed. Drizzle honey if using."}]},
    {"name":"Baked Oatmeal","meal_type":"breakfast","cook_time":"40 min","servings":6,"description":"Hearty batch-prep baked oatmeal. Makes 6 servings.","notes":"Freeze individual portions up to 3 months. Contains baked egg.","calories_per_serving":280,"protein_per_serving":9,"carbs_per_serving":48,"fat_per_serving":6,"fiber_per_serving":5,"net_carbs_per_serving":43,"sodium_per_serving":120,"tags":[],"ingredients":[{"name":"rolled oats","qty":"2 cups","store_section":"pantry"},{"name":"banana, mashed","qty":"2 medium","store_section":"produce"},{"name":"2% milk","qty":"1½ cups","store_section":"dairy"},{"name":"eggs","qty":"2 large","store_section":"dairy"},{"name":"maple syrup or honey","qty":"2 tbsp","store_section":"pantry"},{"name":"baking powder","qty":"1 tsp","store_section":"pantry"},{"name":"cinnamon","qty":"1 tsp","store_section":"pantry"},{"name":"vanilla extract","qty":"1 tsp","store_section":"pantry"},{"name":"ground flaxseed meal","qty":"2 tbsp","store_section":"pantry"},{"name":"mixed berries","qty":"1 cup","store_section":"produce"}],"steps":[{"step_number":1,"title":"Preheat","content":"Preheat oven to 375°F. Grease baking dish.","timer_seconds":600},{"step_number":2,"title":"Mix","content":"Mash bananas. Whisk in milk, eggs, syrup, vanilla. Add oats, baking powder, cinnamon, flaxseed."},{"step_number":3,"title":"Bake","content":"Pour into dish, top with berries. Bake 35–40 min until set.","timer_seconds":2100}]},
    {"name":"Banana Oat Muffins","meal_type":"breakfast","cook_time":"30 min","servings":12,"description":"Simple banana oat muffins. Batch-prep, freezer-safe.","notes":"Contains baked egg. Freezes well individually wrapped.","calories_per_serving":150,"protein_per_serving":4,"carbs_per_serving":28,"fat_per_serving":3,"fiber_per_serving":3,"net_carbs_per_serving":25,"sodium_per_serving":95,"tags":[],"ingredients":[{"name":"rolled oats","qty":"2 cups","store_section":"pantry"},{"name":"ripe bananas, mashed","qty":"3 medium","store_section":"produce"},{"name":"eggs","qty":"2 large","store_section":"dairy"},{"name":"honey or maple syrup","qty":"3 tbsp","store_section":"pantry"},{"name":"baking powder","qty":"1 tsp","store_section":"pantry"},{"name":"cinnamon","qty":"1 tsp","store_section":"pantry"},{"name":"vanilla extract","qty":"1 tsp","store_section":"pantry"},{"name":"ground flaxseed meal","qty":"2 tbsp","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Preheat","content":"Preheat oven to 350°F. Line muffin tin.","timer_seconds":600},{"step_number":2,"title":"Mix","content":"Mash bananas, add eggs, honey, vanilla. Stir in oats, baking powder, cinnamon, flaxseed."},{"step_number":3,"title":"Bake","content":"Fill cups. Bake 20–22 min until toothpick clean.","timer_seconds":1320}]},
    {"name":"Oat Flour Banana Bread (Upgraded)","meal_type":"breakfast","cook_time":"65 min","servings":10,"description":"100% oat flour banana bread with brown butter and espresso.","notes":"155–165 cal/slice. Egg-free. Freezes well sliced.","calories_per_serving":155,"protein_per_serving":4,"carbs_per_serving":23,"fat_per_serving":5,"fiber_per_serving":3,"net_carbs_per_serving":20,"sodium_per_serving":110,"tags":[],"ingredients":[{"name":"oat flour","qty":"1½ cups","store_section":"pantry"},{"name":"ripe bananas, mashed","qty":"3 medium","store_section":"produce"},{"name":"unsalted butter (brown it)","qty":"¼ cup","store_section":"dairy"},{"name":"honey or maple syrup","qty":"¼ cup","store_section":"pantry"},{"name":"ground flaxseed meal","qty":"2 tbsp","store_section":"pantry"},{"name":"warm water (flax egg)","qty":"5 tbsp","store_section":"other"},{"name":"baking powder","qty":"1½ tsp","store_section":"pantry"},{"name":"cinnamon","qty":"1 tsp","store_section":"pantry"},{"name":"nutmeg","qty":"¼ tsp","store_section":"pantry"},{"name":"espresso powder","qty":"½ tsp","store_section":"pantry"},{"name":"vanilla extract","qty":"1 tsp","store_section":"pantry"},{"name":"salt","qty":"¼ tsp","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Flax egg","content":"Mix 2 tbsp flaxseed + 5 tbsp warm water. Rest 10 min.","timer_seconds":600},{"step_number":2,"title":"Brown butter","content":"Melt butter over medium, swirl until golden and nutty, ~5 min. Cool.","timer_seconds":300},{"step_number":3,"title":"Mix","content":"Preheat 350°F. Mash bananas, stir in brown butter, honey, vanilla, flax egg. Add dry ingredients."},{"step_number":4,"title":"Bake","content":"Pour into greased 9x5 pan. Bake 50–55 min until toothpick clean.","timer_seconds":3180},{"step_number":5,"title":"Cool","content":"Cool in pan 10 min, then rack. Slice when fully cool.","timer_seconds":600}]},
    {"name":"Freezer Smoothie Packs","meal_type":"breakfast","cook_time":"10 min batch","servings":1,"description":"Pre-portioned freezer bags for 60-second morning smoothies.","notes":"Batch prep several bags at once. Blend each bag with 1 cup milk and 1 scoop protein powder day-of.","calories_per_serving":220,"protein_per_serving":28,"carbs_per_serving":28,"fat_per_serving":4,"fiber_per_serving":5,"net_carbs_per_serving":23,"sodium_per_serving":160,"tags":[],"ingredients":[{"name":"frozen banana chunks","qty":"½ cup per bag","store_section":"frozen"},{"name":"frozen spinach","qty":"¼ cup per bag","store_section":"frozen"},{"name":"mixed berries, frozen","qty":"½ cup per bag","store_section":"frozen"},{"name":"ground flaxseed meal","qty":"1 tbsp per bag","store_section":"pantry"},{"name":"2% milk or almond milk","qty":"1 cup (day-of)","store_section":"dairy"},{"name":"banana cream whey protein powder","qty":"1 scoop (day-of)","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Pack bags","content":"Portion banana, spinach, berries, flaxseed into zip bags. Freeze."},{"step_number":2,"title":"Morning blend","content":"Empty bag into blender, add milk + protein. Blend 45 sec.","timer_seconds":45}]},
    {"name":"Warm Stovetop Oatmeal","meal_type":"breakfast","cook_time":"10 min","servings":1,"description":"Quick weekday oatmeal. Heart-healthy, minimal cleanup.","notes":"Mild and versatile — customize toppings to taste.","calories_per_serving":250,"protein_per_serving":8,"carbs_per_serving":44,"fat_per_serving":5,"fiber_per_serving":5,"net_carbs_per_serving":39,"sodium_per_serving":90,"tags":[],"ingredients":[{"name":"old-fashioned rolled oats","qty":"½ cup","store_section":"pantry"},{"name":"water or 2% milk","qty":"1 cup","store_section":"dairy"},{"name":"banana, sliced","qty":"½ medium","store_section":"produce"},{"name":"ground flaxseed meal","qty":"1 tbsp","store_section":"pantry"},{"name":"cinnamon","qty":"¼ tsp","store_section":"pantry"},{"name":"honey or maple syrup","qty":"1 tsp","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Cook","content":"Boil liquid, add oats, reduce to medium. Cook 5 min.","timer_seconds":300},{"step_number":2,"title":"Finish","content":"Stir in cinnamon, flaxseed, honey. Top with banana."}]},
    {"name":"Greek Turkey Wrap","meal_type":"lunch","cook_time":"10 min","servings":1,"description":"Greek-inspired turkey wrap. ~42g protein, under 420 cal.","notes":"Pairs best with homemade tzatziki. Store-bought works in a pinch.","calories_per_serving":415,"protein_per_serving":42,"carbs_per_serving":45,"fat_per_serving":7,"fiber_per_serving":31,"net_carbs_per_serving":9,"sodium_per_serving":820,"tags":[],"ingredients":[{"name":"Mission Carb Balance burrito tortilla","qty":"1 large","store_section":"bread"},{"name":"deli turkey breast (low sodium)","qty":"4 oz","store_section":"deli"},{"name":"red split lentils (cooked/rinsed)","qty":"⅓ cup","store_section":"pantry"},{"name":"tzatziki sauce (homemade)","qty":"3 tbsp","store_section":"dairy"},{"name":"baby spinach","qty":"½ cup","store_section":"produce"},{"name":"tomato, sliced","qty":"2 slices","store_section":"produce"},{"name":"cucumber, sliced (peeled)","qty":"⅓ cup","store_section":"produce"},{"name":"dried oregano","qty":"pinch","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Warm tortilla","content":"Heat tortilla in dry skillet 20–30 sec/side.","timer_seconds":40},{"step_number":2,"title":"Layer","content":"Spread tzatziki, then lentils, turkey, cucumber, tomato, spinach. Season."},{"step_number":3,"title":"Roll","content":"Fold sides in, roll from bottom. Slice diagonal."}]},
    {"name":"Air Fryer Fish","meal_type":"dinner","cook_time":"20 min","servings":2,"description":"Versatile air fryer fish — salmon, tilapia, or whitefish.","notes":"Salmon = best omega-3s. Pairs with spinach and Spanish rice.","calories_per_serving":375,"protein_per_serving":40,"carbs_per_serving":2,"fat_per_serving":12,"fiber_per_serving":0,"net_carbs_per_serving":2,"sodium_per_serving":310,"tags":[],"ingredients":[{"name":"fish fillets (salmon, tilapia, or whitefish)","qty":"12 oz","store_section":"seafood"},{"name":"avocado or olive oil spray","qty":"1 spray","store_section":"pantry"},{"name":"Italian herb seasoning","qty":"½ tsp","store_section":"pantry"},{"name":"garlic powder","qty":"½ tsp","store_section":"pantry"},{"name":"onion powder","qty":"½ tsp","store_section":"pantry"},{"name":"salt","qty":"¼ tsp","store_section":"pantry"},{"name":"black pepper","qty":"¼ tsp","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Preheat","content":"Preheat air fryer to 400°F. Pat fish dry.","timer_seconds":180},{"step_number":2,"title":"Season","content":"Spray and rub with combined spices."},{"step_number":3,"title":"Air fry","content":"Cook 400°F — whitefish 8–10 min, salmon 10–12 min. Do not flip.","timer_seconds":600},{"step_number":4,"title":"Rest","content":"Rest 2 min before plating.","timer_seconds":120}]},
    {"name":"Air Fryer Lemon Pepper Shrimp","meal_type":"dinner","cook_time":"15 min","servings":2,"description":"Fast high-protein shrimp. Under 10 min to cook.","notes":"Don't overcrowd basket.","calories_per_serving":550,"protein_per_serving":48,"carbs_per_serving":52,"fat_per_serving":8,"fiber_per_serving":2,"net_carbs_per_serving":50,"sodium_per_serving":680,"tags":[],"ingredients":[{"name":"large shrimp, peeled and deveined","qty":"1 lb","store_section":"seafood"},{"name":"avocado or olive oil spray","qty":"1 spray","store_section":"pantry"},{"name":"lemon pepper seasoning","qty":"1 tsp","store_section":"pantry"},{"name":"garlic powder","qty":"½ tsp","store_section":"pantry"},{"name":"salt","qty":"⅓ tsp","store_section":"pantry"},{"name":"lemon","qty":"½","store_section":"produce"},{"name":"cooked white or brown rice","qty":"½ cup","store_section":"pantry"},{"name":"tzatziki (homemade)","qty":"2 tbsp","store_section":"dairy"}],"steps":[{"step_number":1,"title":"Season","content":"Preheat AF 400°F. Pat shrimp dry, toss with oil, lemon pepper, garlic, salt.","timer_seconds":180},{"step_number":2,"title":"Air fry","content":"Single layer, 400°F, 6–8 min until pink. Don't overcook.","timer_seconds":420},{"step_number":3,"title":"Serve","content":"Squeeze lemon over shrimp. Serve over rice with tzatziki."}]},
    {"name":"Blackened Air Fryer Chicken Thighs","meal_type":"dinner","cook_time":"25 min","servings":4,"description":"Crispy blackened chicken thighs with roasted tomatoes.","notes":"Serve over rice or greens. Skip tomato topping if preferred.","calories_per_serving":420,"protein_per_serving":38,"carbs_per_serving":5,"fat_per_serving":22,"fiber_per_serving":1,"net_carbs_per_serving":4,"sodium_per_serving":520,"tags":[],"ingredients":[{"name":"bone-in skin-on chicken thighs","qty":"4 thighs","store_section":"meat"},{"name":"blackened/cajun seasoning","qty":"1½ tsp","store_section":"pantry"},{"name":"garlic powder","qty":"½ tsp","store_section":"pantry"},{"name":"onion powder","qty":"½ tsp","store_section":"pantry"},{"name":"salt","qty":"¼ tsp","store_section":"pantry"},{"name":"avocado or olive oil spray","qty":"1 spray","store_section":"pantry"},{"name":"cherry tomatoes","qty":"1 cup","store_section":"produce"},{"name":"olive oil","qty":"1 tsp","store_section":"pantry"},{"name":"dried oregano","qty":"¼ tsp","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Season","content":"Preheat AF 400°F. Pat chicken dry, rub with spices.","timer_seconds":180},{"step_number":2,"title":"First cook","content":"Cook skin-side down 400°F 10 min.","timer_seconds":600},{"step_number":3,"title":"Flip","content":"Flip skin-up. Add tomatoes tossed with oil and oregano. Cook 8–10 more min to 165°F.","timer_seconds":540},{"step_number":4,"title":"Plate","content":"Plate over rice. Spoon tomatoes over top."}]},
    {"name":"Air Fryer Italian Herb Pork Tenderloin","meal_type":"dinner","cook_time":"30 min","servings":2,"description":"Lean Italian herb pork with sweet potato and spinach.","notes":"Internal temp 145°F is safe — slight pink center is normal. Always rest before slicing.","calories_per_serving":625,"protein_per_serving":52,"carbs_per_serving":42,"fat_per_serving":14,"fiber_per_serving":6,"net_carbs_per_serving":36,"sodium_per_serving":480,"tags":[],"ingredients":[{"name":"pork tenderloin (~1 lb)","qty":"1","store_section":"meat"},{"name":"avocado or olive oil spray","qty":"1 spray","store_section":"pantry"},{"name":"Italian herb seasoning","qty":"1 tsp","store_section":"pantry"},{"name":"garlic powder","qty":"½ tsp","store_section":"pantry"},{"name":"onion powder","qty":"½ tsp","store_section":"pantry"},{"name":"salt","qty":"⅓ tsp","store_section":"pantry"},{"name":"black pepper","qty":"⅓ tsp","store_section":"pantry"},{"name":"sweet potatoes","qty":"2 medium","store_section":"produce"},{"name":"baby spinach","qty":"4 cups","store_section":"produce"},{"name":"olive oil","qty":"1 tsp","store_section":"pantry"},{"name":"garlic cloves, minced","qty":"2","store_section":"produce"}],"steps":[{"step_number":1,"title":"Prep","content":"Preheat AF 400°F. Pierce sweet potatoes, microwave 5 min each. Season pork.","timer_seconds":300},{"step_number":2,"title":"Air fry","content":"Cook pork 400°F 20–22 min, flip halfway, to 145°F.","timer_seconds":1260},{"step_number":3,"title":"Spinach","content":"Heat oil, sauté garlic 30 sec, add spinach, wilt 1–2 min.","timer_seconds":120},{"step_number":4,"title":"Rest","content":"Rest pork 5 min, slice. Plate with sweet potato and spinach.","timer_seconds":300}]},
    {"name":"Crock Pot White Chicken Chili","meal_type":"dinner","cook_time":"6-8 hr","servings":4,"description":"Zero active cook time. Dump-and-go. Freezes perfectly.","notes":"Serve with Greek yogurt or tzatziki instead of sour cream. Freezes up to 3 months.","calories_per_serving":525,"protein_per_serving":45,"carbs_per_serving":52,"fat_per_serving":8,"fiber_per_serving":14,"net_carbs_per_serving":38,"sodium_per_serving":680,"tags":[],"ingredients":[{"name":"boneless skinless chicken breasts","qty":"2","store_section":"meat"},{"name":"white beans (cannellini/Great Northern), drained","qty":"2 cans (15oz)","store_section":"pantry"},{"name":"low-sodium chicken broth","qty":"2 cups","store_section":"pantry"},{"name":"diced green chiles","qty":"1 can (4oz)","store_section":"pantry"},{"name":"cumin","qty":"1 tsp","store_section":"pantry"},{"name":"garlic powder","qty":"1 tsp","store_section":"pantry"},{"name":"onion powder","qty":"1 tsp","store_section":"pantry"},{"name":"dried oregano","qty":"½ tsp","store_section":"pantry"},{"name":"salt","qty":"⅓ tsp","store_section":"pantry"},{"name":"black pepper","qty":"⅓ tsp","store_section":"pantry"},{"name":"garlic cloves, minced","qty":"4","store_section":"produce"}],"steps":[{"step_number":1,"title":"Load","content":"Add all ingredients to crock pot. Stir."},{"step_number":2,"title":"Cook","content":"LOW 6–8 hr or HIGH 3–4 hr.","timer_seconds":25200},{"step_number":3,"title":"Shred","content":"Remove chicken, shred with forks, return to pot. Adjust salt."},{"step_number":4,"title":"Serve","content":"Bowl with tzatziki or Greek yogurt, optional hot sauce."}]},
    {"name":"Slow Cooker Beef Barley Soup","meal_type":"dinner","cook_time":"7-8 hr","servings":5,"description":"Hearty slow cooker soup with lean beef, lentils, and barley.","notes":"Skim fat after refrigerating overnight. Barley absorbs liquid — add broth when reheating.","calories_per_serving":350,"protein_per_serving":28,"carbs_per_serving":38,"fat_per_serving":8,"fiber_per_serving":9,"net_carbs_per_serving":29,"sodium_per_serving":520,"tags":[],"ingredients":[{"name":"lean beef (sirloin tip/eye of round), cubed","qty":"½ lb","store_section":"meat"},{"name":"green or brown lentils","qty":"½ cup","store_section":"pantry"},{"name":"pearl barley","qty":"½ cup","store_section":"pantry"},{"name":"low-sodium beef broth","qty":"4 cups","store_section":"pantry"},{"name":"carrots, sliced (peeled)","qty":"2 medium","store_section":"produce"},{"name":"celery, sliced","qty":"2 stalks","store_section":"produce"},{"name":"yellow onion, diced","qty":"1 medium","store_section":"produce"},{"name":"garlic cloves, minced","qty":"3","store_section":"produce"},{"name":"tomato paste","qty":"2 tbsp","store_section":"pantry"},{"name":"cremini mushrooms, sliced","qty":"8 oz","store_section":"produce"},{"name":"bay leaf","qty":"1","store_section":"pantry"},{"name":"dried thyme","qty":"½ tsp","store_section":"pantry"},{"name":"Worcestershire sauce","qty":"1 tsp","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Sear beef","content":"Sear beef cubes in skillet over high heat 2–3 min/side.","timer_seconds":360},{"step_number":2,"title":"Load","content":"Add everything to slow cooker. Stir."},{"step_number":3,"title":"Cook","content":"LOW 7–8 hr or HIGH 3.5–4 hr.","timer_seconds":25200},{"step_number":4,"title":"Finish","content":"Discard bay leaf. Adjust seasoning. Add broth if too thick."}]},
    {"name":"Ground Turkey Taco Bowl","meal_type":"dinner","cook_time":"25 min","servings":4,"description":"Quick weeknight taco bowl with lean ground turkey.","notes":"Use Greek yogurt instead of sour cream to reduce saturated fat.","calories_per_serving":480,"protein_per_serving":38,"carbs_per_serving":48,"fat_per_serving":12,"fiber_per_serving":8,"net_carbs_per_serving":40,"sodium_per_serving":620,"tags":[],"ingredients":[{"name":"lean ground turkey","qty":"1 lb","store_section":"meat"},{"name":"taco seasoning (low sodium)","qty":"1 packet","store_section":"pantry"},{"name":"cooked brown rice","qty":"1 cup","store_section":"pantry"},{"name":"black beans, drained","qty":"1 can (15oz)","store_section":"pantry"},{"name":"corn kernels (frozen or canned)","qty":"½ cup","store_section":"pantry"},{"name":"salsa","qty":"¼ cup","store_section":"pantry"},{"name":"avocado, sliced","qty":"½","store_section":"produce"},{"name":"lime","qty":"1","store_section":"produce"},{"name":"shredded lettuce or spinach","qty":"1 cup","store_section":"produce"},{"name":"Fage 0% Greek yogurt","qty":"2 tbsp","store_section":"dairy"}],"steps":[{"step_number":1,"title":"Cook turkey","content":"Brown turkey in skillet over medium-high, 8–10 min. Drain fat.","timer_seconds":600},{"step_number":2,"title":"Season","content":"Add taco seasoning + ¼ cup water. Simmer 2–3 min.","timer_seconds":180},{"step_number":3,"title":"Build bowl","content":"Rice base, then turkey, beans, corn, lettuce, avocado, salsa, yogurt, lime squeeze."}]},
    {"name":"French Onion Baked Rice","meal_type":"side","cook_time":"60 min","servings":4,"description":"Hands-off oven-baked rice with deep French onion flavor.","notes":"Use low-sodium broth and soup to manage sodium. Do not lift the foil mid-bake.","calories_per_serving":320,"protein_per_serving":6,"carbs_per_serving":52,"fat_per_serving":8,"fiber_per_serving":1,"net_carbs_per_serving":51,"sodium_per_serving":680,"tags":[],"ingredients":[{"name":"long-grain white rice (uncooked)","qty":"1 cup","store_section":"pantry"},{"name":"beef or chicken broth (low sodium)","qty":"2 cups","store_section":"pantry"},{"name":"French onion soup (canned, low sodium)","qty":"1 can (10.5oz)","store_section":"pantry"},{"name":"unsalted butter","qty":"2 tbsp","store_section":"dairy"}],"steps":[{"step_number":1,"title":"Combine","content":"Preheat 350°F. Mix rice, broth, soup, butter in 8x8 dish."},{"step_number":2,"title":"Bake","content":"Cover tightly with foil. Bake 60 min — no peeking.","timer_seconds":3600},{"step_number":3,"title":"Fluff","content":"Remove foil, fluff with fork, serve immediately."}]},
    {"name":"Italian Herb Vine Tomatoes","meal_type":"snack","cook_time":"15 min","servings":1,"description":"Roasted vine tomatoes. Low-cal savory snack.","notes":"Great as a low-calorie savory snack or side. Roasting softens the texture.","calories_per_serving":60,"protein_per_serving":1,"carbs_per_serving":7,"fat_per_serving":4,"fiber_per_serving":2,"net_carbs_per_serving":5,"sodium_per_serving":180,"tags":[],"ingredients":[{"name":"vine or cocktail tomatoes","qty":"1 cup","store_section":"produce"},{"name":"olive oil","qty":"1 tsp","store_section":"pantry"},{"name":"Italian herb seasoning","qty":"½ tsp","store_section":"pantry"},{"name":"garlic powder","qty":"¼ tsp","store_section":"pantry"},{"name":"salt and pepper","qty":"to taste","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Season","content":"Toss tomatoes with olive oil and herbs."},{"step_number":2,"title":"Roast","content":"Roast at 400°F 12–15 min.","timer_seconds":840}]},
    {"name":"Strawberry Fruit Dip","meal_type":"snack","cook_time":"5 min","servings":7,"description":"2-ingredient fruit dip. ~40 cal/serving.","notes":"Store covered in fridge up to 5 days.","calories_per_serving":40,"protein_per_serving":1,"carbs_per_serving":6,"fat_per_serving":1,"fiber_per_serving":0,"net_carbs_per_serving":6,"sodium_per_serving":20,"tags":[],"ingredients":[{"name":"Cool Whip Zero Sugar","qty":"8 oz tub","store_section":"frozen"},{"name":"sugar-free strawberry Jello powder","qty":"1 packet (0.3oz)","store_section":"pantry"},{"name":"fresh fruit for dipping","qty":"assorted","store_section":"produce"}],"steps":[{"step_number":1,"title":"Mix","content":"Thaw Cool Whip. Fold in Jello powder gently."},{"step_number":2,"title":"Chill","content":"Refrigerate 30 min before serving.","timer_seconds":1800}]},
    {"name":"NannerFree Cups","meal_type":"snack","cook_time":"20 min + freeze","servings":8,"description":"Frozen banana cups with Wowbutter soy butter. Peanut-free.","notes":"~56 cal each. Contains soy — check for allergies before serving.","calories_per_serving":56,"protein_per_serving":2,"carbs_per_serving":8,"fat_per_serving":3,"fiber_per_serving":1,"net_carbs_per_serving":7,"sodium_per_serving":25,"tags":[],"ingredients":[{"name":"ripe banana","qty":"1 large","store_section":"produce"},{"name":"Wowbutter toasted soy butter","qty":"2 tbsp","store_section":"pantry"},{"name":"honey","qty":"1 tsp","store_section":"pantry"},{"name":"dark chocolate chips","qty":"2 tbsp","store_section":"pantry"},{"name":"coconut oil","qty":"½ tsp","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Mix filling","content":"Mash banana, stir in Wowbutter and honey."},{"step_number":2,"title":"Chocolate shell","content":"Melt chocolate chips + coconut oil in 30-sec microwave bursts.","timer_seconds":90},{"step_number":3,"title":"Fill and freeze","content":"Fill silicone cups. Drizzle chocolate. Freeze 2+ hr.","timer_seconds":7200}]},
    {"name":"NannerKnight Cups","meal_type":"snack","cook_time":"30 min + freeze","servings":10,"description":"Frozen banana cups with peanut butter coating.","notes":"~84 cal each. CONTAINS PEANUTS — check for allergies before serving.","calories_per_serving":84,"protein_per_serving":3,"carbs_per_serving":10,"fat_per_serving":4,"fiber_per_serving":1,"net_carbs_per_serving":9,"sodium_per_serving":35,"tags":[],"ingredients":[{"name":"banana powder or mashed banana","qty":"¼ cup","store_section":"produce"},{"name":"oat flour","qty":"2 tbsp","store_section":"pantry"},{"name":"smooth peanut butter","qty":"2 tbsp","store_section":"pantry"},{"name":"dark chocolate chips","qty":"3 tbsp","store_section":"pantry"},{"name":"coconut oil","qty":"1 tsp","store_section":"pantry"},{"name":"honey","qty":"1 tsp","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Mix base","content":"Combine banana, oat flour, peanut butter, honey until soft dough."},{"step_number":2,"title":"Shape","content":"Press into silicone mini cups."},{"step_number":3,"title":"Coat","content":"Melt chocolate + coconut oil. Spoon over cups. Freeze 2+ hr.","timer_seconds":7200}]},
    {"name":"Banana Vanilla Froyo Popsicles","meal_type":"snack","cook_time":"15 min + freeze","servings":8,"description":"Creamy frozen yogurt popsicles. ~90 cal each. Toddler-safe.","notes":"Freeze at least 4 hours.","calories_per_serving":90,"protein_per_serving":5,"carbs_per_serving":16,"fat_per_serving":1,"fiber_per_serving":1,"net_carbs_per_serving":15,"sodium_per_serving":30,"tags":[],"ingredients":[{"name":"ripe bananas","qty":"3 medium","store_section":"produce"},{"name":"Fage 0% plain Greek yogurt","qty":"1 cup","store_section":"dairy"},{"name":"vanilla extract","qty":"1 tsp","store_section":"pantry"},{"name":"honey","qty":"1 tbsp","store_section":"pantry"},{"name":"ground flaxseed meal","qty":"2 tbsp","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Blend","content":"Blend all ingredients until smooth.","timer_seconds":45},{"step_number":2,"title":"Freeze","content":"Pour into molds, insert sticks. Freeze 4+ hr.","timer_seconds":14400}]},
    {"name":"Homemade Tzatziki","meal_type":"condiment","cook_time":"15 min","servings":8,"description":"Fage 0% base tzatziki. Household standard.","notes":"Store up to 5 days refrigerated. Squeeze cucumber very dry or it will water down.","calories_per_serving":45,"protein_per_serving":5,"carbs_per_serving":4,"fat_per_serving":1,"fiber_per_serving":0,"net_carbs_per_serving":4,"sodium_per_serving":110,"tags":[],"ingredients":[{"name":"Fage 0% plain Greek yogurt","qty":"1 cup","store_section":"dairy"},{"name":"English cucumber, peeled, grated, squeezed dry","qty":"½","store_section":"produce"},{"name":"garlic cloves, minced","qty":"2","store_section":"produce"},{"name":"fresh dill (or 1 tsp dried)","qty":"2 tbsp","store_section":"produce"},{"name":"lemon juice","qty":"1 tbsp","store_section":"produce"},{"name":"olive oil","qty":"1 tsp","store_section":"pantry"},{"name":"salt","qty":"¼ tsp","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Prep cucumber","content":"Grate cucumber. Squeeze out all water in a towel."},{"step_number":2,"title":"Combine","content":"Mix yogurt, cucumber, garlic, dill, lemon, olive oil, salt."},{"step_number":3,"title":"Chill","content":"Refrigerate 1+ hr. Better overnight.","timer_seconds":3600}]},
    {"name":"Homemade Dry Ranch Seasoning","meal_type":"condiment","cook_time":"5 min","servings":24,"description":"Pantry staple dry ranch mix.","notes":"Store in airtight jar up to 6 months. Mix 2–3 tsp per 1 cup Greek yogurt for a quick ranch dip.","calories_per_serving":5,"protein_per_serving":0,"carbs_per_serving":1,"fat_per_serving":0,"fiber_per_serving":0,"net_carbs_per_serving":1,"sodium_per_serving":95,"tags":[],"ingredients":[{"name":"dried dill weed","qty":"2 tbsp","store_section":"pantry"},{"name":"garlic powder","qty":"1 tbsp","store_section":"pantry"},{"name":"onion powder","qty":"1 tbsp","store_section":"pantry"},{"name":"dried parsley","qty":"2 tbsp","store_section":"pantry"},{"name":"dried chives","qty":"1 tbsp","store_section":"pantry"},{"name":"black pepper","qty":"1 tsp","store_section":"pantry"},{"name":"salt","qty":"1 tsp","store_section":"pantry"}],"steps":[{"step_number":1,"title":"Mix","content":"Combine all in a jar. Shake to combine. Store sealed."}]},
]

def seed_db():
    conn = get_db(); c = conn.cursor()
    if c.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] > 0:
        conn.close(); return
    for r in SEED_RECIPES:
        sv = r.get('servings', 1)
        def T(f): v=r.get(f); return float(v)*sv if v else None
        def P(f): v=r.get(f); return float(v) if v else None
        c.execute("""INSERT INTO recipes (name,meal_type,cook_time,servings,description,notes,
            calories_per_serving,calories_total,protein_per_serving,protein_total,
            carbs_per_serving,carbs_total,fat_per_serving,fat_total,
            fiber_per_serving,fiber_total,net_carbs_per_serving,net_carbs_total,
            sodium_per_serving,sodium_total) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r['name'],r['meal_type'],r.get('cook_time',''),sv,r.get('description',''),r.get('notes',''),
             P('calories_per_serving'),T('calories_per_serving'),P('protein_per_serving'),T('protein_per_serving'),
             P('carbs_per_serving'),T('carbs_per_serving'),P('fat_per_serving'),T('fat_per_serving'),
             P('fiber_per_serving'),T('fiber_per_serving'),P('net_carbs_per_serving'),T('net_carbs_per_serving'),
             P('sodium_per_serving'),T('sodium_per_serving')))
        rid = c.lastrowid
        for i,ing in enumerate(r.get('ingredients',[])):
            c.execute("INSERT INTO ingredients (recipe_id,name,qty,store_section,sort_order) VALUES (?,?,?,?,?)",
                      (rid,ing['name'],ing.get('qty',''),ing.get('store_section','pantry'),i))
        for s in r.get('steps',[]):
            c.execute("INSERT INTO steps (recipe_id,step_number,title,content,timer_seconds) VALUES (?,?,?,?,?)",
                      (rid,s['step_number'],s.get('title',''),s['content'],s.get('timer_seconds')))
            # Set default theme to Nordic
            nordic = json.dumps({"accent":"#7eb8c9","bg":"#1a1f2e","bg2":"#222838","text":"#e8edf5","text2":"#8899bb","border":"#2e3650"})
            c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?)", ('theme', nordic))
    conn.commit(); conn.close()

ACTIVITY_MULTIPLIERS = {'sedentary':1.2,'light':1.375,'moderate':1.55,'active':1.725,'very_active':1.9}
GOAL_ADJUSTMENTS = {'lose':-500,'maintain':0,'gain':300}

def calc_tdee(user):
    h_in=user.get('height_in') or 0; w_lb=user.get('weight_lb') or 0
    age=user.get('age') or 30; sex=(user.get('sex') or 'male').lower()
    h_cm=h_in*2.54; w_kg=w_lb*0.453592
    bmr=(10*w_kg+6.25*h_cm-5*age-161) if sex=='female' else (10*w_kg+6.25*h_cm-5*age+5)
    tdee=bmr*ACTIVITY_MULTIPLIERS.get(user.get('activity_level','sedentary'),1.2)
    return {'bmr':round(bmr),'tdee':round(tdee),'target':round(tdee+GOAL_ADJUSTMENTS.get(user.get('goal','maintain'),0))}

def hydrate(row, conn):
    r=dict(row); rid=r['id']
    r['ingredients']=[dict(i) for i in conn.execute("SELECT * FROM ingredients WHERE recipe_id=? ORDER BY sort_order",(rid,)).fetchall()]
    r['steps']=[dict(s) for s in conn.execute("SELECT * FROM steps WHERE recipe_id=? ORDER BY step_number",(rid,)).fetchall()]
    r['tags']=[dict(t) for t in conn.execute("SELECT * FROM tags WHERE recipe_id=?",(rid,)).fetchall()]
    r['cook_log']=[dict(l) for l in conn.execute("SELECT * FROM cook_log WHERE recipe_id=? ORDER BY cooked_on DESC",(rid,)).fetchall()]
    return r

@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/recipes')
def get_recipes():
    mt=request.args.get('meal_type',''); retired=request.args.get('show_retired','false')=='true'
    conn=get_db(); q="SELECT * FROM recipes WHERE 1=1"; p=[]
    if not retired: q+=" AND is_retired=0"
    if mt: q+=" AND meal_type=?"; p.append(mt)
    q+=" ORDER BY meal_type,name"
    rows=[hydrate(r,conn) for r in conn.execute(q,p).fetchall()]
    conn.close(); return jsonify(rows)

@app.route('/api/recipes/<int:rid>')
def get_recipe(rid):
    conn=get_db(); r=conn.execute("SELECT * FROM recipes WHERE id=?",(rid,)).fetchone()
    if not r: conn.close(); return jsonify({'error':'Not found'}),404
    data=hydrate(r,conn); conn.close(); return jsonify(data)

def upsert_recipe(data, rid=None):
    conn=get_db(); c=conn.cursor(); sv=int(data.get('servings',1))
    def T(f): v=data.get(f); return float(v)*sv if v not in (None,'','null') else None
    def P(f): v=data.get(f); return float(v) if v not in (None,'','null') else None
    fields=(data['name'],data['meal_type'],data.get('cook_time',''),sv,data.get('description',''),data.get('notes',''),
            P('calories_per_serving'),T('calories_per_serving'),P('protein_per_serving'),T('protein_per_serving'),
            P('carbs_per_serving'),T('carbs_per_serving'),P('fat_per_serving'),T('fat_per_serving'),
            P('fiber_per_serving'),T('fiber_per_serving'),P('net_carbs_per_serving'),T('net_carbs_per_serving'),
            P('sodium_per_serving'),T('sodium_per_serving'))
    if rid:
        c.execute("""UPDATE recipes SET name=?,meal_type=?,cook_time=?,servings=?,description=?,notes=?,
            calories_per_serving=?,calories_total=?,protein_per_serving=?,protein_total=?,
            carbs_per_serving=?,carbs_total=?,fat_per_serving=?,fat_total=?,
            fiber_per_serving=?,fiber_total=?,net_carbs_per_serving=?,net_carbs_total=?,
            sodium_per_serving=?,sodium_total=? WHERE id=?""", fields+(rid,))
        c.execute("DELETE FROM ingredients WHERE recipe_id=?",(rid,))
        c.execute("DELETE FROM steps WHERE recipe_id=?",(rid,))
        c.execute("DELETE FROM tags WHERE recipe_id=?",(rid,))
    else:
        c.execute("""INSERT INTO recipes (name,meal_type,cook_time,servings,description,notes,
            calories_per_serving,calories_total,protein_per_serving,protein_total,
            carbs_per_serving,carbs_total,fat_per_serving,fat_total,
            fiber_per_serving,fiber_total,net_carbs_per_serving,net_carbs_total,
            sodium_per_serving,sodium_total) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", fields)
        rid=c.lastrowid
    for i,ing in enumerate(data.get('ingredients',[])):
        if ing.get('name'):
            c.execute("INSERT INTO ingredients (recipe_id,name,qty,store_section,sort_order) VALUES (?,?,?,?,?)",
                      (rid,ing['name'],ing.get('qty',''),ing.get('store_section','pantry'),i))
    for s in data.get('steps',[]):
        if s.get('content'):
            c.execute("INSERT INTO steps (recipe_id,step_number,title,content,timer_seconds) VALUES (?,?,?,?,?)",
                      (rid,s['step_number'],s.get('title',''),s['content'],s.get('timer_seconds')))
    for t in data.get('tags',[]):
        c.execute("INSERT INTO tags (recipe_id,tag_type,tag_value) VALUES (?,?,?)",(rid,t['tag_type'],t['tag_value']))
    conn.commit(); conn.close(); return rid

@app.route('/api/recipes',methods=['POST'])
def create_recipe(): rid=upsert_recipe(request.json); return jsonify({'id':rid,'success':True})

@app.route('/api/recipes/<int:rid>',methods=['PUT'])
def update_recipe(rid): upsert_recipe(request.json,rid); return jsonify({'success':True})

@app.route('/api/recipes/<int:rid>',methods=['DELETE'])
def delete_recipe(rid):
    conn=get_db(); conn.execute("DELETE FROM recipes WHERE id=?",(rid,)); conn.commit(); conn.close()
    return jsonify({'success':True})

@app.route('/api/recipes/<int:rid>/retire',methods=['POST'])
def retire_recipe(rid):
    conn=get_db(); conn.execute("UPDATE recipes SET is_retired=1 WHERE id=?",(rid,)); conn.commit(); conn.close()
    return jsonify({'success':True})

@app.route('/api/recipes/<int:rid>/restore',methods=['POST'])
def restore_recipe(rid):
    conn=get_db(); conn.execute("UPDATE recipes SET is_retired=0 WHERE id=?",(rid,)); conn.commit(); conn.close()
    return jsonify({'success':True})

@app.route('/api/recipes/<int:rid>/log',methods=['POST'])
def add_log(rid):
    d=request.json; conn=get_db()
    conn.execute("INSERT INTO cook_log (recipe_id,cooked_on,notes,rating) VALUES (?,?,?,?)",
                 (rid,d.get('cooked_on'),d.get('notes',''),d.get('rating')))
    conn.commit(); conn.close(); return jsonify({'success':True})

@app.route('/api/recipes/<int:rid>/log/<int:lid>',methods=['DELETE'])
def del_log(rid,lid):
    conn=get_db(); conn.execute("DELETE FROM cook_log WHERE id=? AND recipe_id=?",(lid,rid))
    conn.commit(); conn.close(); return jsonify({'success':True})

@app.route('/api/users')
def get_users():
    conn=get_db()
    users=[dict(u) for u in conn.execute("SELECT * FROM users ORDER BY name").fetchall()]
    for u in users: u['tdee_data']=calc_tdee(u)
    conn.close(); return jsonify(users)

@app.route('/api/users',methods=['POST'])
def create_user():
    d=request.json; conn=get_db(); c=conn.cursor()
    c.execute("INSERT INTO users (name,age,sex,height_in,weight_lb,activity_level,goal) VALUES (?,?,?,?,?,?,?)",
              (d['name'],d.get('age'),d.get('sex'),d.get('height_in'),d.get('weight_lb'),d.get('activity_level','sedentary'),d.get('goal','maintain')))
    uid=c.lastrowid; conn.commit(); conn.close(); return jsonify({'id':uid,'success':True})

@app.route('/api/users/<int:uid>',methods=['PUT'])
def update_user(uid):
    d=request.json; conn=get_db()
    conn.execute("UPDATE users SET name=?,age=?,sex=?,height_in=?,weight_lb=?,activity_level=?,goal=? WHERE id=?",
                 (d['name'],d.get('age'),d.get('sex'),d.get('height_in'),d.get('weight_lb'),d.get('activity_level','sedentary'),d.get('goal','maintain'),uid))
    conn.commit(); conn.close(); return jsonify({'success':True})

@app.route('/api/users/<int:uid>',methods=['DELETE'])
def delete_user(uid):
    conn=get_db(); conn.execute("DELETE FROM users WHERE id=?",(uid,)); conn.commit(); conn.close()
    return jsonify({'success':True})

@app.route('/api/mealplan')
def get_mealplan():
    week=request.args.get('week',''); user_id=request.args.get('user_id','')
    conn=get_db()
    q="SELECT mp.*,r.name as recipe_name,r.meal_type,r.calories_per_serving,r.protein_per_serving,r.carbs_per_serving,r.fat_per_serving FROM meal_plan mp JOIN recipes r ON r.id=mp.recipe_id WHERE 1=1"
    p=[]
    if week: q+=" AND mp.plan_date BETWEEN ? AND date(?,'+6 days')"; p+=[week,week]
    if user_id: q+=" AND mp.user_id=?"; p.append(user_id)
    rows=[dict(r) for r in conn.execute(q,p).fetchall()]
    conn.close(); return jsonify(rows)

@app.route('/api/mealplan',methods=['POST'])
def add_mealplan():
    d=request.json; conn=get_db(); c=conn.cursor()
    c.execute("INSERT INTO meal_plan (plan_date,user_id,recipe_id,meal_slot,servings_override) VALUES (?,?,?,?,?)",
              (d['plan_date'],d['user_id'],d['recipe_id'],d['meal_slot'],d.get('servings_override',1)))
    mid=c.lastrowid; conn.commit(); conn.close(); return jsonify({'id':mid,'success':True})

@app.route('/api/mealplan/<int:mid>',methods=['DELETE'])
def del_mealplan(mid):
    conn=get_db(); conn.execute("DELETE FROM meal_plan WHERE id=?",(mid,)); conn.commit(); conn.close()
    return jsonify({'success':True})

@app.route('/api/pantry')
def get_pantry():
    conn=get_db(); items=[dict(r) for r in conn.execute("SELECT * FROM pantry ORDER BY name").fetchall()]
    conn.close(); return jsonify(items)

@app.route('/api/pantry',methods=['POST'])
def add_pantry():
    d=request.json; conn=get_db()
    conn.execute("INSERT OR REPLACE INTO pantry (name,have_it,status,quantity) VALUES (?,?,?,?)",
                 (d['name'],d.get('have_it',1),d.get('status','stocked'),d.get('quantity','')))
    conn.commit(); conn.close(); return jsonify({'success':True})

@app.route('/api/pantry/<int:pid>',methods=['PUT'])
def update_pantry(pid):
    d=request.json; conn=get_db()
    conn.execute("UPDATE pantry SET status=?,quantity=?,have_it=? WHERE id=?",
                 (d.get('status','stocked'),d.get('quantity',''),1 if d.get('status')!='out' else 0,pid))
    conn.commit(); conn.close(); return jsonify({'success':True})

@app.route('/api/pantry/<int:pid>',methods=['DELETE'])
def del_pantry(pid):
    conn=get_db(); conn.execute("DELETE FROM pantry WHERE id=?",(pid,)); conn.commit(); conn.close()
    return jsonify({'success':True})

@app.route('/api/custom_tags')
def get_custom_tags():
    conn=get_db()
    tags=[dict(t) for t in conn.execute("SELECT * FROM custom_tags ORDER BY name").fetchall()]
    conn.close(); return jsonify(tags)

@app.route('/api/custom_tags',methods=['POST'])
def create_custom_tag():
    d=request.json; conn=get_db(); c=conn.cursor()
    c.execute("INSERT OR REPLACE INTO custom_tags (name,color,icon) VALUES (?,?,?)",
              (d['name'],d.get('color','#e8a838'),d.get('icon','🏷')))
    tid=c.lastrowid; conn.commit(); conn.close(); return jsonify({'id':tid,'success':True})

@app.route('/api/custom_tags/<int:tid>',methods=['DELETE'])
def delete_custom_tag(tid):
    conn=get_db()
    tag=conn.execute("SELECT name FROM custom_tags WHERE id=?",(tid,)).fetchone()
    if tag:
        conn.execute("DELETE FROM tags WHERE tag_type='custom' AND tag_value=?",(tag['name'],))
    conn.execute("DELETE FROM custom_tags WHERE id=?",(tid,))
    conn.commit(); conn.close(); return jsonify({'success':True})

@app.route('/api/usda/search')
def usda_search():
    q=request.args.get('q',''); key=get_setting('usda_api_key','')
    if not key: return jsonify({'error':'No USDA API key. Go to Settings.'}),400
    try:
        resp=requests.get('https://api.nal.usda.gov/fdc/v1/foods/search',
            params={'query':q,'api_key':key,'pageSize':8,'dataType':'SR Legacy,Foundation,Branded'},timeout=8)
        foods=resp.json().get('foods',[])
        results=[]
        for f in foods:
            n={x['nutrientName']:x.get('value',0) for x in f.get('foodNutrients',[])}
            results.append({'fdcId':f['fdcId'],'description':f['description'],'brandOwner':f.get('brandOwner',''),
                'per100g':{'calories':n.get('Energy',n.get('Energy (Atwater General Factors)',0)),
                'protein':n.get('Protein',0),'carbs':n.get('Carbohydrate, by difference',0),
                'fat':n.get('Total lipid (fat)',0),'fiber':n.get('Fiber, total dietary',0),'sodium':n.get('Sodium, Na',0)}})
        return jsonify(results)
    except Exception as e: return jsonify({'error':str(e)}),500

@app.route('/api/settings')
def get_settings():
    conn=get_db(); rows=conn.execute("SELECT key,value FROM settings").fetchall(); conn.close()
    return jsonify({r['key']:r['value'] for r in rows})

@app.route('/api/settings',methods=['POST'])
def save_settings():
    conn=get_db()
    for k,v in request.json.items():
        conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",(k,v))
    conn.commit(); conn.close(); return jsonify({'success':True})

def get_setting(key,default=''):
    conn=get_db(); r=conn.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone(); conn.close()
    return r['value'] if r else default

def run_flask():
    app.run(port=5000,debug=False,use_reloader=False)

if __name__=='__main__':
    init_db(); seed_db()
    t=threading.Thread(target=run_flask,daemon=True); t.start()
    import time; time.sleep(1.2)
    try:
        import webview
        webview.create_window('LagomPrep','http://127.0.0.1:5000',width=1280,height=860,min_size=(960,640))
        webview.start()
    except ImportError:
        webbrowser.open('http://127.0.0.1:5000')
        input("Press Enter to quit...\n")
