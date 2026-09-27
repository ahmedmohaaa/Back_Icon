from rest_framework import permissions

# 1. Base Role Definitions

MANAGEMENT_ROLES = ['GM', 'AGM']
DESIGN_MANAGERS = ['GM', 'AGM', 'DESIGN_MGR']
SUPERVISION_MANAGERS = ['SUP_MGR', 'PM']
FINANCE_ROLES = ['GM', 'AGM', 'ACCOUNTANT']
ENGINEERING_ROLES = ['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN', 'PM']

# 2. Base Role Permissions

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
        if user.role == 'ACCOUNTANT':
            return request.method in permissions.SAFE_METHODS
        if user.role in ['GM', 'AGM']:
            return True
        if obj.scope == 'DESIGN':
            if request.method in permissions.SAFE_METHODS:
                return True
            if user.role in DESIGN_MANAGERS:
                return True
            # السكرتيرة: تصميم فقط إن كانت سكرتيرة تصميم
            return user.role == 'SECRETARY' and user.department == 'Design'
        elif obj.scope in ['SUPERVISION', 'BOTH']:
            if request.method in permissions.SAFE_METHODS:
                if user.role in DESIGN_MANAGERS:
                    return True
                return user.department == 'Supervision' or user.role in SUPERVISION_MANAGERS
            if user.role in SUPERVISION_MANAGERS:
                return True
            return user.role == 'SECRETARY' and user.department == 'Supervision'
        return False

class TaskManagementPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        
        if request.method in permissions.SAFE_METHODS:
            return True

        if obj.assigned_to == user:
            return True

        if user.role in DESIGN_MANAGERS + SUPERVISION_MANAGERS + ['SENIOR_ENG']:
            return True

        return False


class CanManageSupervisionTeam(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role in SUPERVISION_MANAGERS
        )

    def has_object_permission(self, request, view, obj):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role in SUPERVISION_MANAGERS
        )

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
    ملف العقد يظهر فقط للإدارة (ناصر ونسرين) والمحاسب
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
    حالة العرض يمكن تعديلها بواسطة:
    - GM, AGM
    - Design Manager
    - Secretary
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and
            request.user.role in ['GM', 'AGM', 'DESIGN_MGR', 'SECRETARY']
        )


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
        return bool(request.user and request.user.is_authenticated and
                   request.user.role == 'SECRETARY' and request.user.department == 'Management')

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
    """الإشراف: مدير/سكرتيرة الإشراف + DC engineers يديرون؛ البقية يقرأون."""
    def has_permission(self, request, view):
        u = request.user
        if request.method in permissions.SAFE_METHODS:
            return True
        if u.role in ['SUP_MGR', 'PM', 'GM', 'AGM']:
            return True
        if u.role == 'SECRETARY' and u.department == 'Supervision':
            return True
        return u.role in ['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN']   # DC engineers
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
    """إنشاء/تعيين المهام: المدراء + كبار المهندسين (لا self-assign هنا)."""
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.role in (
            DESIGN_MANAGERS + SUPERVISION_MANAGERS + ['SENIOR_ENG']
        ))

# ── البند 5: مالية الإشراف للمحاسب + مدير الإشراف (+ الإدارة العليا) ──
class CanViewSupervisionFinance(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated
                    and u.role in ['GM', 'AGM', 'ACCOUNTANT', 'SUP_MGR'])

# ── البند 7 + 8: العملاء (القراءة لكل المدراء، الكتابة + السكرتيرة) ──
class CanManageClient(permissions.BasePermission):
    READ_ROLES  = ['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR', 'PM', 'ACCOUNTANT']
    WRITE_ROLES = ['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR', 'PM', 'SECRETARY']
    def has_permission(self, request, view):
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

    







    CanManageSupervisionTeam