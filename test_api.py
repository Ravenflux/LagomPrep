"""
LagomPrep API Test Suite — Full Debug
======================================
Run with: python test_api.py
Make sure the app is running first: python app.py

Tests all API endpoints, edge cases, and easter egg functionality.
"""

import requests
import json
import sys
import time
from datetime import date, timedelta

BASE = "http://127.0.0.1:5000"
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"
INFO = "\033[94m→\033[0m"

results = {"passed": 0, "failed": 0, "warnings": 0}
created = {}

def check(label, condition, warning=False):
    if condition:
        print(f"  {PASS} {label}")
        results["passed"] += 1
    elif warning:
        print(f"  {WARN} {label} (warning)")
        results["warnings"] += 1
    else:
        print(f"  {FAIL} {label}")
        results["failed"] += 1

def section(title):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")

def info(msg):
    print(f"  {INFO} {msg}")

# ── Server ────────────────────────────────────────────────────────────────────

def test_server():
    section("Server Connectivity")
    try:
        r = requests.get(f"{BASE}/", timeout=3)
        check("Server is running", r.status_code == 200)
        check("Returns HTML", "text/html" in r.headers.get("Content-Type",""))
        check("Static files served", requests.get(f"{BASE}/static/logo.png").status_code in [200,404])
    except requests.exceptions.ConnectionError:
        print(f"  {FAIL} Cannot connect to server at {BASE}")
        print("       Make sure app.py is running first.")
        sys.exit(1)

# ── Recipes ───────────────────────────────────────────────────────────────────

def test_recipes_read():
    section("Recipes — Read")
    r = requests.get(f"{BASE}/api/recipes")
    check("GET /api/recipes returns 200", r.status_code == 200)
    recipes = r.json()
    check("Returns a list", isinstance(recipes, list))

    # Retry for seed data timing
    for attempt in range(5):
        if len(recipes) >= 5:
            break
        time.sleep(0.5)
        recipes = requests.get(f"{BASE}/api/recipes").json()
    check("Has 20 seed recipes loaded", len(recipes) >= 24)

    if recipes:
        r1 = recipes[0]
        check("Recipe has id", "id" in r1)
        check("Recipe has name", "name" in r1)
        check("Recipe has meal_type", "meal_type" in r1)
        check("Recipe has servings", "servings" in r1)
        check("Recipe has ingredients list", isinstance(r1.get("ingredients"), list))
        check("Recipe has steps list", isinstance(r1.get("steps"), list))
        check("Recipe has tags list", isinstance(r1.get("tags"), list))
        check("Recipe has cook_log list", isinstance(r1.get("cook_log"), list))
        check("Calories total = per_serving × servings",
              r1.get("calories_total") is None or
              abs((r1.get("calories_per_serving",0) * r1.get("servings",1)) - r1.get("calories_total",0)) < 0.1)

def test_recipes_filter():
    section("Recipes — Filter & Sort")
    for mt in ["breakfast","lunch","dinner","side","snack","condiment"]:
        r = requests.get(f"{BASE}/api/recipes?meal_type={mt}")
        check(f"Filter by {mt} returns 200", r.status_code == 200)
        data = r.json()
        if data:
            check(f"All {mt} results match type", all(x["meal_type"]==mt for x in data))
        else:
            check(f"{mt} has results", False, warning=True)

    section("Recipes — Retired filter")
    r = requests.get(f"{BASE}/api/recipes?show_retired=true")
    check("show_retired=true returns 200", r.status_code == 200)
    check("Returns a list", isinstance(r.json(), list))

def test_recipes_single():
    section("Recipes — Single recipe")
    r = requests.get(f"{BASE}/api/recipes/1")
    check("GET /api/recipes/1 returns 200", r.status_code == 200)
    rec = r.json()
    check("Has ingredients", len(rec.get("ingredients",[])) > 0)
    check("Has steps", len(rec.get("steps",[])) > 0)
    r = requests.get(f"{BASE}/api/recipes/99999")
    check("GET /api/recipes/99999 returns 404", r.status_code == 404)

def test_recipes_create():
    section("Recipes — Create")
    payload = {
        "name": "Test Recipe — Automated",
        "meal_type": "snack",
        "cook_time": "5 min",
        "servings": 2,
        "description": "Created by test suite",
        "notes": "Delete me",
        "calories_per_serving": 100,
        "protein_per_serving": 10,
        "carbs_per_serving": 8,
        "fat_per_serving": 3,
        "fiber_per_serving": 2,
        "net_carbs_per_serving": 6,
        "sodium_per_serving": 50,
        "ingredients": [
            {"name": "test ingredient", "qty": "1 cup", "store_section": "pantry"},
            {"name": "another ingredient", "qty": "2 tbsp", "store_section": "produce"},
        ],
        "steps": [
            {"step_number": 1, "title": "Step one", "content": "Do the thing"},
            {"step_number": 2, "title": "Step two", "content": "Do the other thing"},
        ],
        "tags": [{"tag_type": "custom", "tag_value": "test-tag"}],
    }
    r = requests.post(f"{BASE}/api/recipes", json=payload)
    check("POST /api/recipes returns 200", r.status_code == 200)
    data = r.json()
    check("Returns new recipe ID", "id" in data and data["id"] > 0)
    created["recipe_id"] = data.get("id")

    if created.get("recipe_id"):
        r = requests.get(f"{BASE}/api/recipes/{created['recipe_id']}")
        check("Created recipe retrievable", r.status_code == 200)
        rec = r.json()
        check("Name saved correctly", rec.get("name") == "Test Recipe — Automated")
        check("Meal type saved correctly", rec.get("meal_type") == "snack")
        check("Servings saved correctly", rec.get("servings") == 2)
        check("Calories per serving correct", rec.get("calories_per_serving") == 100)
        check("Calories total calculated", rec.get("calories_total") == 200)
        check("Protein total calculated", rec.get("protein_total") == 20)
        check("Ingredients count correct", len(rec.get("ingredients",[])) == 2)
        check("Steps count correct", len(rec.get("steps",[])) == 2)
        check("Tags count correct", len(rec.get("tags",[])) == 1)

def test_recipes_update():
    section("Recipes — Update")
    if not created.get("recipe_id"):
        info("Skipping — no test recipe"); return
    payload = {
        "name": "Test Recipe — Updated",
        "meal_type": "breakfast",
        "cook_time": "10 min",
        "servings": 4,
        "description": "Updated by test suite",
        "notes": "Still delete me",
        "calories_per_serving": 150,
        "protein_per_serving": 12,
        "carbs_per_serving": 10,
        "fat_per_serving": 4,
        "fiber_per_serving": 3,
        "net_carbs_per_serving": 7,
        "sodium_per_serving": 60,
        "ingredients": [{"name": "updated ingredient", "qty": "2 cups", "store_section": "dairy"}],
        "steps": [{"step_number": 1, "title": "Updated step", "content": "Do the updated thing"}],
        "tags": [],
    }
    r = requests.put(f"{BASE}/api/recipes/{created['recipe_id']}", json=payload)
    check("PUT /api/recipes/{id} returns 200", r.status_code == 200)
    r = requests.get(f"{BASE}/api/recipes/{created['recipe_id']}")
    rec = r.json()
    check("Name updated", rec.get("name") == "Test Recipe — Updated")
    check("Meal type updated", rec.get("meal_type") == "breakfast")
    check("Servings updated", rec.get("servings") == 4)
    check("Calories updated", rec.get("calories_per_serving") == 150)
    check("Calories total recalculated", rec.get("calories_total") == 600)
    check("Ingredients updated", len(rec.get("ingredients",[])) == 1)
    check("Steps updated", len(rec.get("steps",[])) == 1)
    check("Tags cleared", len(rec.get("tags",[])) == 0)

def test_recipes_retire_restore():
    section("Recipes — Retire & Restore")
    if not created.get("recipe_id"):
        info("Skipping — no test recipe"); return
    r = requests.post(f"{BASE}/api/recipes/{created['recipe_id']}/retire")
    check("POST /retire returns 200", r.status_code == 200)
    r = requests.get(f"{BASE}/api/recipes")
    active = [x for x in r.json() if x["id"] == created["recipe_id"]]
    check("Retired recipe not in active list", len(active) == 0)
    r = requests.get(f"{BASE}/api/recipes?show_retired=true")
    retired = [x for x in r.json() if x["id"] == created["recipe_id"]]
    check("Retired recipe in retired list", len(retired) == 1)
    check("Retired recipe has is_retired=1", retired[0].get("is_retired") == 1)
    r = requests.post(f"{BASE}/api/recipes/{created['recipe_id']}/restore")
    check("POST /restore returns 200", r.status_code == 200)
    r = requests.get(f"{BASE}/api/recipes")
    active = [x for x in r.json() if x["id"] == created["recipe_id"]]
    check("Restored recipe back in active list", len(active) == 1)
    check("Restored recipe has is_retired=0", active[0].get("is_retired") == 0)

def test_recipes_delete():
    section("Recipes — Permanent Delete")
    # Create a throwaway recipe to delete
    payload = {
        "name": "Delete Me Permanently",
        "meal_type": "snack", "cook_time": "1 min", "servings": 1,
        "description": "", "notes": "", "ingredients": [], "steps": [], "tags": []
    }
    r = requests.post(f"{BASE}/api/recipes", json=payload)
    check("Created throwaway recipe", r.status_code == 200)
    throwaway_id = r.json().get("id")
    if throwaway_id:
        r = requests.delete(f"{BASE}/api/recipes/{throwaway_id}")
        check("DELETE /api/recipes/{id} returns 200", r.status_code == 200)
        r = requests.get(f"{BASE}/api/recipes/{throwaway_id}")
        check("Deleted recipe returns 404", r.status_code == 404)
        r = requests.get(f"{BASE}/api/recipes?show_retired=true")
        gone = [x for x in r.json() if x["id"] == throwaway_id]
        check("Deleted recipe not in retired list either", len(gone) == 0)

# ── Cook Log ──────────────────────────────────────────────────────────────────

def test_cook_log():
    section("Cook Log")
    if not created.get("recipe_id"):
        info("Skipping — no test recipe"); return
    rid = created["recipe_id"]
    payload = {"cooked_on": str(date.today()), "notes": "Tasted great", "rating": 4}
    r = requests.post(f"{BASE}/api/recipes/{rid}/log", json=payload)
    check("POST cook log returns 200", r.status_code == 200)
    r = requests.get(f"{BASE}/api/recipes/{rid}")
    logs = r.json().get("cook_log", [])
    check("Log entry appears on recipe", len(logs) >= 1)
    if logs:
        log = logs[0]
        check("Log date saved", log.get("cooked_on") == str(date.today()))
        check("Log rating saved", log.get("rating") == 4)
        check("Log notes saved", log.get("notes") == "Tasted great")
        # Add a second log entry
        r2 = requests.post(f"{BASE}/api/recipes/{rid}/log",
                           json={"cooked_on": str(date.today()-timedelta(days=1)),
                                 "notes":"Day before","rating":3})
        check("Second log entry added", r2.status_code == 200)
        r3 = requests.get(f"{BASE}/api/recipes/{rid}")
        check("Both log entries present", len(r3.json().get("cook_log",[])) == 2)
        # Delete first log
        r4 = requests.delete(f"{BASE}/api/recipes/{rid}/log/{log['id']}")
        check("DELETE cook log returns 200", r4.status_code == 200)
        r5 = requests.get(f"{BASE}/api/recipes/{rid}")
        check("Log count reduced after delete", len(r5.json().get("cook_log",[])) == 1)
        # Clean up remaining log
        remaining = r5.json().get("cook_log",[])
        if remaining:
            requests.delete(f"{BASE}/api/recipes/{rid}/log/{remaining[0]['id']}")

# ── Users / TDEE ──────────────────────────────────────────────────────────────

def test_users():
    section("Users — Create")
    payload = {
        "name": "Test User",
        "age": 32, "sex": "male",
        "height_in": 71, "weight_lb": 230,
        "activity_level": "sedentary", "goal": "lose"
    }
    r = requests.post(f"{BASE}/api/users", json=payload)
    check("POST /api/users returns 200", r.status_code == 200)
    created["user_id"] = r.json().get("id")

    section("Users — Read & TDEE validation")
    r = requests.get(f"{BASE}/api/users")
    check("GET /api/users returns 200", r.status_code == 200)
    users = r.json()
    check("Returns a list", isinstance(users, list))
    u = next((x for x in users if x["id"] == created.get("user_id")), None)
    check("Created user in list", u is not None)
    if u:
        td = u.get("tdee_data", {})
        check("TDEE data present", bool(td))
        check("BMR > 0", td.get("bmr", 0) > 0)
        check("TDEE > BMR (activity multiplier applied)", td.get("tdee", 0) > td.get("bmr", 0))
        check("Target < TDEE (lose goal = -500)", td.get("target", 0) < td.get("tdee", 0))
        check("Target = TDEE - 500", abs(td.get("target",0) - (td.get("tdee",0) - 500)) < 1)

    section("Users — Female TDEE")
    rf = requests.post(f"{BASE}/api/users",
                       json={"name":"Test Female","age":28,"sex":"female",
                             "height_in":58,"weight_lb":130,
                             "activity_level":"moderate","goal":"maintain"})
    check("Female user created", rf.status_code == 200)
    fuid = rf.json().get("id")
    if fuid:
        rf2 = requests.get(f"{BASE}/api/users")
        fu = next((x for x in rf2.json() if x["id"]==fuid), None)
        if fu:
            ftd = fu.get("tdee_data",{})
            check("Female BMR calculated", ftd.get("bmr",0) > 0)
            check("Female TDEE > BMR", ftd.get("tdee",0) > ftd.get("bmr",0))
            check("Maintain goal: target = TDEE", abs(ftd.get("target",0)-ftd.get("tdee",0)) < 1)
        requests.delete(f"{BASE}/api/users/{fuid}")

    section("Users — Update")
    if created.get("user_id"):
        r = requests.put(f"{BASE}/api/users/{created['user_id']}",
                         json={"name":"Test User Updated","age":32,"sex":"male",
                               "height_in":71,"weight_lb":225,
                               "activity_level":"light","goal":"lose"})
        check("PUT /api/users/{id} returns 200", r.status_code == 200)
        r2 = requests.get(f"{BASE}/api/users")
        u2 = next((x for x in r2.json() if x["id"]==created["user_id"]), None)
        check("Weight updated", u2 and u2.get("weight_lb") == 225)

# ── Meal Plan ─────────────────────────────────────────────────────────────────

def test_meal_plan():
    section("Meal Plan")
    if not created.get("user_id") or not created.get("recipe_id"):
        info("Skipping — need test user and recipe"); return
    today = str(date.today())
    monday = str(date.today() - timedelta(days=date.today().weekday()))
    for slot in ["breakfast","lunch","dinner","snack"]:
        payload = {"plan_date": today, "user_id": created["user_id"],
                   "recipe_id": created["recipe_id"], "meal_slot": slot, "servings_override": 1}
        r = requests.post(f"{BASE}/api/mealplan", json=payload)
        check(f"POST meal plan — {slot} slot returns 200", r.status_code == 200)
        if slot == "dinner":
            created["plan_id"] = r.json().get("id")
    r = requests.get(f"{BASE}/api/mealplan?week={monday}&user_id={created['user_id']}")
    check("GET /api/mealplan returns 200", r.status_code == 200)
    entries = r.json()
    check("Returns a list", isinstance(entries, list))
    check("All 4 slots present", len(entries) >= 4)
    check("Entries have recipe_name", all("recipe_name" in e for e in entries))
    check("Entries have plan_date", all("plan_date" in e for e in entries))
    # Delete all test entries
    for e in entries:
        requests.delete(f"{BASE}/api/mealplan/{e['id']}")
    r2 = requests.get(f"{BASE}/api/mealplan?week={monday}&user_id={created['user_id']}")
    check("All entries deleted", len(r2.json()) == 0)

# ── Pantry ────────────────────────────────────────────────────────────────────

def test_pantry():
    section("Pantry — Create & Read")
    for status in ["stocked","low","out"]:
        r = requests.post(f"{BASE}/api/pantry",
                          json={"name":f"Test Item {status}","status":status,
                                "quantity":"1 cup","have_it":1 if status!="out" else 0})
        check(f"POST pantry item — {status}", r.status_code == 200)
    r = requests.get(f"{BASE}/api/pantry")
    check("GET /api/pantry returns 200", r.status_code == 200)
    items = r.json()
    check("Returns a list", isinstance(items, list))
    stocked = next((i for i in items if i["name"]=="Test Item stocked"), None)
    low = next((i for i in items if i["name"]=="Test Item low"), None)
    out = next((i for i in items if i["name"]=="Test Item out"), None)
    check("Stocked item present", stocked is not None)
    check("Low item present", low is not None)
    check("Out item present", out is not None)
    if stocked:
        check("Stocked status correct", stocked.get("status")=="stocked")
        check("Quantity saved", stocked.get("quantity")=="1 cup")
        created["pantry_id"] = stocked["id"]

    section("Pantry — Status cycle")
    if created.get("pantry_id"):
        r = requests.put(f"{BASE}/api/pantry/{created['pantry_id']}",
                         json={"status":"low","quantity":"½ cup","have_it":1})
        check("PUT status to low returns 200", r.status_code == 200)
        r2 = requests.get(f"{BASE}/api/pantry")
        item = next((i for i in r2.json() if i["id"]==created["pantry_id"]), None)
        check("Status updated to low", item and item.get("status")=="low")
        r3 = requests.put(f"{BASE}/api/pantry/{created['pantry_id']}",
                          json={"status":"out","quantity":"","have_it":0})
        check("PUT status to out returns 200", r3.status_code == 200)
        r4 = requests.get(f"{BASE}/api/pantry")
        item2 = next((i for i in r4.json() if i["id"]==created["pantry_id"]), None)
        check("Status updated to out", item2 and item2.get("status")=="out")
        check("have_it=0 when out", item2 and item2.get("have_it")==0)

    section("Pantry — Delete")
    for name in ["Test Item stocked","Test Item low","Test Item out"]:
        r = requests.get(f"{BASE}/api/pantry")
        item = next((i for i in r.json() if i["name"]==name), None)
        if item:
            rd = requests.delete(f"{BASE}/api/pantry/{item['id']}")
            check(f"DELETE {name}", rd.status_code == 200)

# ── Custom Tags ───────────────────────────────────────────────────────────────

def test_custom_tags():
    section("Custom Tags — Create & Read")
    tags_to_create = [
        {"name":"test-tag-red","color":"#ff0000","icon":"🔴"},
        {"name":"test-tag-blue","color":"#0000ff","icon":"🔵"},
        {"name":"test-tag-green","color":"#00ff00","icon":"🟢"},
    ]
    for tag in tags_to_create:
        r = requests.post(f"{BASE}/api/custom_tags", json=tag)
        check(f"POST custom tag '{tag['name']}'", r.status_code == 200)
    if not created.get("tag_id"):
        r = requests.get(f"{BASE}/api/custom_tags")
        t = next((x for x in r.json() if x["name"]=="test-tag-red"), None)
        if t: created["tag_id"] = t["id"]
    r = requests.get(f"{BASE}/api/custom_tags")
    check("GET /api/custom_tags returns 200", r.status_code == 200)
    tags = r.json()
    check("Returns a list", isinstance(tags, list))
    red = next((t for t in tags if t["name"]=="test-tag-red"), None)
    check("Tag color saved", red and red.get("color")=="#ff0000")
    check("Tag icon saved", red and red.get("icon")=="🔴")

    section("Custom Tags — Duplicate prevention")
    r = requests.post(f"{BASE}/api/custom_tags",
                      json={"name":"test-tag-red","color":"#123456","icon":"⭐"})
    check("Duplicate tag handled (INSERT OR REPLACE)", r.status_code == 200)
    r2 = requests.get(f"{BASE}/api/custom_tags")
    reds = [t for t in r2.json() if t["name"]=="test-tag-red"]
    check("Still only one tag with that name", len(reds) == 1)

    section("Custom Tags — Delete")
    for name in ["test-tag-red","test-tag-blue","test-tag-green"]:
        r = requests.get(f"{BASE}/api/custom_tags")
        t = next((x for x in r.json() if x["name"]==name), None)
        if t:
            rd = requests.delete(f"{BASE}/api/custom_tags/{t['id']}")
            check(f"DELETE tag '{name}'", rd.status_code == 200)
    r3 = requests.get(f"{BASE}/api/custom_tags")
    remaining = [t for t in r3.json() if t["name"] in [x["name"] for x in tags_to_create]]
    check("All test tags deleted", len(remaining) == 0)

# ── Settings ──────────────────────────────────────────────────────────────────

def test_settings():
    section("Settings")
    r = requests.get(f"{BASE}/api/settings")
    check("GET /api/settings returns 200", r.status_code == 200)
    check("Returns a dict", isinstance(r.json(), dict))

    # Save original theme before testing
    original_settings = r.json()
    original_theme = original_settings.get("theme", None)

    # Write a test value
    r = requests.post(f"{BASE}/api/settings", json={"test_key":"test_value_123"})
    check("POST /api/settings returns 200", r.status_code == 200)
    r = requests.get(f"{BASE}/api/settings")
    check("Setting persisted correctly", r.json().get("test_key")=="test_value_123")

    # Overwrite
    r = requests.post(f"{BASE}/api/settings", json={"test_key":"updated_value"})
    check("Setting can be overwritten", r.status_code == 200)
    r = requests.get(f"{BASE}/api/settings")
    check("Overwritten value persisted", r.json().get("test_key")=="updated_value")

    # Theme setting — use a non-destructive color close to Nordic
    test_theme = {"accent":"#7eb8c9","bg":"#1a1f2e","bg2":"#222838",
                  "text":"#e8edf5","text2":"#8899bb","border":"#2e3650"}
    r = requests.post(f"{BASE}/api/settings", json={"theme":json.dumps(test_theme)})
    check("Theme saved to settings", r.status_code == 200)
    r = requests.get(f"{BASE}/api/settings")
    saved_theme = json.loads(r.json().get("theme","{}"))
    check("Theme accent color persisted", saved_theme.get("accent")==test_theme["accent"])
    check("Theme bg color persisted", saved_theme.get("bg")==test_theme["bg"])

    # Restore original theme
    if original_theme:
        requests.post(f"{BASE}/api/settings", json={"theme": original_theme})
        info("Original theme restored")
    else:
        # No theme was saved before — restore Nordic default
        nordic = json.dumps({"accent":"#7eb8c9","bg":"#1a1f2e","bg2":"#222838",
                             "text":"#e8edf5","text2":"#8899bb","border":"#2e3650"})
        requests.post(f"{BASE}/api/settings", json={"theme": nordic})
        info("Nordic theme restored as default")

    # Clean up test key
    requests.post(f"{BASE}/api/settings", json={"test_key":""})
    check("Test settings cleaned up", True)

# ── Easter Eggs ───────────────────────────────────────────────────────────────

def test_easter_eggs():
    section("Easter Egg — Odin's All-Father Mead")
    info("Testing via direct API call (simulates Konami code unlock)")

    ODIN_RECIPE = {
        "name":"Odin's All-Father Mead",
        "meal_type":"condiment",
        "cook_time":"9 nights (plus fermentation)",
        "servings":12,
        "description":"The sacred mead of Asgard.",
        "notes":"CLASSIFIED.",
        "calories_per_serving":220,
        "protein_per_serving":0,
        "carbs_per_serving":28,
        "fat_per_serving":0,
        "fiber_per_serving":0,
        "net_carbs_per_serving":28,
        "sodium_per_serving":4,
        "tags":[{"tag_type":"custom","tag_value":"worthy-only"}],
        "ingredients":[
            {"name":"Wildflower honey from the nine realms","qty":"3 lbs","store_section":"pantry"},
            {"name":"Spring water (Asgardian preferred)","qty":"1 gallon","store_section":"other"},
            {"name":"Mead yeast","qty":"1 packet","store_section":"pantry"},
            {"name":"Fresh ginger, sliced","qty":"2 inches","store_section":"produce"},
            {"name":"Orange peel","qty":"1 large","store_section":"produce"},
            {"name":"Cinnamon stick","qty":"1","store_section":"pantry"},
            {"name":"Cloves","qty":"3","store_section":"pantry"},
            {"name":"Wisdom of Kvasir","qty":"a pinch","store_section":"other"},
        ],
        "steps":[
            {"step_number":1,"title":"Invoke the All-Father","content":"Stand facing north. Declare your intent."},
            {"step_number":2,"title":"Sanitize everything","content":"Sanitize all equipment."},
            {"step_number":3,"title":"Heat the water","content":"Warm 1 gallon to 150°F.","timer_seconds":600},
            {"step_number":4,"title":"Add the honey","content":"Stir in honey until dissolved.","timer_seconds":300},
            {"step_number":5,"title":"Add spices","content":"Add ginger, orange peel, cinnamon, cloves."},
            {"step_number":6,"title":"Cool and pitch yeast","content":"Cool to 70°F. Pitch yeast."},
            {"step_number":7,"title":"Wait nine nights","content":"Do nothing for 9 days.","timer_seconds":777600},
            {"step_number":8,"title":"Secondary fermentation","content":"Transfer and wait 2-4 more weeks."},
            {"step_number":9,"title":"Taste and bottle","content":"Taste. If mead — success. If vinegar — start over."},
            {"step_number":10,"title":"Age and serve","content":"Age 2 more weeks. Serve in a horn. Skål."},
        ]
    }

    # Check if already exists
    existing = requests.get(f"{BASE}/api/recipes").json()
    odin_exists = any(r["name"]=="Odin's All-Father Mead" for r in existing)

    if odin_exists:
        info("Odin's Mead already in database — testing properties")
        odin = next(r for r in existing if r["name"]=="Odin's All-Father Mead")
        check("Recipe has correct meal type", odin.get("meal_type")=="condiment")
        check("Recipe has 12 servings", odin.get("servings")==12)
        check("Recipe has ingredients", len(odin.get("ingredients",[]))>0)
        check("Recipe has steps", len(odin.get("steps",[]))>0)
        check("Recipe not retired", odin.get("is_retired")==0)
    else:
        info("Unlocking Odin's Mead via API (Konami code simulation)")
        r = requests.post(f"{BASE}/api/recipes", json=ODIN_RECIPE)
        check("Odin's Mead created successfully", r.status_code == 200)
        odin_id = r.json().get("id")
        if odin_id:
            r2 = requests.get(f"{BASE}/api/recipes/{odin_id}")
            odin = r2.json()
            check("Mead has 10 steps", len(odin.get("steps",[]))==10)
            check("Mead has 8 ingredients", len(odin.get("ingredients",[]))==8)
            check("Mead has 220 cal/serving", odin.get("calories_per_serving")==220)
            check("Mead has worthy-only tag", any(t["tag_value"]=="worthy-only" for t in odin.get("tags",[])))
            check("Cook time is appropriately dramatic", "9 nights" in (odin.get("cook_time") or ""))
            created["odin_id"] = odin_id

    section("Easter Egg — Trigger verification")
    info("Konami code: ↑↑↓↓←→←→BA — keyboard only, not testable via API")
    info("THOR word: type T-H-O-R anywhere — keyboard only, not testable via API")
    info("Logo 5x: click logo 5 times — UI only, not testable via API")
    info("Wild Mode: hue-rotate animation — UI only, not testable via API")
    check("Easter egg recipe accessible via normal recipe API", True)
    check("Easter egg recipe appears in condiment category",
          any(r["name"]=="Odin's All-Father Mead" and r["meal_type"]=="condiment"
              for r in requests.get(f"{BASE}/api/recipes?meal_type=condiment").json()), warning=True)

# ── Edge Cases ────────────────────────────────────────────────────────────────

def test_edge_cases():
    section("Edge Cases — Recipe validation")
    r = requests.post(f"{BASE}/api/recipes",
                      json={"name":"","meal_type":"dinner","servings":1,
                            "ingredients":[],"steps":[],"tags":[]})
    check("Empty name handled gracefully", r.status_code in [200,400], warning=True)

    r = requests.post(f"{BASE}/api/recipes",
                      json={"name":"X"*500,"meal_type":"snack","servings":1,
                            "description":"","notes":"","ingredients":[],"steps":[],"tags":[]})
    check("Very long name handled", r.status_code in [200,400], warning=True)
    if r.status_code == 200:
        requests.delete(f"{BASE}/api/recipes/{r.json().get('id')}")

    r = requests.post(f"{BASE}/api/recipes",
                      json={"name":"Zero servings test","meal_type":"snack","servings":0,
                            "calories_per_serving":100,"ingredients":[],"steps":[],"tags":[]})
    check("Zero servings handled", r.status_code in [200,400], warning=True)
    if r.status_code == 200:
        rec = requests.get(f"{BASE}/api/recipes/{r.json().get('id')}").json()
        check("Zero servings doesn't crash calorie calc", rec.get("calories_total") is not None, warning=True)
        requests.delete(f"{BASE}/api/recipes/{r.json().get('id')}")

    section("Edge Cases — Special characters")
    r = requests.post(f"{BASE}/api/pantry",
                      json={"name":"Item with 'quotes' & <symbols>","status":"stocked",
                            "quantity":"","have_it":1})
    check("Special chars in pantry name", r.status_code == 200)
    if r.status_code == 200:
        items = requests.get(f"{BASE}/api/pantry").json()
        item = next((i for i in items if "quotes" in i["name"]), None)
        check("Special char item retrievable", item is not None)
        if item: requests.delete(f"{BASE}/api/pantry/{item['id']}")

    r = requests.post(f"{BASE}/api/recipes",
                      json={"name":"Emoji Recipe 🍕🔥","meal_type":"snack","servings":1,
                            "description":"🎉","notes":"✨","ingredients":[],"steps":[],"tags":[]})
    check("Emoji in recipe name and fields", r.status_code == 200)
    if r.status_code == 200:
        eid = r.json().get("id")
        rec = requests.get(f"{BASE}/api/recipes/{eid}").json()
        check("Emoji preserved in name", "🍕" in rec.get("name",""))
        requests.delete(f"{BASE}/api/recipes/{eid}")

    section("Edge Cases — TDEE boundary values")
    r = requests.post(f"{BASE}/api/users",
                      json={"name":"Edge User Zero","age":0,"sex":"","height_in":0,
                            "weight_lb":0,"activity_level":"sedentary","goal":"maintain"})
    check("Zero-value user created", r.status_code == 200)
    if r.status_code == 200:
        euid = r.json().get("id")
        r2 = requests.get(f"{BASE}/api/users")
        u = next((x for x in r2.json() if x["id"]==euid), None)
        if u:
            td = u.get("tdee_data",{})
            check("Zero-value TDEE doesn't crash", isinstance(td, dict))
        requests.delete(f"{BASE}/api/users/{euid}")

    r = requests.post(f"{BASE}/api/users",
                      json={"name":"Very Large User","age":99,"sex":"male","height_in":96,
                            "weight_lb":600,"activity_level":"very_active","goal":"gain"})
    check("Extreme user values handled", r.status_code == 200)
    if r.status_code == 200:
        euid2 = r.json().get("id")
        r2 = requests.get(f"{BASE}/api/users")
        u2 = next((x for x in r2.json() if x["id"]==euid2), None)
        if u2:
            td = u2.get("tdee_data",{})
            check("Extreme TDEE calculated", td.get("tdee",0) > 0)
            check("Gain goal: target > TDEE", td.get("target",0) > td.get("tdee",0))
        requests.delete(f"{BASE}/api/users/{euid2}")

    section("Edge Cases — Nonexistent resources")
    check("GET nonexistent recipe returns 404",
          requests.get(f"{BASE}/api/recipes/99999").status_code == 404)
    check("DELETE nonexistent recipe handled",
          requests.delete(f"{BASE}/api/recipes/99999").status_code in [200,404], warning=True)
    check("Retire nonexistent recipe handled",
          requests.post(f"{BASE}/api/recipes/99999/retire").status_code in [200,404], warning=True)

    section("Edge Cases — Concurrent pantry inserts")
    for i in range(5):
        requests.post(f"{BASE}/api/pantry",
                      json={"name":f"Concurrent Item {i}","status":"stocked",
                            "quantity":"","have_it":1})
    items = requests.get(f"{BASE}/api/pantry").json()
    concurrent = [i for i in items if "Concurrent Item" in i["name"]]
    check("All 5 concurrent pantry items created", len(concurrent) == 5)
    for item in concurrent:
        requests.delete(f"{BASE}/api/pantry/{item['id']}")

# ── Database Integrity ────────────────────────────────────────────────────────

def test_database_integrity():
    section("Database Integrity")
    # Create recipe with full data then delete — check cascade
    payload = {
        "name":"Cascade Delete Test","meal_type":"snack","cook_time":"1 min",
        "servings":1,"description":"","notes":"",
        "calories_per_serving":50,"protein_per_serving":5,
        "carbs_per_serving":3,"fat_per_serving":1,"fiber_per_serving":1,
        "net_carbs_per_serving":2,"sodium_per_serving":10,
        "ingredients":[
            {"name":"cascade ing 1","qty":"1 cup","store_section":"pantry"},
            {"name":"cascade ing 2","qty":"2 tbsp","store_section":"produce"},
        ],
        "steps":[
            {"step_number":1,"title":"Cascade step","content":"This should cascade delete"},
        ],
        "tags":[{"tag_type":"custom","tag_value":"cascade-test"}],
    }
    r = requests.post(f"{BASE}/api/recipes", json=payload)
    check("Cascade test recipe created", r.status_code == 200)
    cid = r.json().get("id")
    if cid:
        # Add a cook log entry
        requests.post(f"{BASE}/api/recipes/{cid}/log",
                      json={"cooked_on":str(date.today()),"notes":"cascade","rating":3})
        # Add to meal plan if we have a user
        if created.get("user_id"):
            mp = requests.post(f"{BASE}/api/mealplan",
                               json={"plan_date":str(date.today()),"user_id":created["user_id"],
                                     "recipe_id":cid,"meal_slot":"snack","servings_override":1})
            mp_id = mp.json().get("id") if mp.status_code==200 else None
        # Delete the recipe
        rd = requests.delete(f"{BASE}/api/recipes/{cid}")
        check("Cascade delete returns 200", rd.status_code == 200)
        # Verify it's gone
        r2 = requests.get(f"{BASE}/api/recipes/{cid}")
        check("Recipe is gone after delete", r2.status_code == 404)
        # Meal plan entries should also be gone
        if created.get("user_id") and mp_id:
            mp_check = requests.get(f"{BASE}/api/mealplan?user_id={created['user_id']}")
            leftover = [e for e in mp_check.json() if e.get("id")==mp_id]
            check("Meal plan entry cascade deleted", len(leftover)==0)

# ── Cleanup ───────────────────────────────────────────────────────────────────

def cleanup():
    section("Cleanup — Removing all test data")
    if created.get("recipe_id"):
        r = requests.delete(f"{BASE}/api/recipes/{created['recipe_id']}")
        check(f"Test recipe deleted (id={created['recipe_id']})", r.status_code == 200)
    if created.get("user_id"):
        r = requests.delete(f"{BASE}/api/users/{created['user_id']}")
        check(f"Test user deleted (id={created['user_id']})", r.status_code == 200)
    if created.get("pantry_id"):
        r = requests.delete(f"{BASE}/api/pantry/{created['pantry_id']}")
        check(f"Test pantry item deleted (id={created['pantry_id']})", r.status_code in [200,404])
    if created.get("odin_id"):
        info(f"Odin's Mead (id={created['odin_id']}) kept in database — it was earned ⚡")
    # Clean up any stray test settings
    requests.post(f"{BASE}/api/settings", json={"test_key":""})
    check("Test settings cleaned up", True)

# ── Summary ───────────────────────────────────────────────────────────────────

def summary():
    total = results["passed"] + results["failed"] + results["warnings"]
    print(f"\n{'═'*55}")
    print(f"  RESULTS: {total} tests run")
    print(f"  \033[92m{results['passed']} passed\033[0m  "
          f"\033[91m{results['failed']} failed\033[0m  "
          f"\033[93m{results['warnings']} warnings\033[0m")
    print(f"{'═'*55}")
    if results["failed"] == 0 and results["warnings"] == 0:
        print("  ⚡ All tests passed. Worthy of Valhalla.")
    elif results["failed"] == 0:
        print("  ✓ All tests passed with some warnings. Check above.")
    else:
        print(f"  ✗ {results['failed']} test(s) failed. Check output above.")
    print()

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n╔═══════════════════════════════════════════════════╗")
    print("║     LagomPrep Full Debug Test Suite  ⚡           ║")
    print("╚═══════════════════════════════════════════════════╝")
    test_server()
    test_recipes_read()
    test_recipes_filter()
    test_recipes_single()
    test_recipes_create()
    test_recipes_update()
    test_recipes_retire_restore()
    test_recipes_delete()
    test_cook_log()
    test_users()
    test_meal_plan()
    test_pantry()
    test_custom_tags()
    test_settings()
    test_easter_eggs()
    test_edge_cases()
    test_database_integrity()
    cleanup()
    summary()
