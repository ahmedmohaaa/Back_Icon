from aiohttp import request
from django.db.migrations import serializer
from django.db.models.functions import TruncMonth
from rest_framework import generics, permissions, filters, status, views
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q, F, Count, Sum
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from django.contrib.auth import update_session_auth_hash
from django.db.models import Q, CharField, OuterRef, Subquery
from rest_framework_simplejwt.views import TokenObtainPairView


from erp.services.invoice_service import InvoiceService
from erp.services.change_order_service import (
    create_change_order, confirm_change_order,
    reject_change_order, cancel_change_order,
)
from .serializers import (
    ChangeOrderCreateSerializer, ChangeOrderListSerializer,
    ChangeOrderDetailSerializer, ChangeOrderActionSerializer, ChangeOrderOptionSerializer, ChangeOrderOptionSerializer,
)
from erp.services.task_service import TaskService
from .serializers import ChangePasswordSerializer, InternalReviewAssigneeSerializer, InvoiceFileSerializer, LifecycleHistorySerializer, MyInternalReviewProjectSerializer, PaymentScheduleSerializer, ProjectCreateSerializer
from .serializers import (
    ActionRequestSerializer, AuditLogSerializer, ChatMessageSerializer, 
    ChatRoomSerializer, ClientDirectorySerializer, ExternalLogSerializer, InvoiceSerializer, 
    NotificationSerializer, OfferStatusSerializer, ProjectCardSerializer, ProjectFileSerializer, ProjectNoteSerializer, StaffKPIInsightSerializer, SupervisionInternalReviewSerializer, 
    UserSerializer, TaskSerializer, AssignmentHistorySerializer, 
    SupervisionTeamAssignmentSerializer, SupervisionInvoiceSerializer,
    DisciplineItemSerializer, DisciplineTrackingSerializer, 
    ReplacementRequestSerializer, StaffKPISerializer,
    ClientSerializer, ContractorSerializer, ProjectListSerializer, 
    ProjectDetailSerializer, PriorityHistorySerializer, 
    ProjectLifecycleStageSerializer, InternalReviewStageSerializer,
    TenderingModuleSerializer, InvoicePaymentSerializer,SupervisionReplacementRequestSerializer
)
from .permissions import (
    CanAccessSupervisionFinance, DESIGN_FULL_ASSIGN_ROLES, CanAssignInternalReview, CanCreateInvoice, CanCreateProject, CanCreateTask, CanManageClient, CanManageContractor, CanManageSupervisionTeam, CanUpdateInternalReviewStage, CanUploadContractFile, CanUploadInvoicePDF, CanViewFinancialData, CanViewReports, IsDesignSecretary, IsManagementOrAccountant, IsMohammadMostafa, IsSecretary, IsSupervisionManagerOrPM, IsSupervisionSecretary,
    TenderingPermission, ProjectDirectoryAccess, TaskManagementPermission, 
    IsDesignManagerOrManagement, IsManagement, IsAssignedEngineerOrManager,
    CanViewContractFile,CanAccessClientDirectory, CanAccessStaffKPI, CanManageOfferStatus,
    CanUpdateInternalReview, CanEditProjectByDepartment, CanSelfAssign,
    CanManageExternalLogs, CanUpdateSupervisionLifecycle,
    CanViewInternalReview, can_assign_design_task, get_assignable_design_users, is_project_pm_any,
    is_supervision_task_manager,
    is_supervision_engineer,
    is_design_task_assignee,is_project_pm
)
from .models import (
    ChatMessage, ChatRoom, ExternalLog, Invoice, ActionRequest, InvoiceFile, 
    InvoicePayment, LifecycleHistory, Notification, PaymentSchedule, ProjectFile, ProjectNote, SupervisionAssignmentHistory, 
    SupervisionTeamAssignment, Client, TenderingModule, Project, 
    Contractor, PriorityHistory, ProjectLifecycleStage, InternalReviewStage,
    Task, AssignmentHistory, AuditLog, DisciplineItem, DisciplineTracking,
    ReplacementRequest, StaffKPI, SupervisionInvoice,SupervisionReplacementRequest, sync_lifecycle_from_disciplines,  
        REVIEW_STAGE_TO_DISCIPLINE_STAGES, advance_internal_review_stage,
            SUPERVISION_ENGINEER_USERNAMES,
    DESIGN_TASK_ASSIGNEE_USERNAMES,SUPERVISION_TASK_MANAGER_USERNAMES,

)
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.utils.dateparse import parse_date
User = get_user_model()
def _audience_member(u, audience):
    """من يرى/يرسل في غرفة عامة؟ (مصدر حقيقة واحد)"""
    if audience == 'SUPERVISION':
        return (u.role in ['SUP_MGR', 'PM'] or u.username in SUPERVISION_ENGINEER_USERNAMES
                or (u.role == 'SECRETARY' and u.department == 'Supervision'))
    if audience == 'DESIGN':
        return (u.role in ['GM', 'AGM', 'DESIGN_MGR'] or u.username in DESIGN_TASK_ASSIGNEE_USERNAMES
                or (u.role == 'SECRETARY' and u.department == 'Design'))
    return True   # ALL
def _task_display_name(task):
    """اسم عرض آمن للمهمة — لا ينكسر أبداً حتى لو كانت بلا عنوان أو تخصص."""
    if getattr(task, 'title', None):
        return task.title
    disc = getattr(task, 'discipline', None)
    if disc and getattr(disc, 'name', None):
        return disc.name
    if hasattr(task, 'get_task_type_display'):
        return task.get_task_type_display()
    return 'Untitled Task'


def _notify_task_assignee(task, actor, kind='ASSIGNED'):
    """
    يُرسل إشعاراً فورياً لمستلم المهمة عند تعيينها أو تسليمها له.
    """
    if actor is None:
        return

    assignee = getattr(task, 'assigned_to', None)
    if not assignee:
        return

    # حماية ذكية: لا ترسل إشعاراً إذا كان المستخدم يعيّن نفسه
    if getattr(assignee, 'id', None) == getattr(actor, 'id', None):
        return  

    task_name = _task_display_name(task)
    project_no = getattr(task.project, 'project_no', '') if getattr(task, 'project', None) else ''
    actor_name = actor.get_full_name() or actor.username

    if kind == 'HANDOVER':
        notification_type = 'TASK_HANDOVER'
        title = 'Task Handover'
        message = (
            f"{actor_name} handed over task '{task_name}' ({project_no}) to you. "
            f"Current progress: {task.progress_percentage}% — continue from the same point."
        )
    elif kind == 'REASSIGNED':
        notification_type = 'TASK_REASSIGNED'
        title = 'Task Reassigned to You'
        message = f"{actor_name} reassigned task '{task_name}' ({project_no}) to you."
    elif kind == 'RETURNED':
        notification_type = 'TASK_RETURNED'
        title = 'Task Returned to You'
        message = (
            f"Task '{task_name}' ({project_no}) was returned to you "
            f"after the replacement request was declined."
        )
    else:
        notification_type = 'TASK_ASSIGNED'
        title = 'New Task Assigned'
        message = f"{actor_name} assigned you a new task: '{task_name}' ({project_no})."

    Notification.objects.create(
        user=assignee,
        sender=actor,
        notification_type=notification_type,
        title=title,
        message=message,
    )


def _return_task_to_requester(replacement, actor=None):
    """عند رفض طلب الاستبدال: تُرجَع المهمة للمهندس الأصلي كما كانت بدون أي تغيير آخر."""
    task = replacement.task
    if task.assigned_to_id != replacement.requested_by_id:
        task.assigned_to = replacement.requested_by
        task.save(update_fields=['assigned_to'])

    # ✅ إشعار لصاحب المهمة أنها رجعت له
    _notify_task_assignee(
        task,
        actor or getattr(replacement, 'responded_by', None) or replacement.suggested_engineer,
        kind='RETURNED',
    )


def _execute_task_handover(task, new_engineer, actor, reason=''):
    """
    تسليم المهمة لمهندس جديد مع الحفاظ الكامل على:
    نسبة التقدم + الحالة + تاريخ البدء (بدون أي تصفير).
    ويسجل KPIs المهندس القديم في AssignmentHistory + StaffKPI.
    """
    old_engineer = task.assigned_to
    if old_engineer and old_engineer.id == new_engineer.id:
        return
    days_worked = task.net_duration_days   # ✅ صافي الأيام (الإجمالي − الهولد) — نفس رقم صفحة المهمة
    if old_engineer:
        AssignmentHistory.objects.create(
            task=task,
            old_engineer=old_engineer,
            new_engineer=new_engineer,
            reason_for_change=reason or f"Replacement at progress {task.progress_percentage}%",
            days_worked=days_worked,
            status_at_handover=task.status,
        )
        StaffKPI.objects.create(
            user=old_engineer,
            project=task.project,
            task=task,
            days_worked=days_worked,
            status_at_handover=task.status,
            handover_date=timezone.now().date(),
        )
    task.assigned_to = new_engineer
    task.save(update_fields=['assigned_to'])   # ✅ تغيير المسند إليه فقط — لا تصفير

    # ✅ إشعار فوري للمهندس المستلم بعد إتمام التسليم مباشرة
    _notify_task_assignee(task, actor, kind='HANDOVER')
class UserListAPIView(generics.ListAPIView):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

class UserRetrieveAPIView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

class UserCreateAPIView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagement]

    def perform_create(self, serializer):
        user = serializer.save()
        password = self.request.data.get('password')
        if password:
            user.set_password(password)
            user.save()

class UserUpdateAPIView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagement]

    def perform_update(self, serializer):
        user = serializer.save()
        password = self.request.data.get('password')
        if password:
            user.set_password(password)
            user.save()

class UserDeleteAPIView(generics.DestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagement]

class CurrentUserAPIView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class ClientListCreateAPIView(generics.ListCreateAPIView):
    queryset = Client.objects.all().order_by('-created_at')
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]  # ← شيلنا CanManageClient

    def get(self, request, *args, **kwargs):
        print("=" * 50)
        print("VIEW REACHED!")
        print("User:", request.user.username if request.user.is_authenticated else "ANON")
        print("Role:", repr(getattr(request.user, 'role', None)))
        print("Auth header:", request.headers.get('Authorization', 'NONE'))
        print("=" * 50)
        return super().get(request, *args, **kwargs)
class ClientRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageClient]          

class ClientProjectsAPIView(generics.ListAPIView):
    serializer_class = ProjectListSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageClient]          

    def get_queryset(self):
        client_id = self.kwargs.get('pk')
        client = get_object_or_404(Client, pk=client_id)
        return Project.objects.filter(client=client).order_by('-created_at')


class ContractorListCreateAPIView(generics.ListCreateAPIView):
    queryset = Contractor.objects.all().order_by('-created_at')
    serializer_class = ContractorSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageContractor]      

class ContractorRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Contractor.objects.all()
    serializer_class = ContractorSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageContractor]      

class ContractorProjectsAPIView(generics.ListAPIView):
    serializer_class = ProjectListSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageContractor]      

    def get_queryset(self):
        contractor_id = self.kwargs.get('pk')
        contractor = get_object_or_404(Contractor, pk=contractor_id)
        return Project.objects.filter(contractor=contractor).order_by('-created_at')


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class ProjectListAPIView(generics.ListAPIView):
    queryset = Project.objects.all().order_by('-created_at')
    serializer_class = ProjectListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'priority', 'permit_status', 'client']
    search_fields = ['name', 'project_no', 'application_no', 'pin_no', 'client__name']
    ordering_fields = ['start_date', 'created_at', 'priority']

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()

        if not user or not user.is_authenticated:
            return queryset.none()

        # ✅ 1. الإدارة العليا ومديرو التصميم
        if user.role in ['GM', 'AGM', 'DESIGN_MGR']:
            return queryset.filter(scope__in=['DESIGN', 'BOTH'])

        # ✅ 2. مديرو الإشراف
        if user.role in ['SUP_MGR', 'PM']:
            return queryset.filter(scope__in=['SUPERVISION', 'BOTH'])

        # ✅ 3. المحاسب — يرى الكل
        if user.role == 'ACCOUNTANT':
            return queryset

        # ✅ 4. السكرتارية حسب القسم
        if user.role == 'SECRETARY':
            if user.department == 'Design':
                return queryset.filter(scope__in=['DESIGN', 'BOTH'])
            if user.department == 'Supervision':
                return queryset.filter(scope__in=['SUPERVISION', 'BOTH'])
            return queryset

        # ✅ 5. المهندسون والرسامون حسب القسم (مش حسب المهام المسندة)
        if user.role in ['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN', 'SITE_ENGINEER', 'DESIGN_ENGINEER']:
            if user.department == 'Design':
                return queryset.filter(scope__in=['DESIGN', 'BOTH'])
            if user.department == 'Supervision':
                return queryset.filter(scope__in=['SUPERVISION', 'BOTH'])
            return queryset.none()

        return queryset.none()


class ClosedProjectsAPIView(ProjectListAPIView):
    queryset = Project.objects.filter(is_active=False).order_by('-created_at')


class ProjectCreateAPIView(generics.CreateAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectCreateSerializer
    permission_classes = [IsAuthenticated, CanCreateProject]

    DESIGN_LIFECYCLE = [
        ('OFFER',              'RFQ / Offer',        1),
        ('CONTRACT_SUBMITTED', 'Contract Submitted', 2),
        ('CONTRACT_SIGNED',    'Contract Signed',    3),
        ('CONCEPT',            'Concept Design',     4),
        ('DC1',                'DC1',                5),
        ('DC2',                'DC2',                6),
        ('TENDER',             'Tender Documents',   7),
    ]
    SUPERVISION_LIFECYCLE = [
        ('OFFER',              'Offer',              1),
        ('CONTRACT_SUBMITTED', 'Contract Submit',    2),
        ('CONTRACT_SIGNED',    'Signed',             3),
        ('COLLECTION',         'Collection',         4),
        ('CLOSED',             'Closed',             5),
    ]

    def _create_lifecycle_stages(self, project):
        if project.scope == project.Scope.SUPERVISION:
            stages = [('OFFER', 1), ('CONTRACT_SUBMITTED', 2), ('CONTRACT_SIGNED', 3),
                      ('COLLECTION', 4), ('CLOSED', 5)]
        else:
            stages = [('OFFER', 1), ('CONTRACT_SUBMITTED', 2), ('CONTRACT_SIGNED', 3),
                      ('CONCEPT', 4), ('DC1', 5), ('DC2', 6), ('TENDER', 7), ('CLOSED', 8)]
        ProjectLifecycleStage.objects.bulk_create([
            ProjectLifecycleStage(
                project=project, stage_name=n, sequence_order=o,
                status=(ProjectLifecycleStage.Status.IN_PROGRESS if o == 1
                        else ProjectLifecycleStage.Status.UPCOMING),
            ) for n, o in stages
        ])


    def _create_discipline_trackings(self, project):
        """
        إنشاء سجلات DisciplineTracking تلقائياً لكل العناصر النشطة.
        بدونها، المحرك لن يجد بيانات يفحصها عند DC1/DC2.
        """
        from .models import DisciplineItem, DisciplineTracking
        for item in DisciplineItem.objects.filter(is_active=True):
            DisciplineTracking.objects.get_or_create(
                project=project,
                discipline_item=item,
                defaults={'status': 'PENDING'}
            )

    def perform_create(self, serializer):
        data = self.request.data

        extra = {}
        if not data.get('contractor') and data.get('contractor_name'):
            contractor, _ = Contractor.objects.get_or_create(
                name=data['contractor_name'],
                defaults={
                    'contact_person': data.get('contractor_contact_person', ''),
                    'phone':          data.get('contractor_phone', ''),
                    'email':          data.get('contractor_email', ''),
                },
            )
            extra['contractor'] = contractor

        project = serializer.save(**extra)
        # ✅ ربط المقاولين المتعددين (إشراف فقط) + مزامنة الأول للعرض القديم
        contractor_ids = data.get('contractors') or []
        if contractor_ids:
            project.contractors.set(contractor_ids)
            if not project.contractor_id:
                project.contractor_id = contractor_ids[0]
                project.save(update_fields=['contractor'])
        self._create_lifecycle_stages(project)
        self._create_discipline_trackings(project)

        stage_count = project.lifecycle_stages.count()
        AuditLog.objects.create(
            project=project,
            user=self.request.user,
            action_type=AuditLog.ActionType.PROJECT_CREATED,
            details=(
                f"Project '{project.name}' created with scope {project.scope}. "
                f"Client: {project.client.name if project.client else 'N/A'}. "
                f"{stage_count} lifecycle stages auto-created."
            ),
        )

        if project.internal_design_review_required:
            project.activate_internal_design_review()
            AuditLog.objects.create(
                project=project,
                user=self.request.user,
                action_type=AuditLog.ActionType.PROJECT_UPDATED,
                details="Internal Design Review activated with 5 stages",
            )


class ProjectDetailAPIView(generics.RetrieveAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectDetailSerializer
    permission_classes = [permissions.IsAuthenticated, ProjectDirectoryAccess]

class ProjectUpdateAPIView(generics.UpdateAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectCreateSerializer
    permission_classes = [permissions.IsAuthenticated, CanEditProjectByDepartment]
    
    def perform_update(self, serializer):
        project = serializer.save()
        AuditLog.objects.create(
            project=project,
            user=self.request.user,
            action_type=AuditLog.ActionType.PROJECT_UPDATED,
            details=f"Project '{project.name}' updated by {self.request.user.get_full_name()}"
        )
class ProjectDeleteAPIView(generics.DestroyAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectListSerializer
    permission_classes = [permissions.IsAuthenticated]

class ActiveProjectsAPIView(ProjectListAPIView):
    queryset = Project.objects.filter(is_active=True).order_by('-created_at')


class PendingProjectsAPIView(ProjectListAPIView):
    queryset = Project.objects.filter(permit_status=Project.PermitStatus.PENDING_AUTHORITY).order_by('-created_at')

class DesignProjectsAPIView(ProjectListAPIView):
    queryset = Project.objects.filter(scope=Project.Scope.DESIGN).order_by('-created_at')

class SupervisionProjectsAPIView(ProjectListAPIView):
    queryset = Project.objects.filter(scope=Project.Scope.SUPERVISION).order_by('-created_at')

class SharedProjectsAPIView(ProjectListAPIView):
    queryset = Project.objects.filter(scope=Project.Scope.BOTH).order_by('-created_at')

class ProjectPriorityAPIView(generics.UpdateAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectListSerializer
    permission_classes = [permissions.IsAuthenticated, IsDesignManagerOrManagement]

    def perform_update(self, serializer):
        project = serializer.save()
        PriorityHistory.objects.create(
            project=project,
            priority=project.priority,
            reason=self.request.data.get('reason', 'تم تعديل الأولوية بدون ذكر سبب'),
            updated_by=self.request.user
        )
        AuditLog.objects.create(
            project=project,
            user=self.request.user,
            action_type=AuditLog.ActionType.PRIORITY_CHANGED,
            details=f"Priority changed to {project.priority}"
        )

class PriorityHistoryAPIView(generics.ListAPIView):
    serializer_class = PriorityHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project = get_object_or_404(Project, pk=self.kwargs.get('pk'))
        return PriorityHistory.objects.filter(project=project).order_by('-created_at')

class ProjectChangeOrderAPIView(generics.CreateAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectListSerializer
    permission_classes = [permissions.IsAuthenticated, IsSecretary | IsDesignManagerOrManagement]

    def perform_create(self, serializer):
        parent = get_object_or_404(Project, pk=self.kwargs.get('pk'))
        serializer.save(parent_project=parent, is_active=True)
        AuditLog.objects.create(
            project=parent,
            user=self.request.user,
            action_type=AuditLog.ActionType.REVISION_CREATED,
            details=f"Change Order created for project {parent.project_no}"
        )

class ProjectRevisionAPIView(ProjectChangeOrderAPIView):
    pass

class SubProjectsAPIView(ProjectListAPIView):
    def get_queryset(self):
        parent = get_object_or_404(Project, pk=self.kwargs.get('pk'))
        return Project.objects.filter(parent_project=parent).order_by('-created_at')


class DC1StatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        trackings = project.discipline_trackings.filter(discipline_item__stage='DC1')
        total = trackings.count()
        completed = trackings.filter(status__in=['COMPLETED', 'APPROVED']).count()
        return Response({
            "stage": "DC1",
            "total": total,
            "completed": completed,
            "is_complete": total > 0 and completed == total,
            "items": DisciplineTrackingSerializer(trackings, many=True).data
        })

class DC2StatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        trackings = project.discipline_trackings.filter(discipline_item__stage='DC2')
        total = trackings.count()
        completed = trackings.filter(status__in=['COMPLETED', 'APPROVED']).count()
        return Response({
            "stage": "DC2",
            "total": total,
            "completed": completed,
            "is_complete": total > 0 and completed == total,
            "items": DisciplineTrackingSerializer(trackings, many=True).data
        })
class StructuralStatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated,IsMohammadMostafa]

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)

        discipline_item = DisciplineItem.objects.filter(
            stage='DC1',
            department='STRUCT'
        ).first()

        if not discipline_item:
            return Response(
                {
                    "status": "NOT_FOUND",
                    "message": "Discipline Item 'STRUCT DC1' is missing in Master Data settings."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        tracking, created = project.discipline_trackings.get_or_create(
            discipline_item=discipline_item,
            defaults={'status': 'PENDING'}
        )

        return Response({
            "status": tracking.status,
            "start_date": tracking.start_date,
            "end_date": tracking.end_date,
            "hold_date": tracking.hold_date,
            "hold_reason": tracking.hold_reason,
            "expected_resume_date": tracking.expected_resume_date,
            "is_on_hold": tracking.status == 'ON_HOLD'
        })

    def patch(self, request, pk):
        if not (
            request.user.username == 'mohammad.mostafa'
            or request.user.role in ['GM', 'AGM', 'DESIGN_MGR']
        ):
            return Response(
                {"detail": "Only Mohammad Mostafa or managers can update."},
                status=status.HTTP_403_FORBIDDEN
            )

        project = get_object_or_404(Project, pk=pk)

        discipline_item = DisciplineItem.objects.filter(
            stage='DC1',
            department='STRUCT'
        ).first()

        if not discipline_item:
            return Response(
                {"detail": "Discipline Item 'STRUCT DC1' is missing in Master Data."},
                status=status.HTTP_404_NOT_FOUND
            )

        tracking, created = project.discipline_trackings.get_or_create(
            discipline_item=discipline_item,
            defaults={'status': 'PENDING'}
        )

        new_status = request.data.get('status')

        if new_status:
            prev_status = tracking.status
            tracking.status = new_status

            if new_status in ['COMPLETED', 'APPROVED']:
                tracking.end_date = timezone.now().date()

            if new_status == 'ON_HOLD':
                tracking.hold_date = timezone.now().date()
                tracking.hold_reason = (
                    request.data.get('hold_reason')
                    or tracking.hold_reason
                )

            if (
                new_status != 'ON_HOLD'
                and prev_status == 'ON_HOLD'
            ):
                tracking.expected_resume_date = timezone.now().date()

            tracking.save()

            if new_status in ['COMPLETED', 'APPROVED']:
                shaaban = User.objects.filter(
                    username='shaaban.karam'
                ).first()

                if shaaban:
                    Notification.objects.create(
                        user=shaaban,
                        sender=request.user,
                        notification_type="STRUCTURAL_COMPLETED",
                        title="Structural Completed",
                        message=f"Structural for project {project.project_no} is completed. IFC can start."
                    )

            AuditLog.objects.create(
                project=project,
                user=request.user,
                action_type=AuditLog.ActionType.DISCIPLINE_STATUS_CHANGED,
                details=f"Structural status {prev_status} -> {new_status}"
            )

        project.evaluate_and_advance_lifecycle(actor=request.user)

        return Response(
            DisciplineTrackingSerializer(tracking).data,
            status=status.HTTP_200_OK
        )
class IFCStatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)

        discipline_item = DisciplineItem.objects.filter(
            stage='DC2',
            name__icontains='IFC'
        ).first()

        if not discipline_item:
            discipline_item = DisciplineItem.objects.filter(
                stage='DC2',
                department='ARCH',
                name__icontains='IFC'
            ).first()

        if not discipline_item:
            return Response(
                {
                    "status": "NOT_FOUND",
                    "message": "Discipline Item for IFC (Stage DC2) is missing in Master Data."
                }, 
                status=status.HTTP_404_NOT_FOUND
            )

        tracking, created = project.discipline_trackings.get_or_create(
            discipline_item=discipline_item,
            defaults={'status': 'PENDING'}
        )

        return Response({
            "status": tracking.status,
            "start_date": tracking.start_date,
            "end_date": tracking.end_date
        }, status=status.HTTP_200_OK)

    def patch(self, request, pk):
        # التحقق من الصلاحيات (لتجنب خطأ 403 Forbidden)
        if not (
            request.user.username in ['shaaban.karam', 'israa.omran']
        ):
            return Response(
                {"detail": "Only Shaaban Karam, Israa Omran can update IFC status."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        project = get_object_or_404(Project, pk=pk)

        discipline_item = DisciplineItem.objects.filter(
            stage='DC2',
            name__icontains='IFC'
        ).first()

        if not discipline_item:
            discipline_item = DisciplineItem.objects.filter(
                stage='DC2',
                department='ARCH',
                name__icontains='IFC'
            ).first()

        if not discipline_item:
            return Response(
                {"detail": "Discipline Item for IFC is missing in Master Data."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        tracking, created = project.discipline_trackings.get_or_create(
            discipline_item=discipline_item,
            defaults={'status': 'PENDING'}
        )
        
        new_status = request.data.get('status')
        if new_status:
            tracking.status = new_status
            
            if new_status in ['COMPLETED', 'APPROVED']:
                tracking.end_date = timezone.now().date()
                
            tracking.save()
        
        project.evaluate_and_advance_lifecycle(actor=request.user)

        return Response(
            DisciplineTrackingSerializer(tracking).data, 
            status=status.HTTP_200_OK
        )
class ProjectProgressAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        total_stages = project.lifecycle_stages.count()
        if total_stages == 0:
            return Response({"progress": "0.0%", "completed": 0, "total": 0})
        completed = project.lifecycle_stages.filter(status='ACHIEVED').count()
        return Response({
            "progress": f"{round((completed / total_stages) * 100, 2)}%",
            "completed": completed,
            "total": total_stages
        })




class ProjectCardsAPIView(generics.ListAPIView):
    serializer_class = ProjectCardSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['scope', 'is_active', 'priority', 'permit_status', 'client']
    search_fields = ['name', 'project_no', 'application_no', 'client__name']
    ordering_fields = ['start_date', 'created_at', 'priority']

    def get_queryset(self):
        queryset = Project.objects.select_related(
            'client', 'contractor'
        ).prefetch_related(
            'lifecycle_stages', 'tasks', 'notes'
        ).order_by('-start_date', '-priority')
        
        # فلترة إضافية
        scope = self.request.query_params.get('scope')
        if scope:
            queryset = queryset.filter(scope=scope)
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset


class LifecycleListAPIView(generics.ListAPIView):
    serializer_class = ProjectLifecycleStageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = ProjectLifecycleStage.objects.all().order_by('sequence_order')
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset



class LifecycleUpdateAPIView(generics.UpdateAPIView):
    queryset = ProjectLifecycleStage.objects.all()
    serializer_class = ProjectLifecycleStageSerializer
    permission_classes = [IsAuthenticated, IsDesignManagerOrManagement | IsDesignSecretary]
    def _validate_sequence(self, instance):
        previous = ProjectLifecycleStage.objects.filter(
            project=instance.project,
            sequence_order__lt=instance.sequence_order,
        ).exclude(status='ACHIEVED')
        if previous.exists():
            names = ', '.join(s.get_stage_name_display() for s in previous)
            raise ValidationError(
                f"Cannot update this stage. Achieve first: {names}"
            )

    def _check_and_close_project(self, project):
        stages = project.lifecycle_stages.all()
        total = stages.count()
        if total == 0:
            return False
        if stages.filter(status='ACHIEVED').count() == total:
            if project.is_active:
                project.is_active = False
                project.save(update_fields=['is_active'])
                AuditLog.objects.create(
                    project=project,
                    user=self.request.user,
                    action_type=AuditLog.ActionType.PROJECT_UPDATED,
                    details="Project automatically CLOSED — all lifecycle stages ACHIEVED.",
                )
            return True
        return False

    def perform_update(self, serializer):
        instance = self.get_object()
        self._validate_sequence(instance)
        project = instance.project
        instance = serializer.save()
        if instance.actual_date and instance.status != 'ACHIEVED':
            instance.status = 'ACHIEVED'
            instance.save(update_fields=['status'])
            variance = ''
            if instance.planned_date:
                delta = (instance.actual_date - instance.planned_date).days
                if delta < 0:   variance = f" (Early by {abs(delta)}d)"
                elif delta > 0: variance = f" (Late by {delta}d)"
                else:           variance = " (On time)"
            AuditLog.objects.create(
                project=project,
                user=self.request.user,
                action_type=AuditLog.ActionType.STAGE_ACTUAL_DATE_UPDATED,
                details=f"Stage {instance.stage_name} ACHIEVED{variance}",
            )
        self._check_and_close_project(project)

class LifecycleAdvanceAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsDesignManagerOrManagement]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        target = request.data.get('stage_name')
        
        advanced = project.evaluate_and_advance_lifecycle(actor=request.user)
        resp = {'advanced': advanced}
        
        if target:
            st = project.lifecycle_stages.filter(stage_name=target).first()
            if not st or st.status != 'ACHIEVED':
                resp['blocked'] = target
                resp['reasons'] = project._missing_reasons(target)
                
        return Response(resp, status=status.HTTP_200_OK)


class MarkDeliveredAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsDesignManagerOrManagement]

    def post(self, request, pk):
        from django.utils import timezone
        project = get_object_or_404(Project, pk=pk)
        
        project.delivered = True
        project.delivered_date = timezone.now().date()
        project.save(update_fields=['delivered', 'delivered_date'])
        
        # إعادة تقييم المحرك بعد التسليم
        project.evaluate_and_advance_lifecycle(actor=request.user)
        
        AuditLog.objects.create(
            project=project,
            user=request.user,
            action_type=AuditLog.ActionType.PROJECT_UPDATED,
            details="Project marked as DELIVERED"
        )
        return Response({'delivered': True, 'delivered_date': project.delivered_date}, status=status.HTTP_200_OK)


class CloseProjectAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsDesignManagerOrManagement]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        ok, reasons = project.close_project(actor=request.user)
        
        if not ok:
            return Response(
                {'detail': 'لا يمكن الإغلاق بعد', 'reasons': reasons},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        return Response({'closed': True, 'closed_date': project.closed_date}, status=status.HTTP_200_OK)

    
class LifecycleAnalyticsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        project_id = request.query_params.get('project_id')
        queryset = ProjectLifecycleStage.objects.all()
        if project_id:
            queryset = queryset.filter(project_id=project_id)
            
        total_stages = queryset.count()
        if total_stages == 0:
            return Response({
                "upcoming": 0, "overdue": 0, "late": 0, "early": 0,
                "on_time": 0, "progress_percentage": "0.0%"
            }, status=status.HTTP_200_OK)

        now = timezone.now().date()
        upcoming = queryset.filter(status='UPCOMING').count()
        overdue = queryset.filter(
            ~Q(status='ACHIEVED'),
            planned_end_date__lt=now
        ).count()
        late = queryset.filter(
            status='ACHIEVED',
            actual_end_date__gt=F('planned_end_date')
        ).count()
        early = queryset.filter(
            status='ACHIEVED',
            actual_end_date__lt=F('planned_end_date')
        ).count()
        on_time = queryset.filter(
            status='ACHIEVED',
            actual_end_date=F('planned_end_date')
        ).count()

        completed_count = queryset.filter(status='ACHIEVED').count()
        progress_percentage = round((completed_count / total_stages) * 100, 2)

        return Response({
            "total_stages": total_stages,
            "upcoming": upcoming,
            "overdue": overdue,
            "late": late,
            "early": early,
            "on_time": on_time,
            "progress_percentage": f"{progress_percentage}%"
        }, status=status.HTTP_200_OK)


class InternalReviewListAPIView(generics.ListAPIView):
    serializer_class = InternalReviewStageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = InternalReviewStage.objects.all().select_related('project', 'assigned_to', 'approved_by')
        project_id = self.request.query_params.get('project_id')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

class InternalReviewUpdateAPIView(generics.UpdateAPIView):
    queryset = InternalReviewStage.objects.all()
    serializer_class = InternalReviewStageSerializer
    permission_classes = [permissions.IsAuthenticated, IsAssignedEngineerOrManager]

    def perform_update(self, serializer):
        serializer.save()

class InternalReviewApproveAPIView(generics.UpdateAPIView):
    queryset = InternalReviewStage.objects.all()
    serializer_class = InternalReviewStageSerializer
    permission_classes = [permissions.IsAuthenticated, IsDesignManagerOrManagement]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status == 'APPROVED':
            return Response(
                {"detail": "هذه المرحلة معتمدة ومغلقة بالفعل."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        instance.status = 'APPROVED'
        instance.approved_by = request.user
        instance.approved_at = timezone.now()
        instance.save()
        
        AuditLog.objects.create(
            project=instance.project,
            user=request.user,
            action_type=AuditLog.ActionType.TASK_APPROVED,
            details=f"Internal Review {instance.stage_name} approved"
        )
        
        serializer = self.get_serializer(instance)
        return Response(
            {"message": "تم اعتماد مراجعة المرحلة بنجاح.", "data": serializer.data},
            status=status.HTTP_200_OK
        )


class TenderingDetailAPIView(generics.RetrieveAPIView):
    serializer_class = TenderingModuleSerializer
    permission_classes = [permissions.IsAuthenticated, TenderingPermission]

    def get_object(self):
        project_id = self.kwargs.get('project_id')
        return get_object_or_404(TenderingModule, project_id=project_id)

class TenderingUpdateAPIView(generics.UpdateAPIView):
    serializer_class = TenderingModuleSerializer
    permission_classes = [permissions.IsAuthenticated, TenderingPermission]

    def get_object(self):
        project_id = self.kwargs.get('project_id')
        return get_object_or_404(TenderingModule, project_id=project_id)
    
class TenderingCreateAPIView(generics.CreateAPIView):
    queryset = TenderingModule.objects.all()
    serializer_class = TenderingModuleSerializer
    permission_classes = [permissions.IsAuthenticated, TenderingPermission]


class TaskResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

def restrict_tasks_by_department(qs, user):
    """✅ فصل كامل: التصميم يرى التصميم فقط، الإشراف يرى الإشراف فقط، وزبادي يرى الكل"""
        # الاستثناء الوحيد: أحمد زبادي يرى جميع المهام
    if user.username == 'ahmed.zabady':
        return qs

    is_supervision_side = (
        user.department == 'Supervision'
        or user.role in ['SUP_MGR', 'PM']
        or is_supervision_engineer(user)
    )
    if is_supervision_side:
            # موظفو/مهندسو الإشراف → مهام الإشراف (والمشتركة) فقط
        return qs.filter(
            Q(task_type=Task.TaskType.SUPERVISION) |
            Q(project__scope__in=[Project.Scope.SUPERVISION, Project.Scope.BOTH])
        )

        # التصميم + ناصر/نسرين/فهمي → مهام التصميم فقط (بدون أي مهمة إشراف)
    return qs.exclude(
        Q(task_type=Task.TaskType.SUPERVISION) |
        Q(project__scope=Project.Scope.SUPERVISION)
    )

class TaskListAPIView(generics.ListAPIView):
    queryset = Task.objects.select_related('project', 'assigned_to', 'discipline').order_by('-created_at')
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = TaskResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    # ✅ حذفنا 'stage' من filterset_fields — لأن DjangoFilterBackend يرفض OTHER
    #    (ليس ضمن MasterDiscipline.Stage.choices) ويعطي 400 قبل وصول الطلب لكودنا.
    #    سنعالج فلتر Stage يدوياً داخل get_queryset بالأسفل.
    filterset_fields = ['project', 'assigned_to', 'status', 'priority', 'is_on_hold']

    search_fields = ['title', 'project__name', 'project__project_no', 'assigned_to__username', 'discipline__name',        'assigned_to__first_name', 'assigned_to__last_name']
    ordering_fields = ['start_date', 'created_at', 'priority']

    def get_queryset(self):
        qs = super().get_queryset()
        qs = restrict_tasks_by_department(qs, self.request.user)   # ✅ السطر الوحيد الجديد

        # ✅ فلتر Stage يدوياً مع معاملة خاصة لـ "Other"
        stage = self.request.query_params.get('stage')
        if stage == 'OTHER':
            # ✅ مهام Other = مهام بدون Stage (NULL أو فارغ) أو المخزنة بقيمة 'OTHER'
            qs = qs.filter(
                Q(stage__isnull=True) | Q(stage='') | Q(stage='OTHER')
            )
        elif stage:
            # باقي المراحل تعمل كما كانت (CONCEPT / DC1 / DC2 / TENDER)
            qs = qs.filter(stage=stage)

        department = self.request.query_params.get('department')
        if department:
            qs = qs.filter(discipline__department=department)
        return qs
class TaskCreateAPIView(generics.CreateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, CanCreateTask]

    def _get_boolean(self, key):
        value = self.request.data.get(key)

        if isinstance(value, bool):
            return value

        if value is None:
            return False

        return str(value).strip().lower() in ('1', 'true', 'on', 'yes')

    def _prepare_main_design_task(self,validated_data):
        user = self.request.user

        project = validated_data.get('project')

        if not project:
                raise ValidationError({'project': 'Project is required.'})


        # ✅ لو في review_stage من الخيار B — اعثر على المرحلة أو أنشئها
        extra = {}
        review_stage = self.request.data.get('review_stage')
        if review_stage:
            stage_obj = project.internal_reviews.filter(stage_name=review_stage).first()
            if not stage_obj:
                last = project.internal_reviews.order_by('-sequence_order').first()
                stage_obj = project.internal_reviews.create(
                    stage_name=review_stage,
                    sequence_order=(last.sequence_order + 1 if last else 1))
            extra['internal_review_stage'] = stage_obj

        # ✅ الخيار B (supervision_project + review_stage) يُسمح فيه بمشاريع SUPERVISION
        is_option_b = bool(review_stage)
        
        if not is_option_b and project.scope not in [Project.Scope.DESIGN, Project.Scope.BOTH]:
            raise ValidationError({
                'project': 'Main design tasks are only for Design or Both projects.'
            })

        assigned_to_id = self.request.data.get('assigned_to')
        assignee = None

        if assigned_to_id:
            assignee = get_object_or_404(User, pk=assigned_to_id)

    # المهندس/الرسام يعيّن نفسه فقط
        if user.role in ['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN']:
            if assignee and str(assignee.id) != str(user.id):
             # تحقق: هل عنده صلاحية يعيّن هذا الشخص؟
                if not can_assign_design_task(user, assignee, user):
                    raise ValidationError({
                        'assigned_to': 'You are not allowed to assign tasks to this user.'
                 })
            else:
                assignee = user

        if not assignee:
            raise ValidationError({'assigned_to': 'Assigned user is required.'})

    # تأكد إن المعين له ضمن قائمة التصميم
    # ✅ المدراء (GM/AGM/DESIGN_MGR) يمكنهم تعيين أنفسهم حتى لو مش في القائمة
        if assignee.username not in DESIGN_TASK_ASSIGNEE_USERNAMES:
            if assignee.role not in ['GM', 'AGM', 'DESIGN_MGR']:
                raise ValidationError({'assigned_to': 'Only design team members can be assigned.'})

        return {'assigned_to': assignee}


    def _prepare_supervision_task(self):
        """
        Supervision:
        - أحمد زبادي / PM العام → أي مشروع إشراف.
        - PM المشروع (is_pm=True) → مشروعه فقط.
        - مهندس إشراف عادي → يعيّن نفسه فقط.
        """
        user = self.request.user

        project_id = self.request.data.get('project')
        if not project_id:
            raise ValidationError({'project': 'Supervision project is required.'})

        project = get_object_or_404(Project, pk=project_id)

        if project.scope not in [Project.Scope.SUPERVISION, Project.Scope.BOTH]:
            raise ValidationError({
                'project': 'Supervision tasks are only allowed for Supervision projects.'
            })

        assigned_to_id = self.request.data.get('assigned_to')
        if not assigned_to_id:
            raise ValidationError({'assigned_to': 'Assigned engineer is required.'})

        assignee = get_object_or_404(User, pk=assigned_to_id)

        # ── تحديد مستوى الصلاحية ──
        manager    = is_supervision_task_manager(user)
        project_pm = is_project_pm(user, project)
        engineer   = is_supervision_engineer(user)

        if not (manager or project_pm or engineer):
            raise PermissionDenied(
                'Only Ahmed Zabady, PM, project PM, or supervision engineers '
                'can create supervision tasks.'
            )

        # ── PM المشروع لا يستطيع إنشاء مهمة لمشروع ليس PM عليه ──
        if project_pm and not manager:
            if not SupervisionTeamAssignment.objects.filter(
                project=project, engineer=user, is_pm=True
            ).exists():
                raise PermissionDenied(
                    'You are not a PM for this project.'
                )

        # ── المهندس العادي يعيّن نفسه فقط ──
        if engineer and not project_pm and not manager:
            if str(assignee.id) != str(user.id):
                raise ValidationError({
                    'assigned_to': 'Supervision engineers can only assign tasks to themselves.'
                })

        # ── فقط مهندسو الإشراف يمكن تعيينهم ──
        if assignee.username not in SUPERVISION_ENGINEER_USERNAMES:
            raise ValidationError({
                'assigned_to': 'Only supervision engineers can be assigned to supervision tasks.'
            })

        # ── التحقق من عضوية الفريق (للمدير و PM المشروع) ──
        if manager or project_pm:
            project_team = project.supervision_team.all()
            if project_team.exists() and not project_team.filter(engineer=assignee).exists():
                raise ValidationError({
                    'assigned_to': 'The selected engineer is not assigned to this supervision project.'
                })

        # ── On Hold ──
        is_on_hold = self._get_boolean('is_on_hold')
        hold_reason = (self.request.data.get('hold_reason') or '').strip()

        if is_on_hold and not hold_reason:
            raise ValidationError({
                'hold_reason': 'Hold reason is required when task is On Hold.'
            })

        hold_date = None
        if is_on_hold:
            raw_hold_date = self.request.data.get('hold_date')
            if raw_hold_date:
                hold_date = parse_date(raw_hold_date)
                if not hold_date:
                    raise ValidationError({'hold_date': 'Invalid hold date.'})
            else:
                hold_date = timezone.now().date()

        return {
            'task_type': Task.TaskType.SUPERVISION,
            'assigned_to': assignee,
            'status': Task.Status.ON_HOLD if is_on_hold else Task.Status.UNCHARTED,
            'is_on_hold': is_on_hold,
            'hold_reason': hold_reason if is_on_hold else None,
            'hold_date': hold_date,
            'expected_resume_date': None,
            'discipline': None,
            'stage': None,
        }

    def _prepare_internal_review_task(self):
        user = self.request.user

        project_id = self.request.data.get('project')
        if not project_id:
            raise ValidationError({'project': 'Supervision project is required.'})

        project = get_object_or_404(Project, pk=project_id)

        if project.scope != Project.Scope.SUPERVISION:
            raise ValidationError({
                'project': 'Internal review tasks are only allowed for supervision projects.'
            })

        if not project.internal_design_review_required:
            raise ValidationError({
                'project': 'Internal review tasks are only allowed for projects with Internal Design Review enabled.'
            })

        assigned_to_id = self.request.data.get('assigned_to')

        if assigned_to_id:
            assignee = get_object_or_404(User, pk=assigned_to_id, is_active=True)
        else:
            assignee = user

        is_general_manager = user.username in SUPERVISION_TASK_MANAGER_USERNAMES
        is_pm_user = user.role == 'PM' or is_project_pm_any(user)

        # PM يقدر يضيف فقط للمشروع الذي هو PM عليه
        if is_pm_user and not is_general_manager and not is_project_pm(user, project):
            raise PermissionDenied(
                'PM can add internal review tasks only to his assigned project.'
            )

        if assignee == user:
            allowed_self_roles = [
                'ENGINEER',
                'SENIOR_ENG',
                'DESIGN_MGR',
                'PM',
                'GM',
                'AGM',
                'SUP_MGR',
            ]

            if not (
                is_general_manager or
                is_pm_user or
                user.role in allowed_self_roles
            ):
                raise PermissionDenied(
                    'Only engineers can self-assign internal review tasks.'
                )

        else:
            can_assign_others = is_general_manager or is_project_pm(user, project)

            if not can_assign_others:
                raise ValidationError({
                    'assigned_to': 'You can only assign internal review tasks to yourself.'
                })

            if assignee.role not in ['ENGINEER', 'SENIOR_ENG', 'DESIGN_MGR']:
                raise ValidationError({
                    'assigned_to': 'Internal review tasks can be assigned to engineers only.'
                })

        extra = {
            'task_type': Task.TaskType.INTERNAL_REVIEW,
            'assigned_to': assignee,
        }

        stage_name = (
            self.request.data.get('internal_review_stage_name') or ''
        ).strip()

        if stage_name and stage_name != 'OTHER':
            stage = project.internal_reviews.filter(
                stage_name=stage_name
            ).first()

            if not stage:
                project.activate_internal_design_review(requested_by=user)
                stage = project.internal_reviews.filter(
                    stage_name=stage_name
                ).first()

            if not stage:
                raise ValidationError({
                    'internal_review_stage_name':
                        'Selected review stage does not exist for this project.'
                })

            extra['internal_review_stage'] = stage

        else:
            extra['internal_review_stage'] = None

        return extra
    def _prepare_legacy_task(self):
        """
        للحفاظ على السلوك القديم في Change Order / Internal Review.
        """
        extra = {}

        if self.request.user.role in ['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN']:
            assigned_to_id = self.request.data.get('assigned_to')

            if assigned_to_id and str(assigned_to_id) != str(self.request.user.id):
                raise ValidationError({
                    'assigned_to': 'You can only assign tasks to yourself.'
                })

            if not assigned_to_id:
                extra['assigned_to'] = self.request.user

        return extra

    def perform_create(self, serializer):
        task_type = self.request.data.get(
            'task_type',
            Task.TaskType.MAIN_DESIGN
        )

        if task_type == Task.TaskType.SUPERVISION:
            extra = self._prepare_supervision_task()

        elif task_type == Task.TaskType.INTERNAL_REVIEW:
            extra = self._prepare_internal_review_task()

        elif task_type == Task.TaskType.MAIN_DESIGN:
            extra = self._prepare_main_design_task(serializer.validated_data)

        else:
            extra = self._prepare_legacy_task()
        task = serializer.save(**extra)

        if (
            task.task_type == Task.TaskType.INTERNAL_REVIEW and
            task.internal_review_stage_id
        ):
            stage = task.internal_review_stage

            if stage.status == InternalReviewStage.Status.PENDING:
                stage.status = InternalReviewStage.Status.UNDER_REVIEW
                stage.updated_at = timezone.now()
                stage.save(update_fields=['status', 'updated_at'])

            if task.assigned_to:
                task.project.internal_review_assignees.add(task.assigned_to)

        task_name = (
            task.title or
            (task.discipline.name if task.discipline else task.get_task_type_display())
        )

        AuditLog.objects.create(
            project=task.project,
            task=task,
            user=self.request.user,
            action_type=AuditLog.ActionType.TASK_CREATED,
            details=f"Task created: {task_name}"
        )
        # ✅ إشعار للمستلم أن مهمة جديدة أُسندت له
        _notify_task_assignee(task, self.request.user, kind='ASSIGNED')

class TaskDetailAPIView(generics.RetrieveAPIView):
    queryset = Task.objects.select_related('project', 'assigned_to', 'discipline')
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, TaskManagementPermission]

class TaskUpdateAPIView(generics.UpdateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, TaskManagementPermission]

class TaskDeleteAPIView(generics.DestroyAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, TaskManagementPermission]

class MyTasksAPIView(generics.ListAPIView):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination   # ✅ إضافة Pagination (20 عنصر لكل صفحة)
    filterset_fields = ['status', 'priority', 'task_type']

    def get_queryset(self):
        # ✅ استثناء Change Orders و Internal Reviews من Main Tasks
        qs = Task.objects.filter(
            assigned_to=self.request.user
        ).exclude(
            task_type__in=['CHANGE_ORDER', 'INTERNAL_REVIEW']
        )

        # ✅ فلترة يدوية مضمونة — نفس نمط GlobalFilterBarAPIView (بدون اعتماد على filter_backends)
        status = self.request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)
        priority = self.request.query_params.get('priority')
        if priority:
            qs = qs.filter(priority=priority)

        return qs.order_by('-created_at')
class InternalReviewTasksAPIView(generics.ListAPIView):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'priority']

    def get_queryset(self):
        return Task.objects.filter(
            assigned_to=self.request.user,
            project__internal_design_review_required=True
        ).order_by('-created_at')

class ChangeOrderTasksAPIView(generics.ListAPIView):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'priority']

    def get_queryset(self):
        return Task.objects.filter(
            assigned_to=self.request.user,
            project__parent_project__isnull=False
        ).order_by('-created_at')


class CreateChangeOrderAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSecretary | IsDesignManagerOrManagement]

    def post(self, request, pk):
        parent = get_object_or_404(Project, pk=pk)
        if not parent.is_active:  
            sub_project = Project.objects.create(
                parent_project=parent,
                name=f"{parent.name} - Change Order",
                project_no=f"{parent.project_no}-CO",
                revision_number=request.data.get('revision_number', 'Rev1'),
                new_application_no=request.data.get('new_application_no'),
                revision_start_date=request.data.get('revision_start_date'),
                change_order_reason=request.data.get('change_order_reason'),
                scope=parent.scope, client=parent.client, contractor=parent.contractor,
                is_active=True
            )
            return Response({
                "message": "Change Order (Sub Project) created.",
                "sub_project": ProjectListSerializer(sub_project).data
            })
        else: 
            tasks_data = request.data.get('tasks', [])
            created_tasks = []
            for task_data in tasks_data:
                task = Task.objects.create(
                    project=parent, task_type=Task.TaskType.CHANGE_ORDER,
                    assigned_to_id=task_data.get('assigned_to'),
                    discipline_id=task_data.get('discipline'),
                    stage=task_data.get('stage'), title=task_data.get('title'),
                    priority=task_data.get('priority', Project.PriorityStatus.MEDIUM),
                    status=Task.Status.UNCHARTED
                )
                created_tasks.append(task)
            return Response({
                "message": "Change Order tasks created.",
                "tasks": TaskSerializer(created_tasks, many=True).data
            })

class TaskStatusAPIView(generics.UpdateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated, TaskManagementPermission]

    def update(self, request, *args, **kwargs):
        task = self.get_object()
        data = request.data

        progress_value = task.progress_percentage

        if 'progress_percentage' in data:
            raw_progress = data.get('progress_percentage')

            try:
                progress_value = int(raw_progress)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "Progress must be a valid number."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if progress_value < 0 or progress_value > 100:
                return Response(
                    {"detail": "Progress must be between 0 and 100."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        updated_task = TaskService.update_status(
            task=task,
            new_status=data.get('status', task.status),
            user=request.user,
            is_on_hold=data.get('is_on_hold'),
            hold_reason=data.get('hold_reason'),
            expected_resume_date=data.get('expected_resume_date')
        )

        # ✅ هنا يتم حفظ نسبة التقدم فعليًا
        if int(updated_task.progress_percentage or 0) != progress_value:
            updated_task.progress_percentage = progress_value
            updated_task.save(update_fields=['progress_percentage'])

        updated_task.project.evaluate_and_advance_lifecycle(actor=request.user)

        return Response(self.get_serializer(updated_task).data)
class TaskAssignAPIView(generics.UpdateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, TaskManagementPermission]

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        task = self.get_object()
        assigned_to_id = request.data.get('assigned_to')
        
        if not assigned_to_id:
            return Response({"detail": "assigned_to required"}, status=status.HTTP_400_BAD_REQUEST)
            
        new_engineer = get_object_or_404(User, id=assigned_to_id)
        
        if new_engineer != request.user and request.user.role in ['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN']:
            return Response({"detail": "You can only assign tasks to yourself."}, status=status.HTTP_403_FORBIDDEN)
        
        if task.assigned_to == new_engineer:
            return Response({"detail": "Already assigned to this engineer"}, status=status.HTTP_400_BAD_REQUEST)
        
        is_self_assign = (new_engineer == request.user)
        task.assigned_to = new_engineer
        
        if not task.start_date:
            task.start_date = timezone.now().date()
            
        task.save()
        
        AuditLog.objects.create(
            project=task.project,
            task=task,
            user=request.user,
            action_type=AuditLog.ActionType.TASK_SELF_ASSIGNED if is_self_assign else AuditLog.ActionType.TASK_ASSIGNED,
            details=f"Assigned to {new_engineer.get_full_name()}"
        )
        
        return Response(self.get_serializer(task).data, status=status.HTTP_200_OK)
class TaskReassignAPIView(generics.UpdateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, TaskManagementPermission]

    def update(self, request, *args, **kwargs):
        task = self.get_object()
        new_engineer_id = request.data.get('new_engineer_id')
        reason = request.data.get('reason_for_change', 'No reason')
        if not new_engineer_id:
            return Response({"detail": "new_engineer_id required"}, status=status.HTTP_400_BAD_REQUEST)
        new_engineer = get_object_or_404(User, id=new_engineer_id)
        old_engineer = task.assigned_to
        if old_engineer == new_engineer:
            return Response({"detail": "Same engineer"}, status=status.HTTP_400_BAD_REQUEST)

        days_worked = 0
        if task.start_date:
            days_worked = (timezone.now().date() - task.start_date).days
            days_worked = max(days_worked, 0)

        if old_engineer:
            AssignmentHistory.objects.create(
                task=task,
                old_engineer=old_engineer,
                new_engineer=new_engineer,
                reason_for_change=reason,
                days_worked=days_worked,
                status_at_handover=task.status
            )
            StaffKPI.objects.create(
                user=old_engineer,
                project=task.project,
                task=task,
                days_worked=days_worked,
                status_at_handover=task.status,
                handover_date=timezone.now().date()
            )
            
        task.assigned_to = new_engineer
        task.save()
        
        AuditLog.objects.create(
            project=task.project,
            task=task,
            user=request.user,
            action_type=AuditLog.ActionType.TASK_ASSIGNED,
            details=f"Reassigned from {old_engineer.username if old_engineer else 'None'} to {new_engineer.username}. Reason: {reason}"
        )
        return Response(self.get_serializer(task).data, status=status.HTTP_200_OK)

class AssignmentHistoryAPIView(generics.ListAPIView):
    serializer_class = AssignmentHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        task_id = self.kwargs.get('pk')
        task = get_object_or_404(Task, pk=task_id)
        return AssignmentHistory.objects.filter(task=task).order_by('-created_at')
# ═══════════════════════════════════════════════════════════
# دالة مساعدة آمنة لعرض اسم المهمة (لا تنكسر أبداً)
# ═══════════════════════════════════════════════════════════
def _task_display_name(task):
    """
    اسم عرض آمن للمهمة — لا ينكسر أبداً.
    الأولوية: title → discipline.name → task_type_display → 'Untitled Task'
    """
    if task.title:
        return task.title
    if task.discipline:
        return task.discipline.name
    if hasattr(task, 'get_task_type_display'):
        return task.get_task_type_display()
    return 'Untitled Task'


class ReplacementRequestCreateAPIView(generics.CreateAPIView):
    queryset = ReplacementRequest.objects.all()
    serializer_class = ReplacementRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        print("REQUEST:", request.data)

        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            print("ERRORS:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        self.perform_create(serializer)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        task_id = self.kwargs.get('pk')
        task = get_object_or_404(Task, pk=task_id)

        if task.assigned_to != self.request.user:
            raise ValidationError("You can only request replacement for your own tasks.")

        replacement = serializer.save(task=task, requested_by=self.request.user)

        # ═══ توجيه الإشعار حسب قسم المشروع ═══
        project = task.project
        
        # ✅ كل جهة يُخطر مدراؤها فقط: طلب التصميم لا يصل لزبادي
        if project.scope == 'DESIGN':
            manager_roles = ['DESIGN_MGR', 'GM', 'AGM']
        elif project.scope == 'SUPERVISION':
            manager_roles = ['SUP_MGR', 'PM']
        else:
            manager_roles = ['DESIGN_MGR', 'GM', 'AGM', 'SUP_MGR', 'PM']
            
        managers = User.objects.filter(role__in=manager_roles)

        # ✅ استخدام الدالة المساعدة الآمنة
        task_name = _task_display_name(task)

        for manager in managers:
            Notification.objects.create(
                user=manager,
                sender=self.request.user,
                notification_type="REPLACEMENT_REQUEST",
                title=f"Replacement Request: {project.project_no}",
                message=f"{self.request.user.get_full_name()} requested replacement for task {task_name}"
            )

        # ═══ إشعار للمهندس المقترح (سلمان) ═══
        Notification.objects.create(
            user=replacement.suggested_engineer,
            sender=self.request.user,
            notification_type="REPLACEMENT_REQUEST_PENDING",
            title=f"Replacement Request: {project.project_no}",
            message=f"{self.request.user.get_full_name()} requested you to take task {task_name}"
        )

        AuditLog.objects.create(
            project=project,
            task=task,
            user=self.request.user,
            action_type=AuditLog.ActionType.REASSIGNMENT_REQUESTED,
            details=f"Replacement requested for task {task_name}"
        )


class ReplacementRequestRespondAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk=None):
        replacement = get_object_or_404(ReplacementRequest, pk=pk)

        if request.user.role not in ['SUP_MGR', 'PM', 'DESIGN_MGR', 'GM', 'AGM']:
            return Response(
                {"detail": "Only managers can respond."},
                status=status.HTTP_403_FORBIDDEN
            )

        if replacement.status in [ReplacementRequest.Status.APPROVED, ReplacementRequest.Status.REJECTED]:
            return Response(
                {"detail": "This request has already been processed."},
                status=status.HTTP_400_BAD_REQUEST
            )

        status_choice = request.data.get('status')
        response_reason = request.data.get('response_reason', '')

        if status_choice not in ['APPROVED', 'REJECTED']:
            return Response(
                {"detail": "Status must be APPROVED or REJECTED"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if status_choice == 'APPROVED' and replacement.engineer_response == 'DECLINE':
            return Response(
                {"detail": "The suggested engineer already declined this request."},
                status=status.HTTP_400_BAD_REQUEST
            )

        replacement.status = status_choice
        replacement.response_reason = response_reason
        replacement.responded_by = request.user
        replacement.responded_at = timezone.now()
        replacement.save()

        # ✅ الإصلاح: تعريف task قبل استخدامها
        task = replacement.task

        # ✅ عند الرفض: ترجع المهمة للمهندس الأصلي كما كانت
        if status_choice != 'APPROVED':
            _return_task_to_requester(replacement)

        if status_choice == 'APPROVED':
            # ✅ الآن task معرّفة ويمكن استخدامها
            _execute_task_handover(task, replacement.suggested_engineer, request.user)
            
            old_engineer = task.assigned_to
            new_engineer = replacement.suggested_engineer

            days_worked = 0
            if task.start_date:
                days_worked = max((timezone.now().date() - task.start_date).days, 0)

            if old_engineer:
                AssignmentHistory.objects.create(
                    task=task,
                    old_engineer=old_engineer,
                    new_engineer=new_engineer,
                    reason_for_change=f"Manager-approved replacement: {replacement.reason}",
                    days_worked=days_worked,
                    status_at_handover=task.status
                )
                StaffKPI.objects.create(
                    user=old_engineer,
                    project=task.project,
                    task=task,
                    days_worked=days_worked,
                    status_at_handover=task.status,
                    handover_date=timezone.now().date()
                )

            task.assigned_to = new_engineer
            task.save()

            # ✅ استخدام الدالة المساعدة الآمنة
            task_name = _task_display_name(task)

            Notification.objects.create(
                user=new_engineer,
                sender=request.user,
                notification_type="REPLACEMENT_APPROVED",
                title="Replacement Approved",
                message=f"You have been assigned to task {task_name}"
            )

            AuditLog.objects.create(
                project=task.project,
                task=task,
                user=request.user,
                action_type=AuditLog.ActionType.REASSIGNMENT_APPROVED,
                details=f"Replacement approved by manager: {old_engineer.username if old_engineer else 'None'} -> {new_engineer.username}"
            )

        return Response(
            ReplacementRequestSerializer(replacement).data,
            status=status.HTTP_200_OK
        )


class ReplacementRequestEngineerRespondAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        replacement = get_object_or_404(ReplacementRequest, pk=pk)

        if request.user != replacement.suggested_engineer:
            return Response(
                {"detail": "Only the suggested engineer can respond."},
                status=status.HTTP_403_FORBIDDEN
            )

        if replacement.status != ReplacementRequest.Status.PENDING:
            return Response(
                {"detail": "This request has already been responded to."},
                status=status.HTTP_400_BAD_REQUEST
            )

        response = request.data.get('response')
        if response not in ['APPROVE', 'DECLINE']:
            return Response(
                {"detail": "Response must be APPROVE or DECLINE."},
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = request.data.get('reason', '')
        task = replacement.task
        
        # ✅ استخدام الدالة المساعدة الآمنة
        task_name = _task_display_name(task)

        replacement.engineer_response = response
        replacement.engineer_response_reason = reason
        replacement.engineer_responded_at = timezone.now()
        replacement.responded_by = request.user
        replacement.responded_at = timezone.now()

        if response == 'DECLINE':
            replacement.status = ReplacementRequest.Status.REJECTED
            replacement.save()
            # ✅ إرجاع المهمة للمهندس الأصلي كما كانت
            _return_task_to_requester(replacement)
            Notification.objects.create(
                user=replacement.requested_by,
                sender=request.user,
                notification_type="REPLACEMENT_DECLINED",
                title="Replacement Request Declined",
                message=f"Your replacement request for task {task_name} was declined. Reason: {reason}"
            )

        else:
            replacement.status = ReplacementRequest.Status.APPROVED
            replacement.save()
            
            # ✅ إضافة هذا السطر لتعريف المهندس القديم قبل تغيير المسند إليه
            old_engineer = task.assigned_to 
            new_engineer = replacement.suggested_engineer
            
            # ✅ التسليم مع الحفاظ على نسبة التقدم (يكمّل من نفس النسبة)
            _execute_task_handover(task, new_engineer, request.user,
                                   f"Engineer-approved replacement: {replacement.reason}")
            Notification.objects.create(
                user=replacement.requested_by,
                sender=request.user,
                notification_type="REPLACEMENT_ACCEPTED",
                title="Replacement Request Accepted",
                message=f"Your replacement request for task {task_name} was accepted. Task reassigned to {new_engineer.get_full_name()}."
            )

            AuditLog.objects.create(
                project=task.project,
                task=task,
                user=request.user,
                action_type=AuditLog.ActionType.REASSIGNMENT_APPROVED,
                details=f"Replacement approved by engineer: {old_engineer.username if old_engineer else 'None'} -> {new_engineer.username}"
            )

        return Response(ReplacementRequestSerializer(replacement).data)
class DisciplineItemListAPIView(generics.ListAPIView):
    queryset = DisciplineItem.objects.filter(is_active=True)
    serializer_class = DisciplineItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['stage', 'department']

class DisciplineTrackingListAPIView(generics.ListAPIView):
    serializer_class = DisciplineTrackingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        return DisciplineTracking.objects.filter(project_id=project_id).select_related('discipline_item', 'assigned_to')
class DisciplineTrackingUpdateAPIView(generics.UpdateAPIView):
    queryset = DisciplineTracking.objects.all()
    serializer_class = DisciplineTrackingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.status in ['COMPLETED', 'APPROVED'] and not instance.end_date:
            instance.end_date = timezone.now().date()
            instance.save()
        
        project = instance.project
        stage = instance.discipline_item.stage
        
        total = DisciplineTracking.objects.filter(project=project, discipline_item__stage=stage).count()
        completed = DisciplineTracking.objects.filter(
            project=project, 
            discipline_item__stage=stage,
            status__in=['COMPLETED', 'APPROVED']
        ).count()
        
        if total > 0 and total == completed:
            managers = User.objects.filter(role__in=['DESIGN_MGR', 'GM', 'AGM'])
            for manager in managers:
                Notification.objects.create(
                    user=manager,
                    sender=self.request.user,
                    notification_type="STAGE_COMPLETED",
                    title=f"{stage} Completed",
                    message=f"All {stage} disciplines for project {project.project_no} are completed."
                )
        
        AuditLog.objects.create(
            project=project,
            user=self.request.user,
            action_type=AuditLog.ActionType.DISCIPLINE_STATUS_CHANGED,
            details=f"Discipline {instance.discipline_item.name} status changed to {instance.status}"
        )
        
        project.evaluate_and_advance_lifecycle(actor=self.request.user)

class TaskDisciplineLinkAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        tracking_id = request.data.get('discipline_tracking_id')
        if tracking_id:
            tracking = get_object_or_404(DisciplineTracking, pk=tracking_id)
            task.discipline_tracking = tracking
            task.save()
            if task.status in [Task.Status.COMPLETED, Task.Status.APPROVED]:
                tracking.status = DisciplineTracking.Status.COMPLETED
                tracking.end_date = timezone.now().date()
                tracking.save()
            elif task.status == Task.Status.ON_GOING:
                tracking.status = DisciplineTracking.Status.IN_PROGRESS
                tracking.start_date = timezone.now().date()
                tracking.save()
        task.project.evaluate_and_advance_lifecycle(actor=request.user)

        return Response(TaskSerializer(task).data)# 9. Supervision Views

class SupervisionTeamAPIView(generics.ListAPIView):
    serializer_class = SupervisionTeamAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        return SupervisionTeamAssignment.objects.filter(project_id=project_id)


class AssignEngineerAPIView(generics.CreateAPIView):
    serializer_class = SupervisionTeamAssignmentSerializer
    permission_classes = [CanManageSupervisionTeam]

    def perform_create(self, serializer):
        project = get_object_or_404(
            Project,
            pk=self.kwargs["project_id"]
        )

        with transaction.atomic():
            assignment = serializer.save(project=project)

            AuditLog.objects.create(
                project=project,
                user=self.request.user,
                action_type=AuditLog.ActionType.TASK_ASSIGNED,
                details=f"Assigned {assignment.engineer.get_full_name()} to Supervision Team"
            )

            Notification.objects.create(
                user=assignment.engineer,
                sender=self.request.user,
                notification_type="SUPERVISION_ASSIGNMENT",
                title="New Supervision Assignment",
                message=f"Assigned to project {project.project_no} as {assignment.role}"
            )
class UpdateEngineerAPIView(generics.UpdateAPIView):
    queryset = SupervisionTeamAssignment.objects.all()
    serializer_class = SupervisionTeamAssignmentSerializer
    permission_classes = [CanManageSupervisionTeam]

    def perform_update(self, serializer):
        with transaction.atomic():
            assignment = serializer.save()
            AuditLog.objects.create(
                project=assignment.project,
                user=self.request.user,
                action_type=AuditLog.ActionType.PROJECT_UPDATED,
                details=f"Updated schedule for {assignment.engineer.get_full_name()}"
            )
            Notification.objects.create(
                user=assignment.engineer,
                sender=self.request.user,
                notification_type="SCHEDULE_UPDATED",
                title="Schedule Updated",
                message=f"Your schedule for project {assignment.project.project_no} has been updated"
            )

class RemoveEngineerAPIView(generics.DestroyAPIView):
    queryset = SupervisionTeamAssignment.objects.all()
    permission_classes = [CanManageSupervisionTeam]

    def perform_destroy(self, instance):
        with transaction.atomic():
            project = instance.project
            engineer = instance.engineer
            AuditLog.objects.create(
                project=project,
                user=self.request.user,
                action_type=AuditLog.ActionType.PROJECT_UPDATED,
                details=f"Removed {engineer.get_full_name()} from Supervision Team"
            )
            Notification.objects.create(
                user=engineer,
                sender=self.request.user,
                notification_type="SUPERVISION_REMOVAL",
                title="Removed from Project",
                message=f"Removed from supervision team of project {project.project_no}"
            )
            instance.delete()

class ReplacementRequestAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        assignment_id = request.data.get('assignment_id')
        suggested_engineer_id = request.data.get('suggested_engineer_id')
        reason = request.data.get('reason')
        assignment = get_object_or_404(SupervisionTeamAssignment, id=assignment_id)
        suggested_engineer = get_object_or_404(User, id=suggested_engineer_id)
        if assignment.engineer != request.user:
            return Response({"detail": "You can only request replacement for your own assignments."}, status=403)
        managers = User.objects.filter(role__in=['SUP_MGR', 'PM'])
        SupervisionReplacementRequest.objects.create(
           assignment=assignment, requested_by=request.user,
           suggested_engineer=suggested_engineer, reason=reason,
        )
        for manager in managers:
            Notification.objects.create(
                user=manager,
                sender=request.user,
                notification_type="REPLACEMENT_REQUEST",
                title=f"Replacement Request: {assignment.project.project_no}",
                message=f"{request.user.get_full_name()} requested replacement by {suggested_engineer.get_full_name()}. Reason: {reason}"
            )
        Notification.objects.create(
            user=suggested_engineer, sender=request.user,
            notification_type='SUPERVISION_REPLACEMENT_REQUEST',
            title='Supervision Replacement Request',
            message=f"{request.user.get_full_name()} requested to be replaced by you on project {assignment.project.project_no}.",
            related_link='/replacement-requests',
        )
        return Response({"detail": "Replacement request sent."}, status=200)

    def patch(self, request, *args, **kwargs):
        if request.user.role not in ['SUP_MGR', 'PM']:
            return Response({"detail": "Only managers can approve."}, status=403)
        assignment_id = request.data.get('assignment_id')
        new_engineer_id = request.data.get('new_engineer_id')
        assignment = get_object_or_404(SupervisionTeamAssignment, id=assignment_id)
        new_engineer = get_object_or_404(User, id=new_engineer_id)
        old_engineer = assignment.engineer
        with transaction.atomic():
            assignment.engineer = new_engineer
            assignment.save()
            AuditLog.objects.create(
                project=assignment.project,
                user=request.user,
                action_type=AuditLog.ActionType.TASK_ASSIGNED,
                details=f"Replacement approved: {old_engineer.get_full_name()} -> {new_engineer.get_full_name()}"
            )
            Notification.objects.create(
                user=old_engineer,
                sender=request.user,
                notification_type="REPLACEMENT_APPROVED",
                title="Replacement Approved",
                message=f"Your replacement request for project {assignment.project.project_no} was approved."
            )
            Notification.objects.create(
                user=new_engineer,
                sender=request.user,
                notification_type="NEW_ASSIGNMENT",
                title="New Assignment",
                message=f"Assigned to project {assignment.project.project_no}, replacing {old_engineer.get_full_name()}"
            )
        return Response({"detail": "Replacement executed."}, status=200)

class ActionRequestAPIView(generics.ListCreateAPIView):
    serializer_class = ActionRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['SUP_MGR', 'PM']:
            return ActionRequest.objects.all()
        return ActionRequest.objects.filter(assigned_to=user) | ActionRequest.objects.filter(created_by=user)

    def perform_create(self, serializer):
        with transaction.atomic():
            action_req = serializer.save(created_by=self.request.user)
            Notification.objects.create(
                user=action_req.assigned_to,
                sender=self.request.user,
                notification_type="NEW_ACTION_REQUEST",
                title="New Action Request",
                message=f"New action request in project {action_req.project.project_no}"
            )

class ActionRequestUpdateAPIView(generics.UpdateAPIView):
    queryset = ActionRequest.objects.all()
    serializer_class = ActionRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_update(self, serializer):
        instance = self.get_object()
        new_status = self.request.data.get('status', instance.status)
        hold_reason = self.request.data.get('hold_reason', instance.hold_reason)
        progress_percentage = self.request.data.get('progress_percentage', instance.progress_percentage)

        if new_status == ActionRequest.Status.ON_HOLD and not hold_reason:
            raise ValidationError({"hold_reason": "Hold reason is required."})
        if new_status == ActionRequest.Status.ON_GOING and progress_percentage == 0:
            raise ValidationError({"progress_percentage": "Progress required for On Going."})

        with transaction.atomic():
            updated_req = serializer.save()
            if new_status == ActionRequest.Status.COMPLETED and instance.status != ActionRequest.Status.COMPLETED:
                Notification.objects.create(
                    user=updated_req.created_by,
                    sender=self.request.user,
                    notification_type="ACTION_REQUEST_COMPLETED",
                    title="Action Request Completed",
                    message=f"{self.request.user.get_full_name()} marked action request as Completed."
                )
            if new_status == ActionRequest.Status.ON_HOLD and instance.status != ActionRequest.Status.ON_HOLD:
                Notification.objects.create(
                    user=updated_req.created_by,
                    sender=self.request.user,
                    notification_type="ACTION_REQUEST_ON_HOLD",
                    title="Action Request On Hold",
                    message=f"{self.request.user.get_full_name()} put action request ON HOLD. Reason: {updated_req.hold_reason}"
                )


def update_overdue_supervision_invoices(project_id=None):
    today = timezone.now().date()

    q = SupervisionInvoice.objects.filter(
        status__in=[
            SupervisionInvoice.Status.ISSUED,
            SupervisionInvoice.Status.PARTIALLY_PAID,
        ],
        due_date__lt=today,
    )

    if project_id:
        q = q.filter(project_id=project_id)

    q.update(status=SupervisionInvoice.Status.OVERDUE)
class InvoiceListAPIView(generics.ListAPIView):
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'status', 'milestone_type']
    search_fields = ['title', 'project__name', 'project__project_no']
    ordering_fields = ['due_date', 'created_at']

    def get_queryset(self):
        update_overdue_supervision_invoices()
        return Invoice.objects.all().order_by('-created_at')

class InvoiceCreateAPIView(generics.CreateAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]

    def perform_create(self, serializer):
        invoice = serializer.save()
        AuditLog.objects.create(
            project=invoice.project,
            user=self.request.user,
            action_type=AuditLog.ActionType.INVOICE_ADDED,
            details=f"Invoice '{invoice.title}' created: {invoice.total_amount}"
        )

class InvoiceDetailAPIView(generics.RetrieveAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]

class InvoiceUpdateAPIView(generics.UpdateAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]

    def perform_update(self, serializer):
        old_status = self.get_object().status
        invoice = serializer.save()
        if old_status != invoice.status:
            AuditLog.objects.create(
                project=invoice.project,
                user=self.request.user,
                action_type=AuditLog.ActionType.INVOICE_STATUS_CHANGED,
                details=f"Invoice '{invoice.title}' status: {old_status} -> {invoice.status}"
            )

class InvoiceDeleteAPIView(generics.DestroyAPIView):
    queryset = Invoice.objects.all()
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]

class InvoicePaymentAPIView(generics.CreateAPIView):
    queryset = InvoicePayment.objects.all()
    serializer_class = InvoicePaymentSerializer
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]

    @transaction.atomic
    def perform_create(self, serializer):
        payment = serializer.save(recorded_by=self.request.user)
        invoice = payment.invoice
        
        if payment.amount_paid <= 0:
            payment.delete() 
            raise ValidationError("Payment amount must be greater than zero.")

        total_paid = InvoicePayment.objects.filter(
            invoice=invoice
        ).aggregate(total=Sum('amount_paid'))['total'] or 0

        if total_paid > invoice.total_amount:
            payment.delete()  
            raise ValidationError(
                f"Total payments ({total_paid}) exceed invoice amount ({invoice.total_amount})."
            )

        old_status = invoice.status
        
        if total_paid >= invoice.total_amount:
            invoice.status = Invoice.Status.PAID
        elif total_paid > 0:
            today = timezone.now().date()
            if invoice.due_date and invoice.due_date < today:
                invoice.status = Invoice.Status.OVERDUE
            else:
                invoice.status = Invoice.Status.PARTIALLY_PAID

        if invoice.status != old_status:
            invoice.save()

        AuditLog.objects.create(
            project=invoice.project,
            user=self.request.user,
            action_type=AuditLog.ActionType.INVOICE_STATUS_CHANGED,
            details=(
                f"Payment {payment.amount_paid} recorded for '{invoice.title}'. "
                f"Status: {old_status} → {invoice.status}. "
                f"Total paid: {total_paid}/{invoice.total_amount}"
            )
        )

        # ✅ Actual Start = تاريخ أول دفعة يدخلها المحاسب (أي نوع فاتورة)
        invoice.project.sync_start_date_with_first_payment(actor=self.request.user)
class InvoiceStatisticsAPIView(views.APIView):
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]

    def get(self, request, project_id):
        update_overdue_supervision_invoices(project_id)
        valid_invoices = Invoice.objects.filter(project_id=project_id).exclude(
            status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED]
        )
        total_invoiced = valid_invoices.aggregate(total=Sum('total_amount'))['total'] or 0
        total_collected = InvoicePayment.objects.filter(invoice__in=valid_invoices).aggregate(total=Sum('amount_paid'))['total'] or 0
        total_outstanding = total_invoiced - total_collected

        return Response({
            "project_id": project_id,
            "financial_summary": {
                "total_invoiced": total_invoiced,
                "collected": total_collected,
                "outstanding": total_outstanding,
            },
            "invoices_breakdown": {
                "total_valid_count": valid_invoices.count(),
                "paid_count": valid_invoices.filter(status=Invoice.Status.PAID).count(),
                "partial_count": valid_invoices.filter(status=Invoice.Status.PARTIALLY_PAID).count(),
                "overdue_count": valid_invoices.filter(status=Invoice.Status.OVERDUE).count(),
            }
        }, status=status.HTTP_200_OK)


class FinancialDashboardAPIView(views.APIView):
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]

    def get(self, request):
        user = request.user

        update_overdue_supervision_invoices()

        valid_invoices = Invoice.objects.exclude(
            status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED]
        )

        total_invoiced = (
            valid_invoices.aggregate(total=Sum('total_amount'))['total'] or 0
        )

        total_collected = (
            InvoicePayment.objects.aggregate(total=Sum('amount_paid'))['total'] or 0
        )

        total_outstanding = total_invoiced - total_collected

        overdue_invoices = valid_invoices.filter(
            status=Invoice.Status.OVERDUE
        ).order_by('due_date')

        pending_my_tasks = Task.objects.filter(
            assigned_to=user
        ).exclude(
            status__in=['COMPLETED', 'APPROVED']
        ).count()

        return Response(
            {
                'company_totals': {
                    'total_contract_values_invoiced': total_invoiced,
                    'total_collected': total_collected,
                    'total_outstanding': total_outstanding,
                },
                'alerts': {
                    'total_overdue_invoices': overdue_invoices.count(),
                    'overdue_amount_estimation': (
                        overdue_invoices.aggregate(total=Sum('total_amount'))['total']
                        or 0
                    ),
                },
                'my_tasks': {
                    'pending_count': pending_my_tasks,
                },
                'recent_payments': InvoicePaymentSerializer(
                    InvoicePayment.objects.all().order_by('-payment_date')[:5],
                    many=True,
                ).data,
            },
            status=status.HTTP_200_OK,
        )

class SupervisionInvoiceListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = SupervisionInvoiceSerializer
    permission_classes = [IsAuthenticated, CanAccessSupervisionFinance]

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')

        update_overdue_supervision_invoices(project_id)

        return SupervisionInvoice.objects.filter(
            project_id=project_id
        ).order_by('-created_at')

    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(Project, id=project_id)

        invoice = serializer.save(project=project)

        AuditLog.objects.create(
            project=project,
            user=self.request.user,
            action_type=AuditLog.ActionType.INVOICE_ADDED,
            details=f"Supervision Invoice '{invoice.month_name}' created"
        )
class SupervisionInvoiceUpdateAPIView(generics.UpdateAPIView):
    queryset = SupervisionInvoice.objects.all()
    serializer_class = SupervisionInvoiceSerializer
    permission_classes = [IsAuthenticated, CanAccessSupervisionFinance]

class SupervisionInvoiceDeleteAPIView(generics.DestroyAPIView):
    queryset = SupervisionInvoice.objects.all()
    permission_classes = [IsAuthenticated, CanAccessSupervisionFinance]

class SupervisionInvoiceStatisticsAPIView(views.APIView):
    permission_classes = [IsAuthenticated, CanAccessSupervisionFinance]

    def get(self, request, project_id):
        invoices = SupervisionInvoice.objects.filter(project_id=project_id).exclude(status='CANCELLED')
        total = invoices.aggregate(total=Sum('amount'))['total'] or 0
        collected = invoices.aggregate(total=Sum('amount_paid'))['total'] or 0
        outstanding = total - collected
        
        return Response({
            "project_id": project_id,
            "total_collected_supervision": collected,
            "total_outstanding_supervision": outstanding,
            "total_supervision_invoices": invoices.count(),
            "paid_count": invoices.filter(status='PAID').count(),
            "overdue_count": invoices.filter(status='OVERDUE').count(),
        })


class ChatPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50

class ChatRoomAPIView(generics.RetrieveAPIView):          
    serializer_class = ChatRoomSerializer
    permission_classes = [IsAuthenticated]
    def get_object(self):
        project = get_object_or_404(Project, id=self.kwargs.get('project_id'))
        room, _ = ChatRoom.objects.get_or_create(
            room_type='PROJECT', project=project,
            defaults={'name': f"Project · {project.name}"}
        )
        return room
    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}


class ChatConversationsAPIView(generics.ListAPIView):      
    serializer_class = ChatRoomSerializer
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        u = self.request.user
        direct  = ChatRoom.objects.filter(room_type='DIRECT', participants=u)
        q = Q(audience='ALL')
        if _audience_member(u, 'SUPERVISION'): q |= Q(audience='SUPERVISION')
        if _audience_member(u, 'DESIGN'): q |= Q(audience='DESIGN')
        general = ChatRoom.objects.filter(room_type='GENERAL').filter(q)
        if u.role in ['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR', 'PM', 'ACCOUNTANT']:
            proj_ids = Project.objects.filter(is_active=True).values_list('id', flat=True)
        else:
            proj_ids = Project.objects.filter(
                Q(tasks__assigned_to=u) | Q(supervision_team__engineer=u)
            ).values_list('id', flat=True)
        project_rooms = ChatRoom.objects.filter(room_type='PROJECT', project_id__in=proj_ids)
        return (direct | general | project_rooms).distinct().order_by('-updated_at')
    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}


class ChatDirectAPIView(generics.RetrieveAPIView):        
    serializer_class = ChatRoomSerializer
    permission_classes = [IsAuthenticated]
    def get_object(self):
        other_id = self.kwargs.get('user_id')
        if other_id == self.request.user.id:
            raise ValidationError("لا يمكن محادثة نفسك.")
        other = get_object_or_404(User, id=other_id)
        me = self.request.user
        room = (ChatRoom.objects.filter(room_type='DIRECT', participants=me)
                .filter(participants=other).first())
        if not room:
            room = ChatRoom.objects.create(room_type='DIRECT', name='DM')
            room.participants.set([me, other])
        return room
    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}


class ChatGeneralAPIView(generics.RetrieveAPIView):        
    serializer_class = ChatRoomSerializer
    permission_classes = [IsAuthenticated]
    def get_object(self):
        # ✅ غرفة الإعلانات العامة فقط (ALL) — مش أي جروب GENERAL تاني
        room, _ = ChatRoom.objects.get_or_create(
            room_type='GENERAL', audience='ALL',
            defaults={'name': 'General Broadcast'}
        )
        return room
class ChatMessagesAPIView(generics.ListAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ChatPagination
    def get_queryset(self):
        room = get_object_or_404(ChatRoom, id=self.kwargs.get('room_id'))
        if room.room_type == 'GENERAL' and not _audience_member(self.request.user, room.audience):
            raise PermissionDenied('Not a member of this group.')
               
        return ChatMessage.objects.filter(room_id=self.kwargs.get('room_id')) \
            .select_related('sender').prefetch_related('mentions', 'read_by') \
            .order_by('-created_at')

    def list(self, request, *args, **kwargs):
        room = get_object_or_404(ChatRoom, id=self.kwargs.get('room_id'))

        # ✅ فتح المحادثة = قراءتها: تسجيل القراءة على السيرفر
        #    حتى لا يعود رقم غير المقروء للظهور بعد التبديل بين الجروبات
        unread_ids = list(
            room.messages.exclude(sender=request.user)
                         .exclude(read_by=request.user)
                         .values_list('id', flat=True)
        )
        if unread_ids:
            Through = ChatMessage.read_by.through
            Through.objects.bulk_create([
                Through(chatmessage_id=i, user_id=request.user.id)
                for i in unread_ids
            ])

        return super().list(request, *args, **kwargs)
    
class SendMessageAPIView(generics.CreateAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def perform_create(self, serializer):
        room = get_object_or_404(ChatRoom, id=self.kwargs.get('room_id'))

        # ✅ حماية المجموعات: من يرى الغرفة فقط يرسل فيها
        if room.room_type == 'GENERAL' and not _audience_member(self.request.user, room.audience):
            raise PermissionDenied('Not a member of this group.')

        message = serializer.save(sender=self.request.user, room=room)
        message.read_by.add(self.request.user)
        room.save(update_fields=['updated_at'])
        message.read_by.add(self.request.user)
        room.save(update_fields=['updated_at'])          # لترتيب «آخر رسالة»

        mentions_ids = [int(x) for x in self.request.data.getlist('mentions') if str(x).isdigit()]
        if mentions_ids:
            message.mentions.set(mentions_ids)

        me = self.request.user
        link = f"/chat/?room={room.id}"
        notif_type, targets = None, []

        if room.room_type == 'GENERAL':                  # بث → نبّه الكل
            notif_type = 'CHAT_BROADCAST'
            targets = list(User.objects.filter(is_active=True).exclude(id=me.id))
        elif room.room_type == 'DIRECT':                 # DM → نبّه الطرف الآخر
            notif_type = 'CHAT_DIRECT'
            targets = list(room.participants.exclude(id=me.id))
        else:                                            # مشروع → نبّه الـ mentions فقط
            notif_type = 'CHAT_MENTION'
            targets = list(User.objects.filter(id__in=mentions_ids).exclude(id=me.id))

        if notif_type and targets:
            Notification.objects.bulk_create([
                Notification(
                    user=t, sender=me, notification_type=notif_type,
                    title=f"رسالة جديدة · {room.name or (room.project.name if room.project else 'محادثة')}",
                    message=f"{me.get_full_name()}: {(message.message or '')[:80]}",
                    related_link=link,
                ) for t in targets
            ])

class NotificationListAPIView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination

    def get_queryset(self):
        queryset = Notification.objects.filter(user=self.request.user).select_related('sender').order_by('-created_at')
        is_read_param = self.request.query_params.get('is_read', None)
        if is_read_param is not None:
            is_read = is_read_param.lower() == 'true'
            queryset = queryset.filter(is_read=is_read)
        return queryset

class MarkNotificationReadAPIView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        if pk:
            notification = get_object_or_404(Notification, id=pk, user=request.user)
            if not notification.is_read:
                notification.is_read = True
                notification.save(update_fields=['is_read'])
            return Response({"message": "Notification marked as read."}, status=status.HTTP_200_OK)
        else:
            unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
            updated_count = unread_notifications.update(is_read=True)
            return Response({"message": f"{updated_count} notifications marked as read."}, status=status.HTTP_200_OK)


class AuditLogAPIView(generics.ListAPIView):
    queryset = AuditLog.objects.select_related('user', 'project').all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, CanViewReports]   # ← انظر الملاحظة ٣
    pagination_class = StandardResultsSetPagination        # ✅ الإصلاح الجوهري (#1)
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'user': ['exact'],
        'action_type': ['exact', 'in'],
        'project': ['exact'],
        'created_at': ['date__range', 'date', 'date__gte', 'date__lte'],
    }
    search_fields = ['details', 'user__username', 'project__name', 'project__project_no']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
class ProjectFilesAPIView(generics.ListAPIView):
    serializer_class = ProjectFileSerializer
    permission_classes = [IsAuthenticated, ProjectDirectoryAccess]

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        return ProjectFile.objects.filter(project_id=project_id).select_related('uploaded_by').order_by('-created_at')

class UploadProjectFileAPIView(generics.CreateAPIView):
    serializer_class = ProjectFileSerializer
    permission_classes = [IsAuthenticated, ProjectDirectoryAccess]
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(Project, id=project_id)
        serializer.save(project=project, uploaded_by=self.request.user)

class ExternalLogsAPIView(generics.ListCreateAPIView): 
    queryset = ExternalLog.objects.select_related('project').all()
    serializer_class = ExternalLogSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageExternalLogs]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['project', 'log_type', 'sub_type']

    def get_queryset(self):
        qs = super().get_queryset()
        
        # ✅ فلترة حسب scope المستخدم (التصميم / الإشراف)
        scope = self.request.query_params.get('scope')
        if scope:
            # ✅ المشاريع التي تنتمي للقسم المحدد + المشاريع المشتركة (BOTH)
            qs = qs.filter(project__scope__in=[scope, 'BOTH'])
        
        return qs
class ProjectNotesAPIView(generics.ListAPIView):
    serializer_class = ProjectNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        return ProjectNote.objects.filter(project_id=project_id).select_related('user').order_by('created_at')

class AddProjectNoteAPIView(generics.CreateAPIView):
    serializer_class = ProjectNoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(Project, id=project_id)
        
        content = self.request.data.get('content', '')
        mentions_ids = self.request.data.get('mentions', [])
        is_all_mentioned = '@all' in content or self.request.data.get('mention_all', False)
        
        note = serializer.save(project=project, user=self.request.user)
        
        if is_all_mentioned:
            all_users = User.objects.exclude(id=self.request.user.id)
            note.mentions.set(all_users)
            
            for u in all_users:
                Notification.objects.create(
                    user=u,
                    sender=self.request.user,
                    notification_type="NOTE_MENTION_ALL",
                    title="New Note - Mentioned All",
                    message=f"{self.request.user.get_full_name()} mentioned all in a note for project {project.project_no}"
                )
        elif mentions_ids:
            note.mentions.set(mentions_ids)
            
            for uid in mentions_ids:
                if uid != self.request.user.id:
                    Notification.objects.create(
                        user_id=uid,
                        sender=self.request.user,
                        notification_type="NOTE_MENTION",
                        title="New Note Mention",
                        message=f"{self.request.user.get_full_name()} mentioned you in a note for project {project.project_no}"
                    )
        
        AuditLog.objects.create(
            project=project,
            user=self.request.user,
            action_type=AuditLog.ActionType.NOTE_ADDED,
            details=f"Note added by {self.request.user.get_full_name()}{' with @all' if is_all_mentioned else ''}"
        )

class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        my_tasks_count = Task.objects.filter(assigned_to=user).count()
        # ✅ الجديد: مهامي المعتمدة
        my_approved_tasks = Task.objects.filter(assigned_to=user, status='APPROVED').count()
        # ✅ Pending = كل مهامي ما عدا المعتمدة
        pending_my_tasks = Task.objects.filter(assigned_to=user).exclude(status='APPROVED').count()
        unread_notifications = Notification.objects.filter(user=user, is_read=False).count()

        # ✅ Active Projects حسب القسم (مصدر حقيقة واحد مع منطق projectScope)
        active_qs = Project.objects.filter(is_active=True)
        if user.role in ['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR']:
            # المدراء الأربعة (ناصر / نسرين / فهمي / زبادي) → كل المشاريع النشطة
            active_projects_count = active_qs.count()
        elif user.department == 'Design' or user.username in DESIGN_TASK_ASSIGNEE_USERNAMES:
            # مهندس/موظف التصميم → مشاريع التصميم + المشتركة
            active_projects_count = active_qs.filter(
                scope__in=[Project.Scope.DESIGN, Project.Scope.BOTH]
            ).count()
        elif (user.department == 'Supervision'
              or user.username in SUPERVISION_ENGINEER_USERNAMES
              or user.role in ['SUP_MGR', 'PM']):
            # مهندس/موظف الإشراف → مشاريع الإشراف + المشتركة
            active_projects_count = active_qs.filter(
                scope__in=[Project.Scope.SUPERVISION, Project.Scope.BOTH]
            ).count()
        else:
            active_projects_count = active_qs.count()

        data = {
            "welcome_message": f"Welcome {user.get_full_name() or user.username}",
            "role": user.get_role_display(),
            "server_time": timezone.now(),
            "metrics": {
                "active_projects": active_projects_count,
                "my_total_tasks": my_tasks_count,
                "my_approved_tasks": my_approved_tasks,
                "my_pending_tasks": pending_my_tasks,
                "unread_notifications": unread_notifications,
            }
        }
        if user.role in ['GM', 'AGM', 'ACCOUNTANT']:
            data["financial_snapshot"] = {
                "total_unpaid_invoices": Invoice.objects.filter(status='OVERDUE').count(),
                "partially_paid_invoices": Invoice.objects.filter(status='PARTIALLY_PAID').count(),
                "total_outstanding": Invoice.objects.exclude(status__in=['DRAFT', 'CANCELLED', 'PAID']).aggregate(
                    total=Sum('total_amount')
                )['total'] or 0
            }
        return Response(data, status=200)

class StatisticsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]

    def get(self, request, *args, **kwargs):
        project_stats = Project.objects.aggregate(
            total_projects=Count('id'),
            active_projects=Count('id', filter=Q(is_active=True)),
            closed_projects=Count('id', filter=Q(is_active=False)),
            high_priority=Count('id', filter=Q(priority='HIGH')),
            medium_priority=Count('id', filter=Q(priority='MEDIUM'))
        )
        
        task_stats = Task.objects.aggregate(
            total_tasks=Count('id'),
            completed_tasks=Count('id', filter=Q(status='COMPLETED')),
            approved_tasks=Count('id', filter=Q(status=Task.Status.APPROVED)),
            in_progress_tasks=Count('id', filter=Q(status='ON_GOING')),
            delayed_tasks=Count('id', filter=Q(is_on_hold=True))
        )
        
        total_tasks = task_stats['total_tasks']
        completion_rate = (task_stats['approved_tasks'] / total_tasks * 100) if total_tasks > 0 else 0

        financial_stats = Invoice.objects.exclude(status__in=['DRAFT', 'CANCELLED']).aggregate(
            total_invoice_amount=Sum('total_amount'),
            total_collected=Sum('payments__amount_paid'),
        )
        
        total_revenue = financial_stats['total_invoice_amount'] or 0
        total_collected = financial_stats['total_collected'] or 0
        total_remaining = total_revenue - total_collected

        return Response({
            "projects_analysis": project_stats,
            "tasks_efficiency": {
                **task_stats,
                "completion_rate_percentage": round(completion_rate, 2)
            },
            "financial_analytics": {
                "total_billed": total_revenue,
                "total_collected": total_collected,
                "total_receivables": total_remaining
            }
        }, status=200)

class GlobalSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        query = request.query_params.get('q', '').strip()
        if not query or len(query) < 2:
            return Response({"error": "Min 2 chars required"}, status=400)

        projects = Project.objects.filter(
            Q(name__icontains=query) | 
            Q(project_no__icontains=query) | 
            Q(scope__icontains=query)
        )[:10]
        
        tasks = Task.objects.filter(
            Q(title__icontains=query) | 
            Q(discipline__name__icontains=query)
        )[:10]
        
        clients = Client.objects.filter(
            Q(name__icontains=query) | 
            Q(phone__icontains=query)
        )[:10]

        return Response({
            "results": {
                "projects": ProjectListSerializer(projects, many=True, context={'request': request}).data,
                "tasks": TaskSerializer(tasks, many=True).data,
                "clients": ClientSerializer(clients, many=True).data,
            },
            "search_metadata": {"query": query, "timestamp": timezone.now()}
        }, status=200)

    




    
class StaffKPIInsightsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, CanAccessStaffKPI]

    def get(self, request):
        role = request.query_params.get('role')
        users = User.objects.filter(role__in=['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN'])
        if role:
            users = users.filter(role=role)
        
        serializer = StaffKPIInsightSerializer(users, many=True)
        
        total_engineers = users.count()
        total_days = sum(u['total_days_worked'] for u in serializer.data)
        
        return Response({
            'summary': {
                'total_engineers': total_engineers,
                'total_days_worked': total_days,
            },
            'engineers': serializer.data
        })


class EngineerKPIDetailAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated, CanAccessStaffKPI]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        serializer = StaffKPIInsightSerializer(user)
        return Response(serializer.data)



class ClientDirectoryAPIView(generics.ListAPIView):

    serializer_class = ClientDirectorySerializer
    permission_classes = [permissions.IsAuthenticated, CanManageClient]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'phone', 'email']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self):
        return Client.objects.prefetch_related('projects').order_by('name')


class ClientDirectoryDetailAPIView(generics.RetrieveAPIView):
    queryset = Client.objects.all()
    serializer_class = ClientDirectorySerializer
    permission_classes = [permissions.IsAuthenticated, CanManageClient]



class TaskSelfAssignAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated, CanSelfAssign]

    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        user = request.user
        
        if task.assigned_to is not None and task.assigned_to != user:
            return Response(
                {"detail": "Task already assigned to another engineer."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        task.assigned_to = user
        if not task.start_date:
            task.start_date = timezone.now().date()
        task.save()
        
        AuditLog.objects.create(
            project=task.project,
            user=user,
            action_type=AuditLog.ActionType.TASK_SELF_ASSIGNED,
            details=f"Task self-assigned by {user.get_full_name()}"
        )
        
        managers = User.objects.filter(role__in=['DESIGN_MGR', 'GM', 'AGM', 'SUP_MGR'])
        for manager in managers:
            Notification.objects.create(
                user=manager,
                sender=user,
                notification_type="TASK_SELF_ASSIGNED",
                title="Task Self-Assigned",
                message=f"{user.get_full_name()} self-assigned task: {task.title or task.discipline.name}"
            )
        
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)


# 6. Supervision Internal Design Review Form View 

class SupervisionInternalDesignReviewAPIView(APIView):
    """
    Form خاص للمهندسين لتحديث Internal Design Review status
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, project_id):
        project = get_object_or_404(Project, pk=project_id)
        reviews = InternalReviewStage.objects.filter(
            project=project
        ).select_related('assigned_to', 'reviewer', 'approved_by')
        
        serializer = SupervisionInternalReviewSerializer(
            reviews, many=True, context={'request': request}
        )
        return Response({
            'project': project.name,
            'project_no': project.project_no,
            'reviews': serializer.data
        })

    def patch(self, request, project_id):
        review_id = request.data.get('review_id')
        new_status = request.data.get('status')
        
        if not review_id or not new_status:
            return Response(
                {"detail": "review_id and status are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        review = get_object_or_404(InternalReviewStage, pk=review_id, project_id=project_id)
        
        is_assigned = review.assigned_to == request.user
        is_manager = request.user.role in ['SUP_MGR', 'PM', 'GM', 'AGM']
        
        if not (is_assigned or is_manager):
            return Response(
                {"detail": "Only assigned engineer or managers can update."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        stage_order = ['CRITERIA', 'CONCEPT', 'SCHEMATIC', 'DETAILED', 'IFC']
        current_idx = stage_order.index(review.stage_name) if review.stage_name in stage_order else -1
        
        if current_idx > 0:
            prev_stage_name = stage_order[current_idx - 1]
            prev_review = InternalReviewStage.objects.filter(
                project=review.project,
                stage_name=prev_stage_name
            ).first()
            if prev_review and prev_review.status != 'APPROVED':
                return Response(
                    {"detail": f"Previous stage '{prev_stage_name}' must be APPROVED first."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        old_status = review.status
        review.status = new_status
        
        if new_status == 'UNDER_REVIEW' and old_status == 'PENDING':
            review.reviewer = request.user
            review.review_date = timezone.now().date()
        elif new_status == 'APPROVED' and old_status == 'UNDER_REVIEW':
            review.approved_by = request.user
            review.approved_at = timezone.now()
            
            # Notification للمدير
            managers = User.objects.filter(role__in=['SUP_MGR', 'PM', 'GM'])
            for manager in managers:
                Notification.objects.create(
                    user=manager,
                    sender=request.user,
                    notification_type="INTERNAL_REVIEW_APPROVED",
                    title="Internal Review Approved",
                    message=f"Stage {review.get_stage_name_display()} approved for project {review.project.project_no}"
                )
        
        review.save()
        
        AuditLog.objects.create(
            project=review.project,
            user=request.user,
            action_type=AuditLog.ActionType.TASK_STATUS_CHANGED,
            details=f"Internal Review {review.stage_name}: {old_status} -> {new_status}"
        )
        
        return Response(
            SupervisionInternalReviewSerializer(review, context={'request': request}).data
        )


class ActivateInternalDesignReviewAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        if request.user.role not in ['SECRETARY', 'GM', 'AGM', 'DESIGN_MGR']:
            return Response({"detail": "Permission denied."}, status=403)
        project.internal_design_review_required = True
        project.save()
        project.activate_internal_design_review()
        reviews = InternalReviewStage.objects.filter(project=project)
        return Response({
            "message": "Internal Design Review activated.",
            "reviews": InternalReviewStageSerializer(reviews, many=True).data
        })


class ContractFileUploadAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, CanUploadContractFile]  # ← غيّرناها
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        file = request.FILES.get('contract_file')
        
        if not file:
            return Response(
                {"detail": "No file provided."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if project.contract_file:
            project.contract_file.delete(save=False)
        
        project.contract_file = file
        project.contract_status = 'SUBMITTED'
        project.save()
        
        project.evaluate_and_advance_lifecycle(actor=request.user)
        
        AuditLog.objects.create(
            project=project,
            user=request.user,
            action_type=AuditLog.ActionType.PROJECT_UPDATED,
            details=f"Contract file uploaded by {request.user.get_full_name()}"
        )
        
        return Response({
            "message": "Contract file uploaded successfully.",
            "contract_file_url": project.contract_file.url if project.contract_file else None
        })
class OfferStatusAPIView(generics.RetrieveUpdateAPIView):

    queryset = Project.objects.all()
    serializer_class = OfferStatusSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageOfferStatus]
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_update(self, serializer):
      old_offer = self.get_object().offer_status
      old_contract = self.get_object().contract_status
      project = serializer.save()

      synced = project.sync_contractual_lifecycle()

      if old_offer != project.offer_status or old_contract != project.contract_status:
         AuditLog.objects.create(
             project=project, user=self.request.user,
             action_type=AuditLog.ActionType.PROJECT_UPDATED,
             details=(f"Offer: {old_offer}->{project.offer_status}, "
                      f"Contract: {old_contract}->{project.contract_status}. "
                      f"Auto-achieved stages: {synced or 'none'}")
         )

class GlobalFilterBarAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return Response({"count": 0, "results": []})

        # ═══════════════════════════════════════════════════════════
        # ✅ 1. الفلترة الأساسية حسب الدور والقسم (مطابقة لـ ProjectListAPIView)
        # ═══════════════════════════════════════════════════════════
        queryset = Project.objects.select_related('client', 'contractor').prefetch_related('lifecycle_stages')

        # 1.1 الإدارة العليا ومديرو التصميم
        if user.role in ['GM', 'AGM', 'DESIGN_MGR']:
            # ✅ يرون مشاريع DESIGN + BOTH
            # + مشاريع SUPERVISION التي تتطلب مراجعة تصميم (لـ Option B في CreateTask)
            queryset = queryset.filter(
                Q(scope__in=['DESIGN', 'BOTH']) |
                Q(scope='SUPERVISION', internal_design_review_required=True)
            )

        # 1.2 مديرو الإشراف
        elif user.role in ['SUP_MGR', 'PM']:
            queryset = queryset.filter(scope__in=['SUPERVISION', 'BOTH'])

        # 1.3 المحاسب → يرى الكل
        elif user.role == 'ACCOUNTANT':
            pass

        # 1.4 السكرتارية حسب القسم
        elif user.role == 'SECRETARY':
            if user.department == 'Design':
                # ✅ سكرتيرة التصميم ترى مشاريع التصميم + مشاريع الإشراف التي تحتاج مراجعة
                queryset = queryset.filter(
                    Q(scope__in=['DESIGN', 'BOTH']) |
                    Q(scope='SUPERVISION', internal_design_review_required=True)
                )
            elif user.department == 'Supervision':
                queryset = queryset.filter(scope__in=['SUPERVISION', 'BOTH'])

        # 1.5 ✅ المهندسون والرسامون حسب القسم
        elif user.role in ['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN', 'SITE_ENGINEER', 'DESIGN_ENGINEER']:
            if user.department == 'Design':
                # ✅ مهندسو التصميم يرون مشاريع التصميم + مشاريع الإشراف التي تحتاج مراجعة
                queryset = queryset.filter(
                    Q(scope__in=['DESIGN', 'BOTH']) |
                    Q(scope='SUPERVISION', internal_design_review_required=True)
                )
            elif user.department == 'Supervision':
                queryset = queryset.filter(scope__in=['SUPERVISION', 'BOTH'])
            else:
                queryset = queryset.none()

        # أي دور آخر → لا يرى شيئاً
        else:
            queryset = queryset.none()

        # ═══════════════════════════════════════════════════════════
        # ✅ 2. الفلاتر الإضافية من query params (الكود الأصلي بالكامل)
        # ═══════════════════════════════════════════════════════════
        scope = request.query_params.get('scope')
        is_active = request.query_params.get('is_active')
        priority = request.query_params.get('priority')
        permit_status = request.query_params.get('permit_status')
        application_type = request.query_params.get('application_type')  # ✅ جديد

        client_id = request.query_params.get('client_id')
        stage = request.query_params.get('stage')
        start_date_from = parse_date(request.query_params.get('start_date_from') or '')
        end_date = parse_date(request.query_params.get('end_date') or '')
        query = request.query_params.get('q', '').strip()
        
        # ✅ فلترة خاصة لـ internal_review (مشاريع الإشراف التي تحتاج مراجعة تصميم)
        internal_review = request.query_params.get('internal_review')
        if internal_review and internal_review.lower() == 'true':
            queryset = queryset.filter(internal_design_review_required=True)

        if scope:
            scopes = [s for s in scope.split(',') if s]
            if scopes:
                queryset = queryset.filter(scope__in=scopes)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        if priority:
            queryset = queryset.filter(priority=priority)
        
        if permit_status:
            queryset = queryset.filter(permit_status=permit_status)
        if application_type:
            queryset = queryset.filter(application_type=application_type)
        
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        
        if start_date_from:
            queryset = queryset.filter(start_date__gte=start_date_from)
        if end_date:
            queryset = queryset.filter(end_date__lte=end_date)
        if stage:
            if stage == ProjectLifecycleStage.StageNames.CLOSED:
                queryset = queryset.filter(
                    Q(is_active=False) |
                    Q(
                        lifecycle_stages__stage_name=stage,
                        lifecycle_stages__status=ProjectLifecycleStage.Status.ACHIEVED,
                    )
                ).distinct()
            else:
                # ✅ المرحلة الحالية = أول مرحلة (بالترتيب) لسه مأخدتش ACHIEVED
                current_stage_sq = ProjectLifecycleStage.objects.filter(
                    project=OuterRef('pk'),
                ).exclude(
                    status=ProjectLifecycleStage.Status.ACHIEVED
                ).order_by('sequence_order').values('stage_name')[:1]

                queryset = queryset.annotate(
                    current_stage=Subquery(
                        current_stage_sq,
                        output_field=CharField()
                    )
                ).filter(current_stage=stage)
        if query and len(query) >= 2:
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(project_no__icontains=query) |
                Q(application_no__icontains=query) |
                Q(pin_no__icontains=query) |
                Q(client__name__icontains=query) |
                Q(location__icontains=query)
            )
        
        ordering = request.query_params.get('ordering', '-start_date')

        if ordering:
            allowed_fields = {
              "start_date",
              "priority",
              "created_at",
              "updated_at",
              "name",
              "project_no",
                         } 
            ordering_fields = []
            for field in ordering.split(","):
                field = field.strip()
                if not field:
                    continue
                clean_field = field.lstrip("-")
                if clean_field in allowed_fields:
                    ordering_fields.append(field)
            if ordering_fields:
                queryset = queryset.order_by(*ordering_fields)
        # Pagination
        paginator = StandardResultsSetPagination()
        paginated = paginator.paginate_queryset(queryset.distinct(), request)
        serializer = ProjectCardSerializer(paginated, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    
class PlannedDatesAutoCalculationAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsDesignManagerOrManagement]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        
        if not project.start_date:
            return Response(
                {"detail": "Project start_date is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        planned_dates = project.calculate_planned_dates()
        project.auto_update_lifecycle_planned_dates()
        
        return Response({
            "message": "Planned dates calculated and updated.",
            "start_date": project.start_date,
            "planned_dates": planned_dates,
            "stages_updated": project.lifecycle_stages.count()
        })

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        planned = project.calculate_planned_dates()
        return Response({
            "start_date": project.start_date,
            "planned_dates": planned
        })
    





class TaskReplacementRequestListAPIView(generics.ListAPIView):
    serializer_class = ReplacementRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'task__project']

    def get_queryset(self):
        user = self.request.user
        qs = ReplacementRequest.objects.select_related(
            'task', 'task__project', 'requested_by', 'suggested_engineer'
        )
        # ✅ مديرو الإشراف (زبادي ومن بحكمه) يرون طلبات الإشراف فقط — طلبات التصميم مخفية عنهم
        if user.role in ['SUP_MGR', 'PM'] or user.username in SUPERVISION_TASK_MANAGER_USERNAMES:
            return qs.filter(task__project__scope__in=['SUPERVISION', 'BOTH']).order_by('-created_at')
        # الإدارة العامة/التصميم ترى كل الطلبات
        if user.role in ['DESIGN_MGR', 'GM', 'AGM']:
            return qs.order_by('-created_at')
        # المهندس يرى: طلباته + الطلبات الموجهة له
        return qs.filter(
            Q(requested_by=user) | Q(suggested_engineer=user)
        ).distinct().order_by('-created_at')
class SupervisionReplacementRequestListAPIView(generics.ListAPIView):
    serializer_class = SupervisionReplacementRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = SupervisionReplacementRequest.objects.select_related(
            'assignment', 'assignment__project', 'requested_by', 'suggested_engineer'
        ).order_by('-created_at')
        if user.role in ['SUP_MGR', 'PM'] or user.username in SUPERVISION_TASK_MANAGER_USERNAMES:
            return qs
        return qs.filter(Q(suggested_engineer=user) | Q(requested_by=user)).distinct()
class ChangePasswordAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']
        
        if not user.check_password(old_password):
            return Response(
                {"detail": "Old password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(new_password)
        user.save()
        
        update_session_auth_hash(request, user)
        
        return Response(
            {"detail": "Password changed successfully."},
            status=status.HTTP_200_OK
        )
class DashboardChartsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        monthly_projects = Project.objects.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(count=Count('id')).order_by('month')
        
        tasks_by_department = Task.objects.values(
            'assigned_to__department'
        ).annotate(count=Count('id'))
        
        monthly_revenue = InvoicePayment.objects.annotate(
            month=TruncMonth('payment_date')
        ).values('month').annotate(total=Sum('amount_paid')).order_by('month')
        
        return Response({
            'monthly_projects': list(monthly_projects),
            'tasks_by_department': list(tasks_by_department),
            'monthly_revenue': list(monthly_revenue),
        })
    

class LatestActivitiesAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # آخر 20 نشاط من AuditLog
        activities = AuditLog.objects.select_related('user', 'project').order_by('-created_at')[:20]
        return Response(AuditLogSerializer(activities, many=True).data)



class InvoiceSearchAPIView(APIView):
    permission_classes = [IsAuthenticated, CanViewFinancialData]
    
    def get(self, request):
        invoices = Invoice.objects.all()
        
        if request.query_params.get('project'):
            invoices = invoices.filter(project_id=request.query_params['project'])
        if request.query_params.get('status'):
            invoices = invoices.filter(status=request.query_params['status'])
        if request.query_params.get('date_from'):
            invoices = invoices.filter(issue_date__gte=request.query_params['date_from'])
        if request.query_params.get('date_to'):
            invoices = invoices.filter(issue_date__lte=request.query_params['date_to'])
        
        return Response(InvoiceSerializer(invoices, many=True).data)



class PaymentScheduleListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = PaymentScheduleSerializer
    permission_classes = [IsAuthenticated, CanCreateInvoice]
    
    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        return PaymentSchedule.objects.filter(project_id=project_id)
    
    def perform_create(self, serializer):
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(Project, id=project_id)
        serializer.save(project=project)

class PaymentScheduleUpdateAPIView(generics.UpdateAPIView):
    serializer_class = PaymentScheduleSerializer
    permission_classes = [IsAuthenticated, CanCreateInvoice]
    queryset = PaymentSchedule.objects.all()



class InvoiceFileUploadAPIView(APIView):
    permission_classes = [IsAuthenticated, CanUploadInvoicePDF]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request, invoice_id):
        invoice = get_object_or_404(Invoice, id=invoice_id)
        file = request.FILES.get('file')
        if not file:
            return Response({"detail": "No file provided."}, status=400)
        
        invoice_file = InvoiceFile.objects.create(
            invoice=invoice,
            file=file,
            uploaded_by=request.user,
            file_type=file.content_type or 'PDF'
        )
        
        AuditLog.objects.create(
            project=invoice.project,
            user=request.user,
            action_type=AuditLog.ActionType.PROJECT_UPDATED,
            details=f"Invoice file uploaded for {invoice.title}"
        )
        
        return Response({"message": "File uploaded successfully."})

class InvoiceFileListAPIView(generics.ListAPIView):
    serializer_class = InvoiceFileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        invoice_id = self.kwargs.get('invoice_id')
        return InvoiceFile.objects.filter(invoice_id=invoice_id)
    


class LifecycleHistoryAPIView(generics.ListAPIView):
    serializer_class = LifecycleHistorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        return LifecycleHistory.objects.filter(project_id=project_id)

    
class ProjectReportAPIView(APIView):
    permission_classes = [IsAuthenticated, CanViewReports]
    
    def get(self, request):
        # فلاتر
        scope = request.query_params.get('scope')
        status = request.query_params.get('status')
        client = request.query_params.get('client')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        projects = Project.objects.all()
        
        if scope:
            projects = projects.filter(scope=scope)
        if status:
            projects = projects.filter(is_active=(status == 'active'))
        if client:
            projects = projects.filter(client_id=client)
        if date_from:
            projects = projects.filter(created_at__gte=date_from)
        if date_to:
            projects = projects.filter(created_at__lte=date_to)
        
        return Response({
            'total': projects.count(),
            'active': projects.filter(is_active=True).count(),
            'closed': projects.filter(is_active=False).count(),
            'projects': ProjectListSerializer(projects, many=True).data
        })

class TaskReportAPIView(APIView):
    permission_classes = [IsAuthenticated, CanViewReports]

    def get(self, request):
        tasks = Task.objects.all()
        return Response({
            'total': tasks.count(),
            'completed': tasks.filter(status='COMPLETED').count(),
            'approved': tasks.filter(status='APPROVED').count(),
            'in_progress': tasks.filter(status='ON_GOING').count(),
            'on_hold': tasks.filter(is_on_hold=True).count(),
            'tasks': TaskSerializer(tasks[:100], many=True).data,
        })

class EmployeeReportAPIView(APIView):
    permission_classes = [IsAuthenticated, CanViewReports]
    
    def get(self, request):
        employees = User.objects.filter(
            role__in=['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN']
        )
        
        report = []
        for emp in employees:
            tasks = Task.objects.filter(assigned_to=emp)
            report.append({
                'user': UserSerializer(emp).data,
                'total_tasks': tasks.count(),
                'completed_tasks': tasks.filter(status='COMPLETED').count(),
                'completion_rate': round(
                    (tasks.filter(status='COMPLETED').count() / tasks.count() * 100)
                    if tasks.count() > 0 else 0, 2
                )
            })
        
        return Response(report)

class FinancialReportAPIView(APIView):
    permission_classes = [IsAuthenticated, CanViewReports]
    
    def get(self, request):
        invoices = Invoice.objects.exclude(status__in=['DRAFT', 'CANCELLED'])
        
        return Response({
            'total_invoiced': invoices.aggregate(total=Sum('total_amount'))['total'] or 0,
            'total_collected': InvoicePayment.objects.aggregate(total=Sum('amount_paid'))['total'] or 0,
            'total_outstanding': 0,  
            'overdue_count': invoices.filter(status='OVERDUE').count(),
            'invoices': InvoiceSerializer(invoices, many=True).data
        })


class DashboardChartsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        monthly_projects = Project.objects.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(count=Count('id')).order_by('month')
        
        tasks_by_department = Task.objects.values(
            'assigned_to__department'
        ).annotate(count=Count('id'))
        
        monthly_revenue = InvoicePayment.objects.annotate(
            month=TruncMonth('payment_date')
        ).values('month').annotate(total=Sum('amount_paid')).order_by('month')
        
        return Response({
            'monthly_projects': list(monthly_projects),
            'tasks_by_department': list(tasks_by_department),
            'monthly_revenue': list(monthly_revenue),
        })

    
class InternalReviewDetailAPIView(generics.RetrieveAPIView):
    serializer_class = InternalReviewStageSerializer 
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        u = request.user
        allowed = (u.role in ['SUP_MGR', 'PM', 'GM', 'AGM', 'DESIGN_MGR']
                   or (u.role == 'SECRETARY' and u.department == 'Supervision')
                   or project.internal_review_assignees.filter(id=u.id).exists())
        if not allowed:
            return Response({'detail': 'Not authorized.'}, status=403)
        stages = InternalReviewStageSerializer(project.internal_reviews.all(), many=True).data
        assignees = InternalReviewAssigneeSerializer(project.internal_review_assignees.all(), many=True).data
        prog = ProjectDetailSerializer().get_internal_review_progress(project)
        return Response({'project_id': project.id, 'stages': stages, 'assignees': assignees, 'progress': prog})


class InternalReviewAssignAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, CanAssignInternalReview]

    def patch(self, request, pk):
        project = get_object_or_404(Project, pk=pk, scope=Project.Scope.SUPERVISION)
        ids = request.data.get('assignees', [])
        valid = User.objects.filter(id__in=ids, role__in=['ENGINEER', 'SENIOR_ENG', 'DESIGN_MGR'])
        project.internal_review_assignees.set(valid)
        if not project.internal_reviews.exists():
            project.activate_internal_design_review(requested_by=request.user)
        else:
            project.internal_review_requested_by = request.user
            project.save(update_fields=['internal_review_requested_by'])
        AuditLog.objects.create(
            project=project, user=request.user,
            action_type=AuditLog.ActionType.PROJECT_UPDATED,
            details=f"Internal review assignees set: {', '.join(v.get_full_name() for v in valid)}"
        )
        return Response({
            'assignees': InternalReviewAssigneeSerializer(valid, many=True).data,
            'stages': InternalReviewStageSerializer(project.internal_reviews.all(), many=True).data,
        })


class InternalReviewStageUpdateAPIView(generics.UpdateAPIView):
    queryset = InternalReviewStage.objects.all()
    serializer_class = InternalReviewStageSerializer
    permission_classes = [permissions.IsAuthenticated, CanUpdateInternalReviewStage]

    def perform_update(self, serializer):
        stage = self.get_object()

        # حارس خادمي: لا اعتماد لمرحلة قبل اعتماد ما قبلها
        if (
            self.request.data.get('status') == InternalReviewStage.Status.APPROVED
            and stage.status != InternalReviewStage.Status.APPROVED
        ):
            if stage.project.internal_reviews.filter(
                sequence_order__lt=stage.sequence_order,
            ).exclude(status=InternalReviewStage.Status.APPROVED).exists():
                raise ValidationError('Previous review stages must be APPROVED first.')

        stage = serializer.save(
            updated_by=self.request.user,
            updated_at=timezone.now(),
        )
        AuditLog.objects.create(
            project=stage.project, user=self.request.user,
            action_type=AuditLog.ActionType.DISCIPLINE_STATUS_CHANGED,
            details=f"Internal review '{stage.get_stage_name_display()}' → {stage.status}"
        )
        proj = stage.project
        if proj.internal_reviews.exclude(status='APPROVED').count() == 0:
            targets = set(User.objects.filter(role__in=['SUP_MGR', 'PM']))
            if proj.internal_review_requested_by:
                targets.add(proj.internal_review_requested_by)
            targets.discard(self.request.user)
            Notification.objects.bulk_create([
                Notification(
                    user=t, sender=self.request.user,
                    notification_type='INTERNAL_REVIEW_COMPLETED',
                    title='التصميم جاهز للموقع',
                    message=f'كل مراحل المراجعة الداخلية للمشروع {proj.project_no} اعتمدت.',
                    related_link=f'/projects/{proj.id}',
                ) for t in targets
            ])

class ActivateInternalReviewAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        # ✅ سكرتيرة الإشراف مخوّلة بالتفعيل مثل مدير الإشراف
        is_supervision_secretary = (
            request.user.role == 'SECRETARY' and request.user.department == 'Supervision'
        )
        if request.user.role not in ['SUP_MGR', 'PM', 'GM', 'AGM'] and not is_supervision_secretary:
            return Response({'detail': 'فقط مدير الإشراف/PM/الإدارة العليا/سكرتيرة الإشراف يفعّلون المراجعة.'},
                            status=status.HTTP_403_FORBIDDEN)
        project.activate_internal_design_review(requested_by=request.user)
        AuditLog.objects.create(
            project=project, user=request.user,
            action_type=AuditLog.ActionType.PROJECT_UPDATED,
            details="Internal Design Review activated (5 stages created)",
        )
        return Response({
            'ok': True,
            'internal_design_review_required': project.internal_design_review_required,
        })


class MyInternalReviewsAPIView(generics.ListAPIView):

    serializer_class = MyInternalReviewProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(
            scope='SUPERVISION',
            internal_design_review_required=True,
            internal_review_assignees=self.request.user,   # ← المعيّن فقط يرى
        ).prefetch_related('internal_reviews').order_by('-updated_at')



class InternalReviewActiveProjectsAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated]   # ✅ الجميع يرى الصفحة

    def get(self, request):
        projects = Project.objects.filter(
            scope=Project.Scope.SUPERVISION,
            internal_design_review_required=True,
        ).prefetch_related('internal_reviews', 'internal_review_assignees') \
         .order_by('-updated_at')

        data = []
        for p in projects:
            stages = []
            for s in p.internal_reviews.all().order_by('sequence_order'):
                total = s.tasks.count()
                done = s.tasks.filter(status__in=['COMPLETED', 'APPROVED']).count()
                stages.append({
                    'id': s.id,
                    'stage_name': s.stage_name,
                    'stage_name_display': s.get_stage_name_display(),
                    'status': s.status,
                    'status_display': s.get_status_display(),
                    'sequence_order': s.sequence_order,
                    'total_tasks': total,
                    'done_tasks': done,
                })
            data.append({
                'id': p.id,
                'project_no': p.project_no,
                'name': p.name,
                'stages': stages,
                'assignees': [
                    {'id': u.id, 'full_name': u.get_full_name(), 'role': u.get_role_display()}
                    for u in p.internal_review_assignees.all()
                ],
            })
        return Response(data)


class InternalReviewDisciplineItemsAPIView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        review_stage = request.query_params.get('review_stage')
        mapped = REVIEW_STAGE_TO_DISCIPLINE_STAGES.get(review_stage, [])
        qs = DisciplineItem.objects.filter(is_active=True)
        if mapped:
            qs = qs.filter(stage__in=mapped)
        qs = qs.order_by('stage', 'department', 'name')
        return Response(DisciplineItemSerializer(qs, many=True).data)


def build_lifecycle_stages(project):
    if project.scope == project.Scope.SUPERVISION:
        stages = [('OFFER', 1), ('CONTRACT_SUBMITTED', 2), ('CONTRACT_SIGNED', 3),
                  ('COLLECTION', 4), ('CLOSED', 5)]
    else:
        stages = [('OFFER', 1), ('CONTRACT_SUBMITTED', 2), ('CONTRACT_SIGNED', 3),
                  ('CONCEPT', 4), ('DC1', 5), ('DC2', 6), ('TENDER', 7), ('CLOSED', 8)]
    ProjectLifecycleStage.objects.bulk_create([
        ProjectLifecycleStage(
            project=project, stage_name=n, sequence_order=o,
            status=(ProjectLifecycleStage.Status.IN_PROGRESS if o == 1
                    else ProjectLifecycleStage.Status.UPCOMING),
        ) for n, o in stages
    ])


def build_discipline_trackings(project):
    for item in DisciplineItem.objects.filter(is_active=True):
        DisciplineTracking.objects.get_or_create(
            project=project, discipline_item=item, defaults={'status': 'PENDING'},
        )


def _can_create_change_order(user, parent):
    r, d = user.role, user.department
    # مديرو التصميم → مشاريع التصميم فقط
    if r in ['GM', 'AGM', 'DESIGN_MGR']:
        return parent.scope in ['DESIGN', 'BOTH']
    # مديرو الإشراف (زبادي) → مشاريع الإشراف فقط
    if r in ['SUP_MGR', 'PM'] or user.username == 'ahmed.zabady':
        return parent.scope in ['SUPERVISION', 'BOTH']
    if r == 'SECRETARY':
        if d == 'Management':
            return True
        if d == 'Design' and parent.scope in ['DESIGN', 'BOTH']:
            return True
        if d == 'Supervision' and parent.scope in ['SUPERVISION', 'BOTH']:
            return True
    # مهندس / رسام → فقط إذا كانت له مهمة على هذا المشروع (مهامه هو فقط)
    if r in ['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN']:
        return Task.objects.filter(project=parent, assigned_to=user).exists()
    return False


class ChangeOrderListCreateForParentAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return (ChangeOrderCreateSerializer if self.request.method == 'POST'
                else ChangeOrderListSerializer)

    def get_queryset(self):
        parent = get_object_or_404(Project, pk=self.kwargs['parent_pk'])
        return Project.objects.filter(parent_project=parent).order_by('revision_number')

    def create(self, request, *args, **kwargs):
        parent = get_object_or_404(Project, pk=self.kwargs['parent_pk'])
        if not _can_create_change_order(request.user, parent):
            return Response({'detail': 'ليس لديك صلاحية إنشاء Change Order لهذا المشروع.'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sub = create_change_order(parent.id, serializer.validated_data, actor=request.user)
        if not sub.lifecycle_stages.exists():
            build_lifecycle_stages(sub)
        build_discipline_trackings(sub)

        AuditLog.objects.create(
            project=sub, user=request.user,
            action_type=AuditLog.ActionType.REVISION_CREATED,
            details=(f"Change Order '{sub.project_no}' (rev {sub.revision_number}) "
                     f"created under parent {parent.project_no}"),
        )
        return Response(ChangeOrderDetailSerializer(sub).data, status=status.HTTP_201_CREATED)


class ChangeOrderDetailAPIView(generics.RetrieveAPIView):
    queryset = Project.objects.filter(parent_project__isnull=False)
    serializer_class = ChangeOrderDetailSerializer
    permission_classes = [IsAuthenticated, ProjectDirectoryAccess]


class ChangeOrderConfirmAPIView(APIView):
    permission_classes = [IsAuthenticated, IsDesignManagerOrManagement]

    def post(self, request, pk):
        sub = get_object_or_404(Project, pk=pk, parent_project__isnull=False)
        confirm_change_order(sub.id, actor=request.user)
        sub.refresh_from_db()
        return Response(ChangeOrderDetailSerializer(sub).data)


class ChangeOrderRejectAPIView(APIView):
    permission_classes = [IsAuthenticated, IsDesignManagerOrManagement]

    def post(self, request, pk):
        ser = ChangeOrderActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        reason = (ser.validated_data.get('reason') or '').strip()
        if not reason:
            return Response({'detail': 'reason is required for rejection.'},
                            status=status.HTTP_400_BAD_REQUEST)
        sub = get_object_or_404(Project, pk=pk, parent_project__isnull=False)
        reject_change_order(sub.id, actor=request.user, reason=reason)
        sub.refresh_from_db()
        return Response(ChangeOrderDetailSerializer(sub).data)


class ChangeOrderCancelAPIView(APIView):
    permission_classes = [IsAuthenticated, IsDesignManagerOrManagement]

    def post(self, request, pk):
        sub = get_object_or_404(Project, pk=pk, parent_project__isnull=False)
        cancel_change_order(sub.id, actor=request.user)
        sub.refresh_from_db()
        return Response(ChangeOrderDetailSerializer(sub).data)
    

class ChangeOrderActiveAPIView(generics.ListAPIView):

    serializer_class = ChangeOrderOptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Project.objects.filter(
            parent_project__isnull=False,  
            is_active=True,               
        ).select_related('parent_project').order_by('-created_at')

class TaskFormOptionsAPIView(APIView):
    """
    يرجع المشاريع والمهندسين المناسبين لنوع المهمة.
    - يفصل أقسام التصميم عن الإشراف.
    - يقيّد مشاريع الـ PM بمشاريعه فقط.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        task_type = request.query_params.get(
            'task_type',
            Task.TaskType.MAIN_DESIGN
        )
        project_id = request.query_params.get('project_id')
        user = request.user

        if task_type == Task.TaskType.SUPERVISION:
            return self._supervision_options(user, project_id)

        elif task_type == Task.TaskType.INTERNAL_REVIEW:
            return self._internal_review_options(user, project_id)

        else:
            return self._design_options(user, project_id)
    def _supervision_options(self, user, project_id):
        """
        خيارات مشاريع ومهندسي الإشراف:
        1) مدير عام (أحمد زبادي / دور PM) → كل المشاريع.
        2) PM مشروع (is_pm=True) → مشاريعه فقط، ويختار من فريق المشروع الذي هو PM عليه.
        3) مهندس عادي → مشاريعه فقط، ونفسه فقط.
        """
        engineers = User.objects.filter(
            username__in=SUPERVISION_ENGINEER_USERNAMES,
            is_active=True,
        ).order_by('first_name', 'last_name')

        base_projects = Project.objects.filter(
            scope__in=[Project.Scope.SUPERVISION, Project.Scope.BOTH],
            is_active=True,
        )

        # ── 1) مدير عام: كل المشاريع ──
        if is_supervision_task_manager(user):
            projects = base_projects.order_by('-created_at')
            can_assign_others = True
            if project_id:
                team_ids = SupervisionTeamAssignment.objects.filter(
                    project_id=project_id,
                ).values_list('engineer_id', flat=True)
                if team_ids.exists():
                    engineers = engineers.filter(id__in=team_ids)

        # ── 2) مهندس إشراف و/أو PM مشروع ──
        else:
            my_assignments = SupervisionTeamAssignment.objects.filter(engineer=user)
            pm_ids = set(
                my_assignments.filter(is_pm=True)
                .values_list('project_id', flat=True)
            )
            member_ids = set(my_assignments.values_list('project_id', flat=True))

            # مشاريعه فقط (عضو فيها أو PM عليها)
            projects = base_projects.filter(id__in=member_ids).order_by('-created_at')

            try:
                selected_id = int(project_id) if project_id else None
            except (TypeError, ValueError):
                selected_id = None

            if selected_id is not None and selected_id in pm_ids:
                # PM على المشروع المحدد → يختار من فريقه
                team_ids = SupervisionTeamAssignment.objects.filter(
                    project_id=selected_id,
                ).values_list('engineer_id', flat=True)
                engineers = engineers.filter(id__in=team_ids)
                can_assign_others = True
            elif selected_id is None and pm_ids:
                # PM قبل اختيار المشروع → جاهز للتعيين
                team_ids = SupervisionTeamAssignment.objects.filter(
                    project_id__in=pm_ids,
                ).values_list('engineer_id', flat=True)
                engineers = engineers.filter(id__in=team_ids)
                can_assign_others = True
            else:
                # مهندس عادي → نفسه فقط
                engineers = engineers.filter(id=user.id)
                can_assign_others = False

        return Response({
            'projects': ProjectListSerializer(
                projects, many=True, context={'request': self.request}
            ).data,
            'engineers': UserSerializer(engineers, many=True).data,
            'can_assign_others': can_assign_others,
            'allowed_task_types': self._get_allowed_types(user),
        })

    def _internal_review_options(self, user, project_id):
        base_projects = Project.objects.filter(
            scope=Project.Scope.SUPERVISION,
            internal_design_review_required=True,
            is_active=True,
        ).order_by('-created_at')

        # أحمد زبادي فقط يرى كل مشاريع Internal Review
        if user.username in SUPERVISION_TASK_MANAGER_USERNAMES:
            projects = base_projects

        # PM يرى فقط المشاريع التي هو PM عليها
        elif user.role == 'PM' or is_project_pm_any(user):
            pm_project_ids = SupervisionTeamAssignment.objects.filter(
                engineer=user,
                is_pm=True,
            ).values_list('project_id', flat=True)

            projects = base_projects.filter(id__in=pm_project_ids)

        # باقي المستخدمين يرون كل مشاريع Internal Review للـ self assign
        else:
            projects = base_projects

        selected_project = None
        if project_id:
            selected_project = Project.objects.filter(pk=project_id).first()

        is_general_manager = user.username in SUPERVISION_TASK_MANAGER_USERNAMES
        is_project_pm_here = bool(
            selected_project and is_project_pm(user, selected_project)
        )

        can_assign_others = is_general_manager or is_project_pm_here

        if can_assign_others:
            engineers = User.objects.filter(
                Q(role__in=['ENGINEER', 'SENIOR_ENG', 'DESIGN_MGR']) | Q(id=user.id),
                is_active=True,
            ).distinct().order_by('first_name', 'last_name')
        else:
            engineers = User.objects.filter(id=user.id)

        return Response({
            'projects': ProjectListSerializer(
                projects,
                many=True,
                context={'request': self.request}
            ).data,
            'engineers': UserSerializer(engineers, many=True).data,
            'can_assign_others': can_assign_others,
            'allowed_task_types': self._get_allowed_types(user),
        })
    def _design_options(self, user, project_id):
        projects = Project.objects.filter(
            scope__in=[Project.Scope.DESIGN, Project.Scope.BOTH],
            is_active=True
        ).order_by('-created_at')

        assignable_usernames = get_assignable_design_users(user)
        engineers = User.objects.filter(
            username__in=assignable_usernames,
            is_active=True
        ).order_by('first_name', 'last_name')

        can_assign_others = (
            len(assignable_usernames) > 1 or
            user.role in DESIGN_FULL_ASSIGN_ROLES
        )

        return Response({
            'projects': ProjectListSerializer(
                projects, many=True, context={'request': request}
            ).data,
            'engineers': UserSerializer(engineers, many=True).data,
            'can_assign_others': can_assign_others,
            'allowed_task_types': self._get_allowed_types(user),
        })

    def _get_allowed_types(self, user):
        """
        يحدد أنواع المهام المسموحة للمستخدم:
        - مهندس إشراف → SUPERVISION + CHANGE_ORDER + INTERNAL_REVIEW
        - مهندس تصميم → MAIN_DESIGN + CHANGE_ORDER + INTERNAL_REVIEW
        - PM / SUP_MGR / GM / AGM / DESIGN_MGR → الكل
        """
        if user.username in SUPERVISION_TASK_MANAGER_USERNAMES:
            return ['SUPERVISION', 'CHANGE_ORDER', 'INTERNAL_REVIEW']
        # ✅ ناصر/نسرين (GM/AGM): بدون قسم الإشراف نهائيًا
        if user.role in ['GM', 'AGM']:
            return ['MAIN_DESIGN', 'CHANGE_ORDER', 'INTERNAL_REVIEW']

        if user.role in ['SUP_MGR', 'PM', 'DESIGN_MGR']:
            return ['MAIN_DESIGN', 'SUPERVISION', 'CHANGE_ORDER', 'INTERNAL_REVIEW']

        if is_supervision_engineer(user):
            return [
                'SUPERVISION',
                'CHANGE_ORDER',
                'INTERNAL_REVIEW'
            ]

        if user.username in DESIGN_TASK_ASSIGNEE_USERNAMES:
            return [
                'MAIN_DESIGN',
                'CHANGE_ORDER',
                'INTERNAL_REVIEW'
            ]

        return [
            'MAIN_DESIGN',
            'SUPERVISION',
            'CHANGE_ORDER',
            'INTERNAL_REVIEW'
        ]  



class LoginTokenView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        res = super().post(request, *args, **kwargs)
        if res.status_code == 200:
            User.objects.filter(username=request.data.get('username')).update(
                last_login=timezone.now()
            )
        return res
    



class MySupervisionProjectsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        assignments = SupervisionTeamAssignment.objects.filter(
            engineer=request.user,
            project__is_active=True,
        ).select_related('project').order_by('project__project_no')

        available = User.objects.filter(
            username__in=SUPERVISION_ENGINEER_USERNAMES,
            is_active=True,
        ).exclude(id=request.user.id).order_by('first_name', 'last_name')

        return Response({
            'assignments': SupervisionTeamAssignmentSerializer(assignments, many=True).data,
            'available_engineers': [
                {'id': u.id, 'name': f"{u.first_name} {u.last_name}".strip()}
                for u in available
            ],
        })

class SupervisionReplacementRespondAPIView(APIView):
    """رد المهندس المقترح أو زبادي على طلب استبدال مشروع إشراف."""
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        replacement = get_object_or_404(SupervisionReplacementRequest, pk=pk)
        user = request.user
        is_manager = (user.role in ['SUP_MGR', 'PM']
                      or user.username in SUPERVISION_TASK_MANAGER_USERNAMES)
        if user != replacement.suggested_engineer and not is_manager:
            return Response({'detail': 'Only the suggested engineer or the supervision manager can respond.'},
                            status=status.HTTP_403_FORBIDDEN)

        decision = request.data.get('status')
        if decision not in ['APPROVED', 'REJECTED']:
            return Response({'detail': 'status must be APPROVED or REJECTED.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if replacement.status != SupervisionReplacementRequest.Status.PENDING:
            # ✅ Idempotency: نفس المستخدم + نفس القرار = نجاح بدون خطأ (دبل كليك)
            if replacement.responded_by_id == user.id and replacement.status == decision:
                return Response(SupervisionReplacementRequestSerializer(replacement).data)
            return Response({'detail': 'This request has already been responded to.'},
                            status=status.HTTP_400_BAD_REQUEST)

        replacement.status = decision
        replacement.responded_by = user
        replacement.responded_at = timezone.now()
        replacement.save()

        assignment = replacement.assignment
        requester = replacement.requested_by
        new_engineer = replacement.suggested_engineer
        project_no = assignment.project.project_no

        if decision == 'APPROVED':
            # ═══ نقل الكارت للمهندس الجديد + سجل تاريخ ═══
            SupervisionAssignmentHistory.objects.create(
                assignment=assignment,
                old_engineer=assignment.engineer,
                new_engineer=new_engineer,
                reason_for_change=f"Replacement approved by {user.get_full_name()}: {replacement.reason}",
            )
            assignment.engineer = new_engineer
            assignment.save(update_fields=['engineer'])
            requester_msg = (f"{user.get_full_name()} ACCEPTED your replacement request — "
                             f"project {project_no} is now assigned to {new_engineer.get_full_name()}.")
        else:
            # ═══ الرفض: الكارت يرجع/يظل مع صاحب الطلب ═══
            requester_msg = (f"{user.get_full_name()} REJECTED your replacement request — "
                             f"project {project_no} remains yours.")

        # ═══ إشعار لصاحب الطلب + زبادي في الحالتين ═══
        Notification.objects.create(
            user=requester, sender=user,
            notification_type='SUPERVISION_REPLACEMENT_RESPONDED',
            title='Replacement Request Responded',
            message=requester_msg,
            related_link='/my-supervision-projects',
        )
        for mgr in User.objects.filter(username__in=SUPERVISION_TASK_MANAGER_USERNAMES):
            if mgr.id != user.id:
                Notification.objects.create(
                    user=mgr, sender=user,
                    notification_type='SUPERVISION_REPLACEMENT_RESPONDED',
                    title='Replacement Request Responded',
                    message=(f"{user.get_full_name()} {decision} the replacement request of "
                             f"{requester.get_full_name()} → {new_engineer.get_full_name()} ({project_no})."),
                    related_link='/replacement-requests',
                )
        return Response(SupervisionReplacementRequestSerializer(replacement).data)

class SupervisionReplacementRequestCreateAPIView(APIView):
    """إنشاء طلب استبدال — الحالة PENDING ولا يُلمس الإسناد إطلاقًا هنا."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        assignment = get_object_or_404(
            SupervisionTeamAssignment, pk=request.data.get('assignment'))
        if assignment.engineer != request.user:
            return Response({'detail': 'You can only request replacement for your own assignment.'},
                            status=status.HTTP_403_FORBIDDEN)

        suggested = get_object_or_404(User, pk=request.data.get('suggested_engineer'))
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response({'detail': 'Reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if suggested.username not in SUPERVISION_ENGINEER_USERNAMES:
            return Response({'detail': 'The suggested engineer is not a supervision engineer.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # ✅ طلب ينتظر الرد فقط — الكارت يبقى مع صاحبه لحد ما يجي APPROVED
        replacement = SupervisionReplacementRequest.objects.create(
            assignment=assignment,
            requested_by=request.user,
            suggested_engineer=suggested,
            reason=reason,
            status='PENDING',
        )

        Notification.objects.create(
            user=suggested, sender=request.user,
            notification_type='SUPERVISION_REPLACEMENT_REQUEST',
            title='Supervision Replacement Request',
            message=f"{request.user.get_full_name()} requested to be replaced by you on project {assignment.project.project_no}.",
            related_link='/replacement-requests',
        )
        for mgr in User.objects.filter(username__in=SUPERVISION_TASK_MANAGER_USERNAMES):
            Notification.objects.create(
                user=mgr, sender=request.user,
                notification_type='SUPERVISION_REPLACEMENT_REQUEST',
                title='Supervision Replacement Request',
                message=f"{request.user.get_full_name()} requested replacement → {suggested.get_full_name()} ({assignment.project.project_no}).",
                related_link='/replacement-requests',
            )
        return Response(SupervisionReplacementRequestSerializer(replacement).data, status=201)
    

ProjectDeleteAPIView