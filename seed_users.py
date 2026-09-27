import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# ============================================================
# ALL EMPLOYEES (DEPARTMENTS + DISCIPLINES ALIGNED)
# ============================================================
# department = القسم الرئيسي (Design, Supervision, Management, Finance)
# discipline = التخصص الدقيق (Civil, Structural, Architect, Electrical, Mechanical, Planner, DC, General)
# ============================================================

employees = [
    # ========================================================
    # MANAGEMENT
    # ========================================================
    {'username': 'nasser.tabouni', 'password': 'Admin@123', 'role': 'GM', 'department': 'Management', 'discipline': 'Architect', 'first_name': 'Nasser', 'last_name': 'Tabouni'},
    {'username': 'nisreen.tabouni', 'password': 'Admin@123', 'role': 'AGM', 'department': 'Management', 'discipline': 'Architect', 'first_name': 'Nisreen', 'last_name': 'Tabouni'},
    {'username': 'mohammad.fahmi', 'password': 'Admin@123', 'role': 'DESIGN_MGR', 'department': 'Design', 'discipline': 'Architect', 'first_name': 'Mohammad', 'last_name': 'Fahmi'},

    # ========================================================
    # SUPERVISION MANAGEMENT
    # ========================================================
    {'username': 'ahmed.zabady', 'password': 'Admin@123', 'role': 'SUP_MGR', 'department': 'Supervision', 'discipline': 'Civil', 'first_name': 'Ahmed', 'last_name': 'Zabady'},

    # ========================================================
    # DESIGN ENGINEERS
    # ========================================================
    {'username': 'salah.ahmad', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Design', 'discipline': 'Architect', 'first_name': 'Salah', 'last_name': 'Ahmad'},
    {'username': 'basem.taha', 'password': 'Eng@123', 'role': 'SENIOR_ENG', 'department': 'Design', 'discipline': 'Architect', 'first_name': 'Basem', 'last_name': 'Taha'},
    {'username': 'vicky.jr', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Design', 'discipline': 'Structural', 'first_name': 'Vicky', 'last_name': 'JR'},
    {'username': 'mohammad.mostafa', 'password': 'Eng@123', 'role': 'SENIOR_ENG', 'department': 'Design', 'discipline': 'Structural', 'first_name': 'Mohammad', 'last_name': 'Mostafa'},
    {'username': 'mohammad.alqadi', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Design', 'discipline': 'Structural', 'first_name': 'Mohammad', 'last_name': 'Al-Qadi'},
    {'username': 'mahmoud.aldemyati', 'password': 'Eng@123', 'role': 'SENIOR_ENG', 'department': 'Design', 'discipline': 'Electrical', 'first_name': 'Mahmoud', 'last_name': 'Al-Demyati'},
    {'username': 'abdulhamid.ahmad', 'password': 'Eng@123', 'role': 'SENIOR_ENG', 'department': 'Design', 'discipline': 'Mechanical', 'first_name': 'Abdulhamid', 'last_name': 'Ahmad'},
    {'username': 'jan.bina', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Design', 'discipline': 'Architect', 'first_name': 'Jan', 'last_name': 'Bina'},
    {'username': 'shaaban.karam', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Design', 'discipline': 'Architect', 'first_name': 'Shaaban', 'last_name': 'Karam'},
    {'username': 'basel.shaat', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Design', 'discipline': 'Architect', 'first_name': 'Basel', 'last_name': 'Shaat'},
    {'username': 'israa.omran', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Design', 'discipline': 'Architect', 'first_name': 'Israa', 'last_name': 'Omran'},
    {'username': 'ahmad.alqadi', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Design', 'discipline': 'Structural', 'first_name': 'Ahmad', 'last_name': 'Al-Qadi'},
    {'username': 'yousef.amro', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Design', 'discipline': 'Mechanical', 'first_name': 'Yousef', 'last_name': 'Amro'},

    # ========================================================
    # DESIGN DRAFTSMEN
    # ========================================================
    {'username': 'salman.saeed', 'password': 'Eng@123', 'role': 'DRAFTSMAN', 'department': 'Design', 'discipline': 'General', 'first_name': 'Salman', 'last_name': 'Saeed'},  # كهرباء+ميكانيك+معماري
    {'username': 'shahajan.puthi', 'password': 'Eng@123', 'role': 'DRAFTSMAN', 'department': 'Design', 'discipline': 'Architect', 'first_name': 'Shahajan', 'last_name': 'Puthi'},
    {'username': 'mohammad.raheem', 'password': 'Eng@123', 'role': 'DRAFTSMAN', 'department': 'Design', 'discipline': 'Mechanical', 'first_name': 'Mohammad', 'last_name': 'Raheem'},
    {'username': 'mohammad.lebbe', 'password': 'Eng@123', 'role': 'DRAFTSMAN', 'department': 'Design', 'discipline': 'Mechanical', 'first_name': 'Mohammad', 'last_name': 'Lebbe'},
    {'username': 'shammer.pareeth', 'password': 'Eng@123', 'role': 'DRAFTSMAN', 'department': 'Design', 'discipline': 'Electrical', 'first_name': 'Shammer', 'last_name': 'Pareeth'},
    {'username': 'mojib.rahiman', 'password': 'Eng@123', 'role': 'DRAFTSMAN', 'department': 'Design', 'discipline': 'Architect', 'first_name': 'Mojib', 'last_name': 'Rahiman'},
    {'username': 'md.hossain', 'password': 'Eng@123', 'role': 'DRAFTSMAN', 'department': 'Design', 'discipline': 'Architect', 'first_name': 'Md', 'last_name': 'Hossain'},

    # ======================================================== 
    # DESIGN SECRETARY
    # ========================================================
    {'username': 'mildred.barrion', 'password': 'Sec@123', 'role': 'SECRETARY', 'department': 'Design', 'discipline': 'Secretary', 'first_name': 'Mildred', 'last_name': 'Barrion'},

    # ========================================================
    # MANAGEMENT SECRETARY
    # ========================================================
    {'username': 'linda.ashraf', 'password': 'Sec@123', 'role': 'SECRETARY', 'department': 'Management', 'discipline': 'Secretary', 'first_name': 'Linda', 'last_name': 'Ashraf'},

    # ========================================================
    # ACCOUNTANT
    # ========================================================
    {'username': 'mohammad.mishab', 'password': 'Fin@123', 'role': 'ACCOUNTANT', 'department': 'Finance', 'discipline': 'Finance', 'first_name': 'Mohammad', 'last_name': 'Mishab'},

    # ========================================================
    # SUPERVISION - CIVIL (13)
    # ========================================================
    {'username': 'nader.bekhit', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Civil', 'first_name': 'Nader', 'last_name': 'Bekhit'},
    {'username': 'syed.mahmoud', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Civil', 'first_name': 'Syed', 'last_name': 'Mahmoud'},
    {'username': 'muhammed.faisal', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Civil', 'first_name': 'Muhammed', 'last_name': 'Faisal'},
    {'username': 'eslam.mahdy', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Civil', 'first_name': 'Eslam', 'last_name': 'Mahdy'},
    {'username': 'ahmed.yosef', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Civil', 'first_name': 'Ahmed', 'last_name': 'Yosef'},
    {'username': 'saheer.parayil', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Civil', 'first_name': 'Saheer', 'last_name': 'Parayil'},
    {'username': 'mahmoud.hamed', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Civil', 'first_name': 'Mahmoud', 'last_name': 'Hamed'},
    {'username': 'waled.mohamed', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Civil', 'first_name': 'Waled', 'last_name': 'Mohamed'},
    {'username': 'ahmed.zaki', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Civil', 'first_name': 'Ahmed', 'last_name': 'Zaki'},
    {'username': 'mohamed.salah', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Civil', 'first_name': 'Mohamed', 'last_name': 'Salah'},
    {'username': 'loai.hamouda', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Civil', 'first_name': 'Loai', 'last_name': 'Hamouda'},
    {'username': 'mohamed.elshenawy', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Civil', 'first_name': 'Mohamed', 'last_name': 'Elshenawy'},

    # ========================================================
    # SUPERVISION - ELECTRICAL (4)
    # ========================================================
    {'username': 'ahmed.ghazy', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Electrical', 'first_name': 'Ahmed', 'last_name': 'Ghazy'},
    {'username': 'muammer.muhammed', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Electrical', 'first_name': 'Muammer', 'last_name': 'Muhammed'},
    {'username': 'abdulrahim.ahmed', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Electrical', 'first_name': 'Abdul Rahim', 'last_name': 'Ahmed'},
    {'username': 'ali.odeh', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Electrical', 'first_name': 'Ali', 'last_name': 'Odeh'},

    # ========================================================
    # SUPERVISION - MECHANICAL (3)
    # ========================================================
    {'username': 'noufal.thodi', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Mechanical', 'first_name': 'Noufal', 'last_name': 'Thodi'},
    {'username': 'mohammed.shemseer', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Mechanical', 'first_name': 'Mohammed', 'last_name': 'Shemseer'},
    {'username': 'mohammed.rashid', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Mechanical', 'first_name': 'Mohammed', 'last_name': 'Rashid'},

    # ========================================================
    # SUPERVISION - ARCHITECT (2)
    # ========================================================
    {'username': 'mohamed.hisham', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Architect', 'first_name': 'Mohamed', 'last_name': 'Hisham'},
    {'username': 'mohamed.salem', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Architect', 'first_name': 'Mohamed', 'last_name': 'Salem'},

    # ========================================================
    # SUPERVISION - PLANNER (1)
    # ========================================================
    {'username': 'mani.kumar', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'Planner', 'first_name': 'Mani', 'last_name': 'Kumar'},

    # ========================================================
    # SUPERVISION - DC (6)
    # ========================================================
    {'username': 'jocelyn.mallilin', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'DC', 'first_name': 'Jocelyn', 'last_name': 'Mallilin'},
    {'username': 'allen.guanzon', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'DC', 'first_name': 'Allen', 'last_name': 'Guanzon'},
    {'username': 'jason.cuison', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'DC', 'first_name': 'Jason', 'last_name': 'Cuison'},
    {'username': 'mostafa.zabady', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'DC', 'first_name': 'Mostafa', 'last_name': 'Zabady'},
    {'username': 'isuru.palliyaguruge', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'DC', 'first_name': 'Isuru', 'last_name': 'Palliyaguruge'},
    {'username': 'faseela.foroth', 'password': 'Eng@123', 'role': 'ENGINEER', 'department': 'Supervision', 'discipline': 'DC', 'first_name': 'Faseela', 'last_name': 'Foroth'},

    # ========================================================
    # SUPERVISION SECRETARY
    # ========================================================
    {'username': 'joy.malilen', 'password': 'Sec@123', 'role': 'SECRETARY', 'department': 'Supervision', 'discipline': 'Secretary', 'first_name': 'Joy', 'last_name': 'Malilen'},
]


# ============================================================
# VALIDATE ROLES BEFORE CREATING USERS
# ============================================================

valid_roles = {choice[0] for choice in User.Role.choices}

print("=" * 70)
print("Checking employee roles...")
print("=" * 70)

invalid_roles = []
for emp in employees:
    if emp['role'] not in valid_roles:
        invalid_roles.append((emp['username'], emp['role']))

if invalid_roles:
    print("❌ Invalid roles found:")
    for username, role in invalid_roles:
        print(f"   {username} -> {role}")
    raise ValueError("Some employees have roles that do not exist in User.Role.choices")

print("✅ All roles are valid.")


# ============================================================
# DELETE EXISTING USERS (CLEAN SLATE)
# ============================================================
print("=" * 70)
print("🗑️  Deleting all existing users to ensure a clean seed...")
print("=" * 70)
deleted_count, _ = User.objects.all().delete()
print(f"✅ Successfully deleted {deleted_count} existing users.")


# ============================================================
# CREATE USERS
# ============================================================

print("=" * 70)
print("Starting to seed users...")
print("=" * 70)

created_count = 0

for emp in employees:
    User.objects.create_user(
        username=emp['username'],
        password=emp['password'],
        role=emp['role'],
        department=emp['department'],
        discipline=emp['discipline'],   # ✅ الحقل الجديد
        first_name=emp['first_name'],
        last_name=emp['last_name'],
        email=f"{emp['username']}@company.com"
    )
    created_count += 1
    print(f"✅ Created: {emp['username'].ljust(25)} | {emp['role'].ljust(12)} | Dept: {emp['department'].ljust(12)} | Discipline: {emp['discipline']}")


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("SEED COMPLETED SUCCESSFULLY")
print("=" * 70)
print(f"Total employees seeded : {created_count}")
print("=" * 70)

# إحصائيات الأقسام والتخصصات
from collections import Counter
dept_count = Counter(emp['department'] for emp in employees)
disc_count = Counter(emp['discipline'] for emp in employees)

print("📊 Department Breakdown:")
for dept, count in dept_count.most_common():
    print(f"   {dept}: {count}")

print("\n📊 Discipline Breakdown:")
for disc, count in disc_count.most_common():
    print(f"   {disc}: {count}")

print("\n" + "=" * 70)
print("⚠️  REMINDER: Update hardcoded username lists in models.py if changed!")
print("=" * 70)