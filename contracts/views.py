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
    TenderingModuleSerializer, InvoicePaymentSerializer
)
from .permissions import (
    CanManageSupervisionTeam, IsManagementOrAccountant, IsSecretary,
    TenderingPermission, ProjectDirectoryAccess, TaskManagementPermission, 
    IsDesignManagerOrManagement, IsManagement, IsAssignedEngineerOrManager,
    CanViewContractFile
)
from .models import (
    ChatMessage, ChatRoom, ExternalLog, Invoice, ActionRequest, 
    InvoicePayment, Notification, ProjectFile, ProjectNote, 
    SupervisionTeamAssignment, Client, TenderingModule, Project, 
    Contractor, PriorityHistory, ProjectLifecycleStage, InternalReviewStage,
    Task, AssignmentHistory, AuditLog, DisciplineItem, DisciplineTracking,
    ReplacementRequest, StaffKPI, SupervisionInvoice
)

User = get_user_model()

# 1. User Views

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

# 2. Client Views (تم إصلاح الـ Serializer)

class ClientListCreateAPIView(generics.ListCreateAPIView):
    queryset = Client.objects.all().order_by('-created_at')
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]

class ClientRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]

class ClientProjectsAPIView(generics.ListAPIView):
    serializer_class = ProjectListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        client_id = self.kwargs.get('pk')
        client = get_object_or_404(Client, pk=client_id)
        return Project.objects.filter(client=client).order_by('-created_at')

# 3. Contractor Views (تم إصلاح الـ Serializer)

class ContractorListCreateAPIView(generics.ListCreateAPIView):
    queryset = Contractor.objects.all().order_by('-created_at')
    serializer_class = ContractorSerializer
    permission_classes = [permissions.IsAuthenticated]

class ContractorRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Contractor.objects.all()
    serializer_class = ContractorSerializer
    permission_classes = [permissions.IsAuthenticated]

class ContractorProjectsAPIView(generics.ListAPIView):
    serializer_class = ProjectListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        contractor_id = self.kwargs.get('pk')
        contractor = get_object_or_404(Contractor, pk=contractor_id)
        return Project.objects.filter(contractor=contractor).order_by('-created_at')

# 4. Project Views

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
    filterset_fields = ['scope', 'is_active', 'priority', 'permit_status', 'client']
    search_fields = ['name', 'project_no', 'application_no', 'pin_no', 'client__name']
    ordering_fields = ['start_date', 'created_at', 'priority']

class ProjectCreateAPIView(generics.CreateAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectListSerializer
    permission_classes = [permissions.IsAuthenticated, IsSecretary | IsDesignManagerOrManagement]

class ProjectDetailAPIView(generics.RetrieveAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectDetailSerializer
    permission_classes = [permissions.IsAuthenticated, ProjectDirectoryAccess]

class ProjectUpdateAPIView(generics.UpdateAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectListSerializer
    permission_classes = [permissions.IsAuthenticated, ProjectDirectoryAccess]

class ProjectDeleteAPIView(generics.DestroyAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectListSerializer
    permission_classes = [permissions.IsAuthenticated, IsDesignManagerOrManagement]

class ActiveProjectsAPIView(ProjectListAPIView):
    queryset = Project.objects.filter(is_active=True).order_by('-created_at')

class ClosedProjectsAPIView(ProjectListAPIView):
    queryset = Project.objects.filter(is_active=False).order_by('-created_at')

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

# NEW: Project Flag & Progress Views

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
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        tracking = project.discipline_trackings.filter(
            discipline_item__stage='DC1',
            discipline_item__department='STRUCT'
        ).first()
        if not tracking:
            return Response({"status": "NOT_FOUND", "message": "No structural tracking found"}, status=404)
        return Response({
            "status": tracking.status,
            "start_date": tracking.start_date,
            "end_date": tracking.end_date,
            "hold_date": tracking.hold_date,
            "hold_reason": tracking.hold_reason,
            "is_on_hold": tracking.status == 'ON_HOLD'
        })

    def patch(self, request, pk):
        if not (request.user.username == 'mohammad.mostafa' or request.user.role in ['GM', 'AGM', 'DESIGN_MGR']):
            return Response({"detail": "Only Mohammad Mostafa or managers can update."}, status=403)
        project = get_object_or_404(Project, pk=pk)
        tracking = project.discipline_trackings.filter(
            discipline_item__stage='DC1',
            discipline_item__department='STRUCT'
        ).first()
        if not tracking:
            return Response({"detail": "Not found"}, status=404)
        
        new_status = request.data.get('status')
        if new_status:
            tracking.status = new_status
            if new_status in ['COMPLETED', 'APPROVED']:
                tracking.end_date = timezone.now().date()
            tracking.save()
            
            if new_status in ['COMPLETED', 'APPROVED']:
                shaaban = User.objects.filter(username='shaaban.karam').first()
                if shaaban:
                    Notification.objects.create(
                        user=shaaban,
                        sender=request.user,
                        notification_type="STRUCTURAL_COMPLETED",
                        title="Structural Completed",
                        message=f"Structural for project {project.project_no} is completed. IFC can start."
                    )
        
        return Response(DisciplineTrackingSerializer(tracking).data)

class IFCStatusAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        tracking = project.discipline_trackings.filter(
            discipline_item__stage='DC2',
            discipline_item__name__icontains='IFC'
        ).first()
        if not tracking:
            tracking = project.discipline_trackings.filter(
                discipline_item__stage='DC2',
                discipline_item__department='ARCH',
                discipline_item__name__icontains='IFC'
            ).first()
        if not tracking:
            return Response({"status": "NOT_FOUND"}, status=404)
        return Response({
            "status": tracking.status,
            "start_date": tracking.start_date,
            "end_date": tracking.end_date
        })

    def patch(self, request, pk):
        if not (request.user.username == 'shaaban.karam' or request.user.role in ['GM', 'AGM', 'DESIGN_MGR']):
            return Response({"detail": "Only Shaaban Karam or managers can update."}, status=403)
        project = get_object_or_404(Project, pk=pk)
        tracking = project.discipline_trackings.filter(
            discipline_item__stage='DC2',
            discipline_item__name__icontains='IFC'
        ).first()
        if not tracking:
            return Response({"detail": "Not found"}, status=404)
        
        new_status = request.data.get('status')
        if new_status:
            tracking.status = new_status
            if new_status in ['COMPLETED', 'APPROVED']:
                tracking.end_date = timezone.now().date()
            tracking.save()
        
        return Response(DisciplineTrackingSerializer(tracking).data)

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
    """
    قائمة بطاقات المشاريع الذكية مع تخطيط مخصص
    """
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

# 5. Lifecycle Views

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
    permission_classes = [permissions.IsAuthenticated, IsDesignManagerOrManagement]

    def _get_stage_sequence(self, stage_name):
        """ترتيب المراحل: كل مرحلة يجب أن تكتمل قبل التي بعدها"""
        sequences = {
            'OFFER': 1,
            'CONTRACT_SUBMITTED': 2,
            'CONTRACT_SIGNED': 3,
            'DESIGN_PHASE': 4,
            'COLLECTION': 5,
            'CLOSED': 6,
        }
        return sequences.get(stage_name, 0)

    def _validate_sequence(self, instance):
        """
        Validation: كل مرحلة تُغلق حتى تُنهى السابقة
        لا يمكن تحديث مرحلة قبل إكمال جميع المراحل السابقة
        """
        current_seq = self._get_stage_sequence(instance.stage_name)
        project = instance.project
        
        # التحقق من جميع المراحل السابقة
        previous_stages = ProjectLifecycleStage.objects.filter(
            project=project,
            sequence_order__lt=instance.sequence_order
        ).exclude(status='ACHIEVED')
        
        if previous_stages.exists():
            unachieved = [s.get_stage_name_display() for s in previous_stages]
            raise ValidationError(
                f"Cannot update this stage. Previous stages must be ACHIEVED first: {', '.join(unachieved)}"
            )

    def _auto_calculate_planned_dates(self, project):
        """
        ملء planned dates تلقائياً بناءً على start_date
        """
        if not project.start_date:
            return
        
        from datetime import timedelta
        
        stage_duration = {
            'OFFER': 0,
            'CONTRACT_SUBMITTED': 7,
            'CONTRACT_SIGNED': 14,
            'DESIGN_PHASE': 30,
            'COLLECTION': 60,
            'CLOSED': 90,
        }
        
        for stage in project.lifecycle_stages.all():
            if stage.planned_date:
                continue
            days = stage_duration.get(stage.stage_name, 0)
            stage.planned_date = project.start_date + timedelta(days=days)
            stage.save(update_fields=['planned_date'])

    def perform_update(self, serializer):
        instance = self.get_object()
        
        # التحقق من التسلسل
        self._validate_sequence(instance)
        
        # تحديث planned dates تلقائياً
        project = instance.project
        self._auto_calculate_planned_dates(project)
        
        instance = serializer.save()
        
        # إذا دُخل تاريخ فعلي، حدث الحالة تلقائياً
        if instance.actual_date and instance.status != 'ACHIEVED':
            instance.status = 'ACHIEVED'
            instance.save()
            
            # حاول إنشاء المرحلة التالية تلقائياً
            next_stage = ProjectLifecycleStage.objects.filter(
                project=project,
                sequence_order=instance.sequence_order + 1
            ).first()
            if next_stage and next_stage.status == 'UPCOMING':
                next_stage.status = 'UPCOMING'
                next_stage.save()
        
        AuditLog.objects.create(
            project=instance.project,
            user=self.request.user,
            action_type=AuditLog.ActionType.STAGE_ACTUAL_DATE_UPDATED,
            details=f"Stage {instance.stage_name} updated"
        )


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

# 6. Internal Review Views

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

# 7. Tendering Views

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

# 8. Task Views

class TaskResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class TaskListAPIView(generics.ListAPIView):
    queryset = Task.objects.select_related('project', 'assigned_to', 'discipline').order_by('-created_at')
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = TaskResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['project', 'assigned_to', 'status', 'priority', 'stage', 'is_on_hold']
    search_fields = ['title', 'project__name', 'project__project_no', 'assigned_to__username', 'discipline__name']
    ordering_fields = ['start_date', 'created_at', 'priority']

class TaskCreateAPIView(generics.CreateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, TaskManagementPermission]

    def perform_create(self, serializer):
        task = serializer.save()
        AuditLog.objects.create(
            project=task.project,
            user=self.request.user,
            action_type=AuditLog.ActionType.TASK_CREATED,
            details=f"Task created: {task.title or task.discipline.name}"
        )

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
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'priority']

    def get_queryset(self):
        return Task.objects.filter(
            assigned_to=self.request.user,
            project__parent_project__isnull=True,
            project__internal_design_review_required=False
        ).order_by('-created_at')

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


class TaskStatusAPIView(generics.UpdateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, TaskManagementPermission]

    def update(self, request, *args, **kwargs):
        task = self.get_object()
        data = request.data
        changes_log = []
        action_type = AuditLog.ActionType.TASK_STATUS_CHANGED

        if 'is_on_hold' in data:
            new_hold_state = data['is_on_hold']
            if new_hold_state and not task.is_on_hold:
                hold_reason = data.get('hold_reason')
                if not hold_reason:
                    return Response({"detail": "Hold reason is required."}, status=status.HTTP_400_BAD_REQUEST)
                task.is_on_hold = True
                task.hold_reason = hold_reason
                task.hold_date = timezone.now().date()
                task.expected_resume_date = data.get('expected_resume_date')
                action_type = AuditLog.ActionType.ON_HOLD_SET
                changes_log.append(f"Hold set: {hold_reason}")
            elif not new_hold_state and task.is_on_hold:
                task.is_on_hold = False
                task.hold_reason = None
                task.hold_date = None
                task.expected_resume_date = None
                action_type = AuditLog.ActionType.ON_HOLD_RESUMED
                changes_log.append("Hold resumed")

        if 'status' in data:
            old_status = task.status
            new_status = data['status']
            if old_status != new_status:
                task.status = new_status
                # ====== status_date auto-calculation ======
                task.status_date = timezone.now().date()
                task.status_changed_at = timezone.now()
                changes_log.append(f"Status: {old_status} -> {new_status}")
                if new_status == Task.Status.COMPLETED:
                    task.end_date = timezone.now().date()
                    task.progress_percentage = 100
                    action_type = AuditLog.ActionType.TASK_COMPLETED
                elif new_status == Task.Status.APPROVED:
                    task.approval_date = timezone.now().date()
                    task.progress_percentage = 100
                    action_type = AuditLog.ActionType.TASK_APPROVED

        if 'progress_percentage' in data:
            task.progress_percentage = data['progress_percentage']

        task.save()

        if changes_log:
            AuditLog.objects.create(
                project=task.project,
                user=request.user,
                action_type=action_type,
                details=" | ".join(changes_log)
            )

        return Response(self.get_serializer(task).data, status=status.HTTP_200_OK)


class TaskAssignAPIView(generics.UpdateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, TaskManagementPermission]

    def update(self, request, *args, **kwargs):
        task = self.get_object()
        assigned_to_id = request.data.get('assigned_to')
        if not assigned_to_id:
            return Response({"detail": "assigned_to required"}, status=status.HTTP_400_BAD_REQUEST)
        new_engineer = get_object_or_404(User, id=assigned_to_id)
        if task.assigned_to == new_engineer:
            return Response({"detail": "Already assigned"}, status=status.HTTP_400_BAD_REQUEST)
        
        is_self_assign = (new_engineer == request.user)
        task.assigned_to = new_engineer
        if not task.start_date:
            task.start_date = timezone.now().date()
        task.save()
        
        AuditLog.objects.create(
            project=task.project,
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

# NEW: Replacement Request Views

class ReplacementRequestCreateAPIView(generics.CreateAPIView):
    queryset = ReplacementRequest.objects.all()
    serializer_class = ReplacementRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        task_id = self.kwargs.get('pk')
        task = get_object_or_404(Task, pk=task_id)
        if task.assigned_to != self.request.user:
            raise ValidationError("You can only request replacement for your own tasks.")
        serializer.save(task=task, requested_by=self.request.user)
        
        managers = User.objects.filter(role__in=['SUP_MGR', 'PM', 'DESIGN_MGR', 'GM', 'AGM'])
        for manager in managers:
            Notification.objects.create(
                user=manager,
                sender=self.request.user,
                notification_type="REPLACEMENT_REQUEST",
                title=f"Replacement Request: {task.project.project_no}",
                message=f"{self.request.user.get_full_name()} requested replacement for task {task.title}"
            )
        
        AuditLog.objects.create(
            project=task.project,
            user=self.request.user,
            action_type=AuditLog.ActionType.REASSIGNMENT_REQUESTED,
            details=f"Replacement requested for task {task.title}"
        )

class ReplacementRequestRespondAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk=None):
        replacement = get_object_or_404(ReplacementRequest, pk=pk)
        if request.user.role not in ['SUP_MGR', 'PM', 'DESIGN_MGR', 'GM', 'AGM']:
            return Response({"detail": "Only managers can respond."}, status=status.HTTP_403_FORBIDDEN)
        
        status_choice = request.data.get('status')
        response_reason = request.data.get('response_reason', '')
        if status_choice not in ['APPROVED', 'REJECTED']:
            return Response({"detail": "Status must be APPROVED or REJECTED"}, status=status.HTTP_400_BAD_REQUEST)
        
        replacement.status = status_choice
        replacement.response_reason = response_reason
        replacement.responded_by = request.user
        replacement.responded_at = timezone.now()
        replacement.save()
        
        if status_choice == 'APPROVED':
            task = replacement.task
            old_engineer = task.assigned_to
            new_engineer = replacement.suggested_engineer
            
            days_worked = 0
            if task.start_date:
                days_worked = (timezone.now().date() - task.start_date).days
                days_worked = max(days_worked, 0)
            
            if old_engineer:
                AssignmentHistory.objects.create(
                    task=task,
                    old_engineer=old_engineer,
                    new_engineer=new_engineer,
                    reason_for_change=f"Approved replacement: {replacement.reason}",
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
            
            Notification.objects.create(
                user=new_engineer,
                sender=request.user,
                notification_type="REPLACEMENT_APPROVED",
                title="Replacement Approved",
                message=f"You have been assigned to task {task.title}"
            )
            
            AuditLog.objects.create(
                project=task.project,
                user=request.user,
                action_type=AuditLog.ActionType.REASSIGNMENT_APPROVED,
                details=f"Replacement approved: {old_engineer.username if old_engineer else 'None'} -> {new_engineer.username}"
            )
        
        return Response(ReplacementRequestSerializer(replacement).data, status=status.HTTP_200_OK)

# NEW: Discipline Tracking Views

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

# 9. Supervision Views

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
        with transaction.atomic():
            assignment = serializer.save()
            project = assignment.project
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
        for manager in managers:
            Notification.objects.create(
                user=manager,
                sender=request.user,
                notification_type="REPLACEMENT_REQUEST",
                title=f"Replacement Request: {assignment.project.project_no}",
                message=f"{request.user.get_full_name()} requested replacement by {suggested_engineer.get_full_name()}. Reason: {reason}"
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

# 10. Invoice Views

def update_overdue_invoices(project=None):
    today = timezone.now().date()
    query = Invoice.objects.filter(
        status__in=[Invoice.Status.ISSUED, Invoice.Status.PARTIALLY_PAID],
        due_date__lt=today
    )
    if project:
        query = query.filter(project=project)
    query.update(status=Invoice.Status.OVERDUE)

class InvoiceListAPIView(generics.ListAPIView):
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['project', 'status', 'milestone_type']
    search_fields = ['title', 'project__name', 'project__project_no']
    ordering_fields = ['due_date', 'created_at']

    def get_queryset(self):
        update_overdue_invoices()
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
        total_paid = InvoicePayment.objects.filter(invoice=invoice).aggregate(total=Sum('amount_paid'))['total'] or 0

        if total_paid >= invoice.total_amount:
            invoice.status = Invoice.Status.PAID
        elif total_paid > 0:
            today = timezone.now().date()
            if invoice.due_date and invoice.due_date < today:
                invoice.status = Invoice.Status.OVERDUE
            else:
                invoice.status = Invoice.Status.PARTIALLY_PAID
        invoice.save()
        
        AuditLog.objects.create(
            project=invoice.project,
            user=self.request.user,
            action_type=AuditLog.ActionType.INVOICE_STATUS_CHANGED,
            details=f"Payment {payment.amount_paid} added to '{invoice.title}'. Status: {invoice.status}"
        )

class InvoiceStatisticsAPIView(views.APIView):
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]

    def get(self, request, project_id):
        update_overdue_invoices(project_id)
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
        update_overdue_invoices()
        valid_invoices = Invoice.objects.exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED])
        total_invoiced = valid_invoices.aggregate(total=Sum('total_amount'))['total'] or 0
        total_collected = InvoicePayment.objects.aggregate(total=Sum('amount_paid'))['total'] or 0
        total_outstanding = total_invoiced - total_collected
        overdue_invoices = valid_invoices.filter(status=Invoice.Status.OVERDUE).order_by('due_date')

        return Response({
            "company_totals": {
                "total_contract_values_invoiced": total_invoiced,
                "total_collected": total_collected,
                "total_outstanding": total_outstanding,
            },
            "alerts": {
                "total_overdue_invoices": overdue_invoices.count(),
                "overdue_amount_estimation": overdue_invoices.aggregate(total=Sum('total_amount'))['total'] or 0,
            },
            "recent_payments": InvoicePaymentSerializer(
                InvoicePayment.objects.all().order_by('-payment_date')[:5], many=True
            ).data
        }, status=status.HTTP_200_OK)

# NEW: Supervision Invoice Views

class SupervisionInvoiceListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = SupervisionInvoiceSerializer
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]

    def get_queryset(self):
        project_id = self.kwargs.get('project_id')
        return SupervisionInvoice.objects.filter(project_id=project_id).order_by('-created_at')

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
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]

class SupervisionInvoiceDeleteAPIView(generics.DestroyAPIView):
    queryset = SupervisionInvoice.objects.all()
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]

class SupervisionInvoiceStatisticsAPIView(views.APIView):
    permission_classes = [IsAuthenticated, IsManagementOrAccountant]

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

# 11. Chat & Notifications

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
        project_id = self.kwargs.get('project_id')
        project = get_object_or_404(Project, id=project_id)
        room, created = ChatRoom.objects.get_or_create(
            project=project,
            defaults={'name': f"Chat Room - {project.name}"}
        )
        return room

class ChatMessagesAPIView(generics.ListAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ChatPagination

    def get_queryset(self):
        room_id = self.kwargs.get('room_id')
        return ChatMessage.objects.filter(room_id=room_id).select_related('sender').prefetch_related('mentions', 'read_by').order_by('-created_at')

class SendMessageAPIView(generics.CreateAPIView):
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @transaction.atomic
    def perform_create(self, serializer):
        room_id = self.kwargs.get('room_id')
        room = get_object_or_404(ChatRoom, id=room_id)
        message = serializer.save(sender=self.request.user, room=room)
        message.read_by.add(self.request.user)
        mentions_data = self.request.data.getlist('mentions')
        if mentions_data:
            message.mentions.set(mentions_data)
            notifications = []
            for user_id in mentions_data:
                if int(user_id) != self.request.user.id:
                    notifications.append(Notification(
                        user_id=user_id,
                        sender=self.request.user,
                        notification_type='CHAT_MENTION',
                        title=f"New Mention in {room.project.name}",
                        message=f"{self.request.user.get_full_name()} mentioned you in chat.",
                        related_link=f"/projects/{room.project.id}/chat/"
                    ))
            if notifications:
                Notification.objects.bulk_create(notifications)

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

# 12. Files, Notes & Logs

class AuditLogAPIView(generics.ListAPIView):
    queryset = AuditLog.objects.select_related('user', 'project').all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsManagement]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        'user': ['exact'],
        'action_type': ['exact', 'in'],
        'project': ['exact'],
        'created_at': ['date__range', 'date', 'date__gte', 'date__lte'],
    }
    search_fields = ['details', 'user__username', 'project__name']
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

class ExternalLogsAPIView(generics.ListAPIView):
    queryset = ExternalLog.objects.select_related('project').all()
    serializer_class = ExternalLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['project', 'log_type']

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
        
        # إذا كان @all، أضف جميع المستخدمين
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
        # إذا كانت mentions محددة
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
# 13. Dashboard & Search

class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        my_tasks_count = Task.objects.filter(assigned_to=user).count()
        pending_my_tasks = Task.objects.filter(assigned_to=user, status='PENDING').count()
        unread_notifications = Notification.objects.filter(user=user, is_read=False).count()
        active_projects_count = Project.objects.filter(is_active=True).count()

        data = {
            "welcome_message": f"مرحباً بك {user.get_full_name() or user.username}",
            "role": user.get_role_display(),
            "server_time": timezone.now(),
            "metrics": {
                "active_projects": active_projects_count,
                "my_total_tasks": my_tasks_count,
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
    permission_classes = [IsAuthenticated, IsManagement]

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
            in_progress_tasks=Count('id', filter=Q(status='ON_GOING')),
            delayed_tasks=Count('id', filter=Q(is_on_hold=True))
        )
        
        total_tasks = task_stats['total_tasks']
        completion_rate = (task_stats['completed_tasks'] / total_tasks * 100) if total_tasks > 0 else 0

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
    """
    إحصائيات شاملة لكل مهندس
    """
    permission_classes = [permissions.IsAuthenticated, IsManagement]

    def get(self, request):
        # فلترة حسب الدور
        role = request.query_params.get('role')
        users = User.objects.filter(role__in=['ENGINEER', 'SENIOR_ENG', 'DRAFTSMAN'])
        if role:
            users = users.filter(role=role)
        
        serializer = StaffKPIInsightSerializer(users, many=True)
        
        # ملخص إجمالي
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
    """
    تفاصيل KPI لمهندس محدد
    """
    permission_classes = [permissions.IsAuthenticated, IsManagement]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        serializer = StaffKPIInsightSerializer(user)
        return Response(serializer.data)


# 4. Client Directory View 

class ClientDirectoryAPIView(generics.ListAPIView):
    """
    دليل العملاء مع الإحصائيات - للمديرين فقط
    """
    serializer_class = ClientDirectorySerializer
    permission_classes = [permissions.IsAuthenticated, IsManagement]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'phone', 'email']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self):
        return Client.objects.prefetch_related('projects').order_by('name')


class ClientDirectoryDetailAPIView(generics.RetrieveAPIView):
    """
    تفاصيل عميل مع إحصائيات كاملة
    """
    queryset = Client.objects.all()
    serializer_class = ClientDirectorySerializer
    permission_classes = [permissions.IsAuthenticated, IsManagement]


# 5. Self-Assign Endpoint 

class TaskSelfAssignAPIView(APIView):
    """
    endpoint منفصل واضح للـ Self-Assign
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        user = request.user
        
        # التحقق من أن المهمة غير معينة لأحد
        if task.assigned_to is not None and task.assigned_to != user:
            return Response(
                {"detail": "Task already assigned to another engineer."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # تسجيل التعيين
        task.assigned_to = user
        if not task.start_date:
            task.start_date = timezone.now().date()
        task.save()
        
        # Audit Log
        AuditLog.objects.create(
            project=task.project,
            user=user,
            action_type=AuditLog.ActionType.TASK_SELF_ASSIGNED,
            details=f"Task self-assigned by {user.get_full_name()}"
        )
        
        # Notification للمديرين
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
        """عرض جميع مراحل الـ Internal Review للمشروع"""
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
        """تحديث status لمرحلة معينة"""
        review_id = request.data.get('review_id')
        new_status = request.data.get('status')
        
        if not review_id or not new_status:
            return Response(
                {"detail": "review_id and status are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        review = get_object_or_404(InternalReviewStage, pk=review_id, project_id=project_id)
        
        # التحقق من الصلاحية
        is_assigned = review.assigned_to == request.user
        is_manager = request.user.role in ['SUP_MGR', 'PM', 'GM', 'AGM']
        
        if not (is_assigned or is_manager):
            return Response(
                {"detail": "Only assigned engineer or managers can update."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # التحقق من التسلسل: لا يمكن تحديث مرحلة قبل إكمال السابقة
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
        
        # تحديث الحالة
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


# 7. Contract File Upload View 

class ContractFileUploadAPIView(APIView):
    """
    رفع ملف العقد - للإدارة والمحاسب فقط
    """
    permission_classes = [permissions.IsAuthenticated, CanViewContractFile]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        file = request.FILES.get('contract_file')
        
        if not file:
            return Response(
                {"detail": "No file provided."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # حذف الملف القديم إن وجد
        if project.contract_file:
            project.contract_file.delete(save=False)
        
        project.contract_file = file
        project.contract_status = 'SUBMITTED'
        project.save()
        
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


# 8. Offer Status View 

class OfferStatusAPIView(generics.RetrieveUpdateAPIView):
    """
    نموذج منفصل واضح لحالة العرض
    """
    queryset = Project.objects.all()
    serializer_class = OfferStatusSerializer
    permission_classes = [permissions.IsAuthenticated, IsDesignManagerOrManagement]
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_update(self, serializer):
        old_status = self.get_object().offer_status
        project = serializer.save()
        
        if old_status != project.offer_status:
            AuditLog.objects.create(
                project=project,
                user=self.request.user,
                action_type=AuditLog.ActionType.PROJECT_UPDATED,
                details=f"Offer status changed: {old_status} -> {project.offer_status}"
            )


# 9. Global Filter Bar View 

class GlobalFilterBarAPIView(APIView):
    """
    فلاتر شاملة للمشاريع (حسب stage, status, type)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # قراءة معاملات الفلتر
        scope = request.query_params.get('scope')
        is_active = request.query_params.get('is_active')
        priority = request.query_params.get('priority')
        permit_status = request.query_params.get('permit_status')
        client_id = request.query_params.get('client_id')
        stage = request.query_params.get('stage')
        start_date_from = request.query_params.get('start_date_from')
        start_date_to = request.query_params.get('start_date_to')
        query = request.query_params.get('q', '').strip()
        
        queryset = Project.objects.select_related('client', 'contractor').prefetch_related('lifecycle_stages')
        
        # فلترة Scope
        if scope:
            queryset = queryset.filter(scope=scope)
        
        # فلترة Active/Closed
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # فلترة Priority
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # فلترة Permit Status
        if permit_status:
            queryset = queryset.filter(permit_status=permit_status)
        
        # فلترة Client
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        
        # فلترة تاريخ البدء
        if start_date_from:
            queryset = queryset.filter(start_date__gte=start_date_from)
        if start_date_to:
            queryset = queryset.filter(start_date__lte=start_date_to)
        
        # فلترة المرحلة (Stage)
        if stage:
            queryset = queryset.filter(lifecycle_stages__stage_name=stage)
        
        # البحث النصي
        if query and len(query) >= 2:
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(project_no__icontains=query) |
                Q(application_no__icontains=query) |
                Q(pin_no__icontains=query) |
                Q(client__name__icontains=query) |
                Q(location__icontains=query)
            )
        
        # الترتيب
        ordering = request.query_params.get('ordering', '-start_date')
        if ordering:
            queryset = queryset.order_by(ordering)
        
        # Pagination
        paginator = StandardResultsSetPagination()
        paginated = paginator.paginate_queryset(queryset.distinct(), request)
        serializer = ProjectCardSerializer(paginated, many=True)
        
        return paginator.get_paginated_response(serializer.data)


class PlannedDatesAutoCalculationAPIView(APIView):
    """
    حساب وملء التواريخ المخططة تلقائياً بناءً على start_date
    """
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
        """معاينة التواريخ المخططة بدون حفظ"""
        project = get_object_or_404(Project, pk=pk)
        planned = project.calculate_planned_dates()
        return Response({
            "start_date": project.start_date,
            "planned_dates": planned
        })