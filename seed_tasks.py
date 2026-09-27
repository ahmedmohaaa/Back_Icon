from erp.models import Task, Project, DisciplineItem
from django.contrib.auth import get_user_model

User = get_user_model()

def run_lifecycle_test():
    # --- خطوة تنظيف اختيارية ---
    # مسح المهام التي تم إنشاؤها بالخطأ مسبقاً (التي تبدأ بـ Auto Test Task)
    deleted_count, _ = Task.objects.filter(title__startswith='Auto Test Task').delete()
    if deleted_count > 0:
        print(f"🧹 Cleaned up {deleted_count} mistakenly created tasks.")

    # 1. تحديد المشروع بناءً على الـ ID رقم 2 (كما في الصورة)
    try:
        project = Project.objects.get(id=2)
    except Project.DoesNotExist:
        print("❌ Error: Project with ID 2 not found.")
        return
    
    # 2. تحديد المهندس
    engineer = User.objects.filter(role__in=['ENGINEER', 'SENIOR_ENG', 'PM']).first()
    
    if not engineer:
        print("❌ Error: No Engineer found in the database.")
        return

    # 3. جلب التخصصات
    disciplines = DisciplineItem.objects.filter(is_active=True)[:31]
    
    if disciplines.count() == 0:
        print("❌ Error: No active disciplines found.")
        return

    print(f"🚀 Starting creation of {disciplines.count()} tasks for Project: {project.name} (ID: {project.id})...")

    # 4. الدوران لإنشاء المهام
    tasks_created = 0
    for disc in disciplines:
        task = Task.objects.create(
            task_type='MAIN_DESIGN',
            project=project,
            stage=disc.stage,
            discipline=disc,
            title=f'Auto Test Task - {disc.name}',
            assigned_to=engineer,
            priority='MEDIUM',
            duration_days=2,
            progress_percentage=100,
            status='APPROVED' 
        )
        tasks_created += 1
        print(f"✅ Created & Approved: {task.title} (Stage: {task.stage})")

    print(f"🎉 Success: {tasks_created} tasks have been successfully created for {project.name}!")

# تشغيل الدالة
run_lifecycle_test()