from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    User,
    Client,
    Contractor,
    MasterDiscipline,
    DisciplineItem,
    DisciplineTracking,
    Project,
    PriorityHistory,
    ProjectLifecycleStage,
    InternalReviewStage,
    TenderingModule,
    Task,
    AssignmentHistory,
    ReplacementRequest,
    StaffKPI,
    SupervisionTeamAssignment,
    ActionRequest,
    Invoice,
    InvoicePayment,
    SupervisionInvoice,
    AuditLog,
    ChatRoom,
    ChatMessage,
    Notification,
    ProjectNote,
    ProjectFile,
    ExternalLog,
)
from .models import User

class CustomUserAdmin(UserAdmin):
    # 1. ترتيب الحقول عند (تعديل) بيانات مستخدم موجود
    fieldsets = UserAdmin.fieldsets + (
        ('Job Details', {
            'fields': ('role', 'department', 'phone_number'),
        }),
    )
    
    # 2. ترتيب الحقول عند (إضافة) مستخدم جديد (وهذا هو حل مشكلتك في الصورة)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Job Details', {
            'fields': ('first_name', 'last_name', 'email', 'role', 'department', 'phone_number'),
        }),
    )

    # 3. الحقول التي ستظهر في الجدول الخارجي (قائمة المستخدمين)
    list_display = ['username', 'first_name', 'last_name', 'role', 'department', 'is_staff']
    
    # 4. إضافة فلاتر جانبية لتسهيل البحث عن المهندسين أو السكرتارية
    list_filter = ['role', 'department', 'is_staff', 'is_active']

# تسجيل الموديل في لوحة التحكم
admin.site.register(User, CustomUserAdmin)

# ===========================
# User
# ===========================

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    User,
    Client,
    Contractor,
    MasterDiscipline,
    DisciplineItem,
    DisciplineTracking,
    Project,
    PriorityHistory,
    ProjectLifecycleStage,
    InternalReviewStage,
    TenderingModule,
    Task,
    AssignmentHistory,
    ReplacementRequest,
    StaffKPI,
    SupervisionTeamAssignment,
    ActionRequest,
    Invoice,
    InvoicePayment,
    SupervisionInvoice,
    AuditLog,
    ChatRoom,
    ChatMessage,
    Notification,
    ProjectNote,
    ProjectFile,
    ExternalLog,
)




@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "project_no",
        "name",
        "client",
        "scope",
        "priority",
        "permit_status",
        "is_active",
    )
    search_fields = (
        "project_no",
        "application_no",
        "pin_no",
        "name",
        "client__name",
    )
    list_filter = (
        "scope",
        "priority",
        "permit_status",
        "is_active",
    )


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "project",
        "assigned_to",
        "status",
        "priority",
    )
    list_filter = (
        "status",
        "priority",
        "stage",
    )
    search_fields = (
        "title",
        "project__project_no",
        "project__name",
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "title",
        "milestone_type",
        "status",
        "total_amount",
        "issue_date",
        "due_date",
    )
    list_filter = (
        "status",
        "milestone_type",
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "user",
        "action_type",
        "created_at",
    )
    list_filter = (
        "action_type",
        "created_at",
    )
    search_fields = (
        "project__project_no",
        "details",
    )


# تسجيل بقية الموديلات
admin.site.register(Client)
admin.site.register(Contractor)
admin.site.register(MasterDiscipline)
admin.site.register(DisciplineItem)
admin.site.register(DisciplineTracking)
admin.site.register(PriorityHistory)
admin.site.register(ProjectLifecycleStage)
admin.site.register(InternalReviewStage)
admin.site.register(TenderingModule)
admin.site.register(AssignmentHistory)
admin.site.register(ReplacementRequest)
admin.site.register(StaffKPI)
admin.site.register(SupervisionTeamAssignment)
admin.site.register(ActionRequest)
admin.site.register(InvoicePayment)
admin.site.register(SupervisionInvoice)
admin.site.register(ChatRoom)
admin.site.register(ChatMessage)
admin.site.register(Notification)
admin.site.register(ProjectNote)
admin.site.register(ProjectFile)
admin.site.register(ExternalLog)