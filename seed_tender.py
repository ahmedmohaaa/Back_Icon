from erp.models import Task, Project, DisciplineItem
from django.contrib.auth import get_user_model

User = get_user_model()

def run_tender_lifecycle_test():
    # --- خطوة تنظيف اختيارية ---
    # مسح المهام التي تم إنشاؤها بالخطأ مسبقاً والخاصة بالـ Tender فقط
    deleted_count, _ = Task.objects.filter(title__startswith='Auto Test Task Tender').delete()
    if deleted_count > 0:
        print(f"🧹 Cleaned up {deleted_count} mistakenly created Tender tasks.")

    # 1. تحديد المشروع بناءً على الـ ID رقم 2
    try:
        project = Project.objects.get(id=2)
    except Project.DoesNotExist:
        print("❌ Error: Project with ID 2 not found.")
        return
    
    # 2. تحديد المسؤول (سواء كان مهندس أو مدير مشروع)
    engineer = User.objects.filter(role__in=['ENGINEER', 'SENIOR_ENG', 'PM']).first()
    
    if not engineer:
        print("❌ Error: No user found in the database to assign tasks to.")
        return

    # 3. جلب التخصصات الخاصة بمرحلة العطاءات
    # ملاحظة: تأكد أن قيمة 'TENDER' مطابقة تماماً للاسم المحفوظ عندك في قاعدة البيانات (قد تكون 'TENDERING' مثلاً)
    disciplines = DisciplineItem.objects.filter(is_active=True, stage='TENDER')
    
    if disciplines.count() == 0:
        print("❌ Error: No active disciplines found for TENDER stage.")
        return

    print(f"🚀 Starting creation of {disciplines.count()} Tender tasks for Project: {project.name} (ID: {project.id})...")

    # 4. الدوران لإنشاء المهام
    tasks_created = 0
    for disc in disciplines:
        task = Task.objects.create(
            # عدل 'TENDER_TASK' إذا كان لديك حقل Choices مختلف لمهام العطاءات في الموديل
            task_type='TENDERING', 
            project=project,
            stage=disc.stage, # ستكون بناءً على الفلتر مرحلة العطاءات
            discipline=disc,
            title=f'Auto Test Task Tender - {disc.name}',
            assigned_to=engineer,
            priority='HIGH', # عادة مهام العطاءات تكون ذات أولوية عالية
            duration_days=3,
            progress_percentage=100,
            status='APPROVED' 
        )
        tasks_created += 1
        print(f"✅ Created & Approved: {task.title} (Stage: {task.stage})")

    print(f"🎉 Success: {tasks_created} Tender tasks have been successfully created for {project.name}!")

# تشغيل الدالة
run_tender_lifecycle_test()