from rest_framework import permissions
from .models import (
    SUPERVISION_ENGINEER_USERNAMES,
    DESIGN_TASK_ASSIGNEE_USERNAMES,
    SUPERVISION_TASK_MANAGER_USERNAMES,
)
# 1. Base Role Definitions

MANAGEMENT_ROLES = ['GM', 'AGM']
DESIGN_MANAGERS = ['GM', 'AGM', 'DESIGN_MGR']
SUPERVISION_MANAGERS = ['SUP_MGR', 'PM']
FINANCE_ROLES = ['GM', 'AGM', 'ACCOUNTANT']
ENGINEERING_ROLES = ['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN', 'PM']
# ── صلاحيات تعيين إضافية محدودة (مصدر واحد بدون تكرار) ──
EXTRA_DESIGN_ASSIGN = {
    'mohammad.mostafa': frozenset({
        'vicky.jr', 'mohammad.alqadi', 'ahmad.alqadi', 'mohammad.mostafa',
    }),
}

SENIOR_ENG_TARGETS = frozenset({
    'abdulhamid.ahmad',
    'mohammad.mostafa',
    'mahmoud.aldemyati',
})

EXTRA_SENIOR_ENG_ASSIGN = {
    'israa.omran':  SENIOR_ENG_TARGETS,
    'basem.taha':   SENIOR_ENG_TARGETS,
    'salah.ahmad':  SENIOR_ENG_TARGETS,
    'basel.shaat':  SENIOR_ENG_TARGETS,
}
# 2. Base Role Permissions
def is_supervision_task_manager(user):
    return bool(
        user and
        getattr(user, 'is_authenticated', False) and
        (
            getattr(user, 'role', None) == 'PM' or
            getattr(user, 'username', None) in SUPERVISION_TASK_MANAGER_USERNAMES
        )
    )


def is_supervision_engineer(user):
    return bool(
        user and
        getattr(user, 'is_authenticated', False) and
        getattr(user, 'role', None) == 'ENGINEER' and
        getattr(user, 'username', None) in SUPERVISION_ENGINEER_USERNAMES
    )

def is_project_pm(user, project):
    """
    هل المستخدم PM لمشروع محدد؟
    project يمكن أن يكون Project instance أو project_id.
    """
    from .models import SupervisionTeamAssignment

    if not user or not getattr(user, 'is_authenticated', False):
        return False

    project_id = (
        project
        if isinstance(project, (int, str))
        else getattr(project, 'id', None)
    )

    if not project_id:
        return False

    return SupervisionTeamAssignment.objects.filter(
        project_id=project_id,
        engineer=user,
        is_pm=True
    ).exists()


def is_project_pm_any(user):
    """
    هل المستخدم PM على أي مشروع؟
    (يختلف عن is_project_pm الذي يفحص مشروع محدد)
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False

    from .models import SupervisionTeamAssignment
    return SupervisionTeamAssignment.objects.filter(
        engineer=user, is_pm=True
    ).exists()


def is_design_task_assignee(user):
    return bool(
        user and
        getattr(user, 'username', None) in DESIGN_TASK_ASSIGNEE_USERNAMES
    )


# ═══════════════════════════════════════════════════════════
#  DESIGN TASK ASSIGNMENT RULES
# ═══════════════════════════════════════════════════════════

# من له صلاحية تعيين مهام للجميع (مهندسين + رسامين) في التصميم
DESIGN_FULL_ASSIGN_ROLES = ['GM', 'AGM', 'DESIGN_MGR']
# ═══════════════════════════════════════════════════════════════
# DESIGN DRAFTSMEN ASSIGNMENT — بالاعتماد على حقل discipline الجديد
# ═══════════════════════════════════════════════════════════════

# من له صلاحية تعيين مهام للرسامين حسب التخصص (discipline وليس department)
# ✅ لاحظ: المفتاح أصبح 'Architect' ليطابق القيمة المخزنة في قاعدة البيانات
DESIGN_DRAFTSMEN_ASSIGNERS = {
    'Mechanical':   ['abdulhamid.ahmad'],
    'Electrical':   ['mahmoud.aldemyati'],
    'Structural':   ['mohammad.mostafa'],
    'Architect':    ['basel.shaat', 'basem.taha', 'salah.ahmad', 'israa.omran'],
}

# ✅ الرسام متعدد التخصصات (discipline = 'General' مثل سلمان سعيد)
#    يستقبل مهام من هذه التخصصات فقط
GENERAL_DRAFTSMAN_ACCEPTED_DISCIPLINES = ['Mechanical', 'Electrical', 'Architect']


def can_assign_design_task(assignor, assignee, user=None):
    """
    هل يستطيع assignor تعيين مهمة لـ assignee في التصميم؟
    (توقيع مرن: يعمل مع الاستدعاء بمتغيرين أو ثلاثة — بدون تعديل views.py)
    """
    checker = user if user is not None else assignor

    # 0) صلاحيات إضافية محدودة (مثل محمد مصطفى)
    allowed = EXTRA_DESIGN_ASSIGN.get(checker.username)
    if allowed and assignee.username in allowed:
        return True

    # ✅ 0.5) صلاحيات تعيين Senior Engineers المحددة (israa, basem, salah, basel)
    senior_allowed = EXTRA_SENIOR_ENG_ASSIGN.get(checker.username)
    if senior_allowed and assignee.username in senior_allowed:
        return True

    # 1) صلاحية كاملة: المدراء
    if assignor.role in DESIGN_FULL_ASSIGN_ROLES:
        return True

    # 2) صلاحية تعيين رسامين حسب التخصص (discipline)
    assignee_role = getattr(assignee, 'role', None)
    assignee_discipline = getattr(assignee, 'discipline', None) or ''

    if assignee_role == 'DRAFTSMAN':
        # أ) رسام متعدد التخصصات (General): يقبل مهام من التخصصات المقبولة فقط
        if assignee_discipline == 'General':
            return any(
                assignor.username in DESIGN_DRAFTSMEN_ASSIGNERS.get(disc, [])
                for disc in GENERAL_DRAFTSMAN_ACCEPTED_DISCIPLINES
            )
        # ب) رسام بتخصص محدد: فقط مهندسو نفس التخصص
        return assignor.username in DESIGN_DRAFTSMEN_ASSIGNERS.get(assignee_discipline, [])

    return False

def get_assignable_design_users(user):
    """
    يرجع قائمة المستخدمين الذين يستطيع user تعيين مهام لهم.
    """
    from .models import DESIGN_TASK_ASSIGNEE_USERNAMES
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    User = get_user_model()

    # ✅ المدراء: كل مهندسي ورسامي التصميم + أنفسهم (علشان يقدروا يعينوا أنفسهم)
    if user.role in DESIGN_FULL_ASSIGN_ROLES:
        result = set(DESIGN_TASK_ASSIGNEE_USERNAMES)
        result.add(user.username)   # ✅ يقدر يعيّن نفسه
        return list(result)

    # نفسه دائماً
    assignable = {user.username}

    # ✅ الصلاحيات الإضافية (EXTRA_DESIGN_ASSIGN) تظهر له في القائمة
    extra = EXTRA_DESIGN_ASSIGN.get(user.username)
    if extra:
        assignable.update(extra)

    # ✅ جديد: صلاحيات Senior Engineers الإضافية تظهر له في القائمة
    senior_extra = EXTRA_SENIOR_ENG_ASSIGN.get(user.username)
    if senior_extra:
        assignable.update(senior_extra)

    # ✅ التخصصات التي يديرها هذا المستخدم
    managed_disciplines = [
        disc for disc, assigners in DESIGN_DRAFTSMEN_ASSIGNERS.items()
        if user.username in assigners
    ]

    if managed_disciplines:
        query = Q(discipline__in=managed_disciplines)
        # الرسام General يظهر فقط لمن تخصصه ضمن تخصصاته المقبولة
        if set(managed_disciplines) & set(GENERAL_DRAFTSMAN_ACCEPTED_DISCIPLINES):
            query |= Q(discipline='General')

        draftsmen = User.objects.filter(
            role='DRAFTSMAN',
            is_active=True,
        ).filter(query).values_list('username', flat=True)
        assignable.update(draftsmen)

    return list(assignable)
def is_management_secretary(user):
    return bool(
        user and
        getattr(user, 'is_authenticated', False) and
        (
            getattr(user, 'role', None) == 'MANAGEMENT_SECRETARY' or
            (
                getattr(user, 'role', None) == 'SECRETARY' and
                getattr(user, 'department', None) == 'Management'
            )
        )
    )
class IsManagement(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.role in MANAGEMENT_ROLES)


class IsDesignManagerOrManagement(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.role in DESIGN_MANAGERS)


class IsSupervisionManagerOrPM(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.role in SUPERVISION_MANAGERS)


class IsSecretary(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.role == 'SECRETARY')


# 3. Module-Specific Permissions

class IsManagementOrAccountant(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.role in FINANCE_ROLES)

    def has_object_permission(self, request, view, obj):
        return bool(request.user.role in FINANCE_ROLES)


class TenderingPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.role == 'AGM')


class ProjectDirectoryAccess(permissions.BasePermission):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        is_safe = request.method in permissions.SAFE_METHODS

        # 1. المحاسب: قراءة فقط
        if user.role == 'ACCOUNTANT':
            return is_safe

        # 2. الإدارة (ناصر + نسرين): كل شيء
        if user.role in ['GM', 'AGM']:
            return True
        if user.role == 'SECRETARY' and user.department == 'Management':
            return is_safe

        # 3. المهندسون: قراءة فقط لأي مشروع (بدون تعديل)
        # PM مستبعد لأنه يحتاج تعديل مشاريع الإشراف عبر SUPERVISION_MANAGERS
        if user.role in ['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN']:
            return is_safe

        # 4. فحص الصلاحيات بناءً على نطاق المشروع (Scope)
        has_design_access = False
        has_sup_access = False

        # شروط التصميم (تُطبّق إذا كان المشروع DESIGN أو BOTH)
        if obj.scope in ['DESIGN', 'BOTH']:
            if is_safe:
                has_design_access = True
            elif user.role in DESIGN_MANAGERS or (user.role == 'SECRETARY' and user.department == 'Design'):
                has_design_access = True

        # شروط الإشراف (تُطبّق إذا كان المشروع SUPERVISION أو BOTH)
        if obj.scope in ['SUPERVISION', 'BOTH']:
            if is_safe:
                if user.role in DESIGN_MANAGERS or user.department == 'Supervision' or user.role in SUPERVISION_MANAGERS:
                    has_sup_access = True
            elif user.role in SUPERVISION_MANAGERS or (user.role == 'SECRETARY' and user.department == 'Supervision'):
                has_sup_access = True

        # السماح بالوصول في حال تحقق صلاحيات أي من القسمين للمشاريع المشتركة أو المحددة
        return has_design_access or has_sup_access
class TaskManagementPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        # السماح بالوصول والتعديل لجميع المستخدمين
        return True

class CanManageSupervisionTeam(permissions.BasePermission):
    """
    إدارة فريق الإشراف:
    - المديرون العامون (SUP_MGR / PM) → أي مشروع.
    - PM المشروع (is_pm=True في SupervisionTeamAssignment) → مشروعه فقط.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.role in SUPERVISION_MANAGERS:
            return True

        project_id = view.kwargs.get('project_id')
        if project_id:
            return is_project_pm(user, project_id)

        return False

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if user.role in SUPERVISION_MANAGERS:
            return True

        project = getattr(obj, 'project', None)
        if project:
            return is_project_pm(user, project)

        return False

class IsAssignedEngineerOrManager(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        user = request.user
        is_manager = hasattr(user, 'role') and user.role in ['GM', 'AGM', 'DESIGN_MGR']
        is_assigned = getattr(obj, 'assigned_to', None) == user
        
        return is_manager or is_assigned


# NEW: Special Permissions

class CanViewContractFile(permissions.BasePermission):
    """
    عرض ملف العقد وحالته: ناصر (GM) ونسرين (AGM) والمحاسب فقط
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.role in ['GM', 'AGM', 'ACCOUNTANT'])

    def has_object_permission(self, request, view, obj):
        return bool(request.user.role in ['GM', 'AGM', 'ACCOUNTANT'])


class IsMohammadMostafa(permissions.BasePermission):
    """
    صلاحية Mohammad Mostafa (Structural Senior)
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.username == 'mohammad.mostafa')

    def has_object_permission(self, request, view, obj):
        return bool(request.user.username == 'mohammad.mostafa')


class IsShaabanKaram(permissions.BasePermission):
    """
    صلاحية Shaaban Karam (IFC)
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.username == 'shaaban.karam')

    def has_object_permission(self, request, view, obj):
        return bool(request.user.username == 'shaaban.karam')


class IsSalmanSaeed(permissions.BasePermission):
    """
    Salman Saeed يظهر في جميع الأقسام
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.username == 'salman.saeed')
    



class CanAccessClientDirectory(permissions.BasePermission):
    """
    Client Directory متاح لجميع المديرين:
    - GM, AGM (Nasser, Nisreen)
    - Design Manager (Fahmi)
    - Supervision Managers
    - Accountant
    """
    def has_permission(self, request, view):
        allowed_roles = [
            'GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR', 'PM', 'ACCOUNTANT'
        ]
        return bool(
            request.user and 
            request.user.is_authenticated and
            request.user.role in allowed_roles
        )


# 2. CanAccessStaffKPI (جديد)
#
# Staff KPI للإدارة فقط

class CanAccessStaffKPI(permissions.BasePermission):
    """
    Staff Insights / KPI متاح لـ:
    - GM, AGM
    - Design Manager
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and
            request.user.role in ['GM', 'AGM', 'DESIGN_MGR']
        )


# 3. CanManageOfferStatus (جديد)
#
# صلاحية تعديل حالة العرض

class CanManageOfferStatus(permissions.BasePermission):
    """
    تعديل حالة العرض/العقد:
    - الإدارة العليا
    - مدير التصميم
    - سكرتيرة الإدارة
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return is_management_secretary(user)   # ✅ سكرتيرة الإدارة فقط

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
# 4. CanUpdateInternalReview (جديد)
#
# صلاحية تحديث Internal Design Review

class CanUpdateInternalReview(permissions.BasePermission):
    """
    تحديث Internal Design Review:
    - المهندس المعين
    - Supervision Manager
    - PM
    - GM, AGM
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        
        is_assigned = getattr(obj, 'assigned_to', None) == user
        is_manager = user.role in ['SUP_MGR', 'PM', 'GM', 'AGM']
        
        return is_assigned or is_manager


# 5. IsEngineer (جديد)
#
# للتحقق من أن المستخدم مهندس

class IsEngineer(permissions.BasePermission):
    """
    أي دور هندسي
    """
    def has_permission(self, request, view):
        engineer_roles = ['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN', 'PM']
        return bool(
            request.user and 
            request.user.is_authenticated and
            request.user.role in engineer_roles
        )


# 6. CanUseGlobalFilter (جديد)
#
# Global Filter متاح لجميع المستخدمين المسجلين

class CanUseGlobalFilter(permissions.BasePermission):
    """
    Global Filter Bar متاح لجميع المستخدمين المسجلين
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated
        )
    
class IsDesignSecretary(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and
                   request.user.role == 'SECRETARY' and request.user.department == 'Design')

class IsSupervisionSecretary(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and
                   request.user.role == 'SECRETARY' and request.user.department == 'Supervision')

class IsManagementSecretary(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role == 'MANAGEMENT_SECRETARY'
        )
class CanCreateProject(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated: return False
        if user.role in ['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR']: return True
        if user.role == 'SECRETARY':
            scope = request.data.get('scope', '')
            if user.department == 'Management': return True
            if user.department == 'Design' and scope in ['DESIGN', 'BOTH']: return True
            if user.department == 'Supervision' and scope in ['SUPERVISION', 'BOTH']: return True
        return False


class CanCreateInvoice(permissions.BasePermission):
    """فقط المحاسب والإدارة يمكنهم إنشاء فواتير"""
    def has_permission(self, request, view):
        return request.user.role in ['GM', 'AGM', 'ACCOUNTANT']

class CanViewFinancialData(permissions.BasePermission):
    """عرض البيانات المالية للمحاسب والإدارة فقط"""
    def has_permission(self, request, view):
        return request.user.role in ['GM', 'AGM', 'ACCOUNTANT', 'DESIGN_MGR', 'SUP_MGR']

class CanUploadInvoicePDF(permissions.BasePermission):
    """رفع ملفات الفواتير"""
    def has_permission(self, request, view):
        return request.user.role in ['GM', 'AGM', 'ACCOUNTANT']
    

class CanViewReports(permissions.BasePermission):
    """عرض التقارير للمديرين فقط"""
    def has_permission(self, request, view):
        return request.user.role in ['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR', 'ACCOUNTANT']

class CanExportReports(permissions.BasePermission):
    """تصدير التقارير (PDF/Excel)"""
    def has_permission(self, request, view):
        return request.user.role in ['GM', 'AGM', 'ACCOUNTANT']


class CanSelfAssign(permissions.BasePermission):
    """المهندسون فقط يمكنهم self-assign"""
    def has_permission(self, request, view):
        return request.user.role in ['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN']
    

# في permissions.py
class CanEditProjectByDepartment(permissions.BasePermission):
    """
    التحقق من أن المستخدم يمكنه تعديل المشروع حسب قسمه
    """
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # المديرين يمكنهم تعديل أي مشروع
        if user.role in ['GM', 'AGM']:
            return True
        
        # سكرتير التصميم يمكنه تعديل مشاريع التصميم والمشتركة
        if user.role == 'SECRETARY' and user.department == 'Design':
            return obj.scope in ['DESIGN', 'BOTH']
        
        # سكرتير الإشراف يمكنه تعديل مشاريع الإشراف والمشتركة
        if user.role == 'SECRETARY' and user.department == 'Supervision':
            return obj.scope in ['SUPERVISION', 'BOTH']
        
        # مديرو التصميم
        if user.role == 'DESIGN_MGR':
            return obj.scope in ['DESIGN', 'BOTH']
        
        # مديرو الإشراف
        if user.role in ['SUP_MGR', 'PM']:
            return obj.scope in ['SUPERVISION', 'BOTH']
        
        return False
class CanManageExternalLogs(permissions.BasePermission):
    """ السماح بالقراءة للجميع، والإدارة للمديرين الأربعة فقط """
    
    def has_permission(self, request, view):
        u = request.user
        
        if request.method in permissions.SAFE_METHODS:
            return True
            
        return u.role in ['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR']
    
class CanUpdateSupervisionLifecycle(permissions.BasePermission):
    """Lifecycle الإشراف: مدير الإشراف/PM + سكرتيرة الإشراف (+ الإدارة)"""
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if u.role in ['GM', 'AGM', 'SUP_MGR', 'PM']:
            return True
        return u.role == 'SECRETARY' and u.department == 'Supervision'


# ── البند 2: إنشاء المهام للمدراء والـ Seniors فقط ──────────────
class CanCreateTask(permissions.BasePermission):
    """إنشاء/تعيين المهام: أي مستخدم مسجل دخول."""
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated)

# ── البند 5: مالية الإشراف للمحاسب + مدير الإشراف (+ الإدارة العليا) ──
class CanViewSupervisionFinance(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated
                    and u.role in ['GM', 'AGM', 'ACCOUNTANT', 'SUP_MGR'])

# ── البند 7 + 8: العملاء (القراءة لكل المدراء، الكتابة + السكرتيرة) ──
class CanManageClient(permissions.BasePermission):
    READ_ROLES = ['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR', 'PM', 'ACCOUNTANT', 'SECRETARY']
    WRITE_ROLES = ['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR', 'PM', 'SECRETARY']

    def has_permission(self, request, view):
        print("========== CLIENT ==========")
        print("User:", request.user.username)
        print("Role:", repr(request.user.role))
        print("Method:", request.method)
        print("Allowed:", request.user.role in self.READ_ROLES)

        u = request.user
        if not u or not u.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return u.role in self.READ_ROLES

        return u.role in self.WRITE_ROLES
# ── البند 7 + 8: المقاولون (قاعدة بيانات للإدارة، تُدخلها السكرتيرة) ──
class CanManageContractor(permissions.BasePermission):
    READ_ROLES  = ['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR', 'PM', 'ACCOUNTANT', 'SECRETARY']
    WRITE_ROLES = ['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR', 'PM', 'SECRETARY']
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return u.role in self.READ_ROLES
        return u.role in self.WRITE_ROLES

    
class CanAssignInternalReview(permissions.BasePermission):
    """تعيين مهندسي المراجعة: مدير الإشراف / PM / الإدارة العليا فقط."""
    def has_permission(self, request, view):
        return request.user.role in ['SUP_MGR', 'PM', 'GM', 'AGM']

class CanUpdateInternalReviewStage(permissions.BasePermission):
    """
    تحديث مرحلة مراجعة:
    - قراءة: أي مستخدم مسجّل.
    - كتابة: الإدارة العليا + مدير الإشراف (أحمد زبادي) + سكرتيرة الإشراف
      + المهندس المعيّن على المشروع/المرحلة.
    """
    def has_object_permission(self, request, view, obj):
        u = request.user
        if request.method in permissions.SAFE_METHODS:
            return True
        if u.role in ['GM', 'AGM']:
            return True
        # ✅ زر الإنجاز: مدير الإشراف (أحمد زبادي) وسكرتيرة الإشراف فقط
        if u.username in SUPERVISION_TASK_MANAGER_USERNAMES:
            return True
        if u.role == 'SECRETARY' and u.department == 'Supervision':
            return True
        stage = obj  # obj = InternalReviewStage
        # المهندس المعيّن على مستوى المشروع أو على المرحلة
        return (stage.project.internal_review_assignees.filter(id=u.id).exists()
                or getattr(stage, 'assigned_to_id', None) == u.id)
class CanViewInternalReview(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if u.role in ['GM', 'AGM', 'SUP_MGR', 'PM', 'DESIGN_MGR']:
            return True
        return u.role == 'SECRETARY' and u.department == 'Supervision'




class CanUploadContractFile(permissions.BasePermission):
    """
    رفع/تعديل ملف العقد:
    - الإدارة العليا
    - سكرتيرة الإدارة
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        return is_management_secretary(user)   # ✅ الرفع لها وحدها

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)

class CanCreateTask(permissions.BasePermission):
    """
    إنشاء المهام:
    - مهام الإشراف: فقط أحمد زبادي / PM / مهندس إشراف.
    - باقي المهام: أي مستخدم مسجل دخول.
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        task_type = request.data.get('task_type')

        if task_type == 'SUPERVISION':
            return (
                is_supervision_task_manager(user) or
                is_supervision_engineer(user)
            )

        return True
    

# ═══════════════════════════════════════════════════════════
# Supervision Finance — Restricted Users
# ═══════════════════════════════════════════════════════════

SUPERVISION_FINANCE_VIEW_USERNAMES = (
    'ahmed.zabady',
    'mohammad.mishab',  # ← عدّل اسم المستخدم الفعلي لمحمد مشعب هنا
)

SUPERVISION_FINANCE_WRITE_USERNAMES = (
    'mohammad.mishab',
)


class CanAccessSupervisionFinance(permissions.BasePermission):
    """
    مالية الإشراف:
    - القراءة: أحمد زبادي + محمد مشعب فقط.
    - الكتابة: محمد مشعب فقط، وبشرط أن يكون ACCOUNTANT.
    """

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        username = getattr(user, 'username', None)

        if request.method in permissions.SAFE_METHODS:
            return username in SUPERVISION_FINANCE_VIEW_USERNAMES

        return (
            username in SUPERVISION_FINANCE_WRITE_USERNAMES
            and getattr(user, 'role', None) == 'ACCOUNTANT'
        )





