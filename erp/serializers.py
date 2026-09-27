from jsonschema import ValidationError
from rest_framework import serializers
from decimal import Decimal
from .models import (
    InvoiceFile, PaymentSchedule, User, Client, Contractor, MasterDiscipline, DisciplineItem, DisciplineTracking,
    Project, PriorityHistory, ProjectLifecycleStage, InternalReviewStage,
    TenderingModule, Task, AssignmentHistory, ReplacementRequest, StaffKPI,
    SupervisionTeamAssignment, ActionRequest, Invoice, InvoicePayment,
    SupervisionInvoice, AuditLog, ChatRoom, ChatMessage, Notification,
    ProjectNote, ProjectFile, ExternalLog,SupervisionReplacementRequest,
    SupervisionTeamAssignment,LifecycleHistory,
)
from django.db.models import Count, Q, Avg, Sum
from django.utils import timezone
from .permissions import SUPERVISION_FINANCE_VIEW_USERNAMES
# 1. Base Models & Users
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'role', 'role_display', 'department', 'phone_number',            'date_joined',
            'last_login',]

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'

class ContractorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contractor
        fields = '__all__'


# 2. Master Data

class MasterDisciplineSerializer(serializers.ModelSerializer):
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)

    class Meta:
        model = MasterDiscipline
        fields = ['id', 'name', 'stage', 'stage_display']


class DisciplineItemSerializer(serializers.ModelSerializer):
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    department_display = serializers.CharField(source='get_department_display', read_only=True)

    class Meta:
        model = DisciplineItem
        fields = '__all__'


class DisciplineTrackingSerializer(serializers.ModelSerializer):
    discipline_item_name = serializers.CharField(source='discipline_item.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = DisciplineTracking
        fields = '__all__'


# 3. Project Details & Modules

class PriorityHistorySerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)

    class Meta:
        model = PriorityHistory
        fields = '__all__'

class ProjectLifecycleStageSerializer(serializers.ModelSerializer):
    stage_display = serializers.CharField(source='get_stage_name_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    variance_days = serializers.SerializerMethodField()

    class Meta:
        model = ProjectLifecycleStage
        fields = '__all__'

    def get_variance_days(self, obj):
        if obj.status == 'ACHIEVED' and obj.planned_end_date and obj.actual_end_date:
            return (obj.actual_end_date - obj.planned_end_date).days
        return None


class InternalReviewStageSerializer(serializers.ModelSerializer):
    stage_name_display = serializers.CharField(source='get_stage_name_display', read_only=True)
    status_display     = serializers.CharField(source='get_status_display', read_only=True)
    updated_by_name    = serializers.SerializerMethodField()

    class Meta:
        model = InternalReviewStage
        fields = ['id', 'stage_name', 'stage_name_display', 'status', 'status_display',
                  'sequence_order', 'updated_by_name', 'updated_at', 'notes']

    def get_updated_by_name(self, obj):
        return obj.updated_by.get_full_name() if obj.updated_by else None


class InternalReviewAssigneeSerializer(serializers.ModelSerializer):
    """تمثيل مختصر للمهندس المعيّن"""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    class Meta:
        model = User   # استورد User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name', 'role', 'department']
class TenderingModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenderingModule
        fields = '__all__'


# 4. Tasks & Supervision Tracking
class WorkTypeField(serializers.ChoiceField):
    """✅ بيقبل القيم القديمة المخزنة بالليبل ويحوّلها للمفتاح الصحيح قبل التحقق"""
    LEGACY = {
        'Design': 'DESIGN',
        'Design Review': 'DESIGN_REVIEW',
        'drafting': 'DRAFTING',
        'Drafting': 'DRAFTING',
        'calculation': 'CALCULATION',
        'Calculation': 'CALCULATION',
        'Report': 'REPORT',
        '3D rendering': 'RENDERING_3D',
        '3D Rendering': 'RENDERING_3D',
        'presentation': 'PRESENTATION',
        'Presentation': 'PRESENTATION',
        'printing': 'PRINTING',
        'Printing': 'PRINTING',
    }

    def to_internal_value(self, data):
        return super().to_internal_value(self.LEGACY.get(data, data))


class TaskSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    discipline_name = serializers.CharField(source='discipline.name', read_only=True)
    discipline_code = serializers.CharField(source='discipline.department', read_only=True)
    discipline_tracking_status = serializers.CharField(source='discipline_tracking.status', read_only=True)
    internal_review_stage_name = serializers.CharField(source='internal_review_stage.stage_name', read_only=True)
    task_type_display = serializers.CharField(source='get_task_type_display', read_only=True) 
    project_name        = serializers.CharField(source='project.name', read_only=True)
    project_no          = serializers.CharField(source='project.project_no', read_only=True)
    parent_project_name = serializers.SerializerMethodField()
    parent_project_no   = serializers.SerializerMethodField()
    is_change_order     = serializers.SerializerMethodField()
    discipline_department = serializers.CharField(source='discipline.get_department_display', read_only=True)
    work_type_display       = serializers.CharField(source='get_work_type_display', read_only=True)
    scope = serializers.CharField(source='project.scope', read_only=True)
    work_type = WorkTypeField(choices=Task.WorkType.choices, required=False, allow_blank=True, allow_null=True)
    total_duration_days = serializers.ReadOnlyField()
    net_duration_days = serializers.ReadOnlyField()
    total_hold_days = serializers.ReadOnlyField()
    hold_count = serializers.SerializerMethodField()
    hold_periods = serializers.SerializerMethodField()
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, allow_null=True)
    stage = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    supervision_project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.filter(scope='SUPERVISION'),
        required=False, allow_null=True, write_only=True)
    review_stage = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, write_only=True)
    def get_hold_count(self, obj):
        return obj.hold_periods.count()

    def get_hold_periods(self, obj):
        return [{
            'hold_start': p.hold_start,
            'release_at': p.release_at,
            'days': p.duration_days,
        } for p in obj.hold_periods.order_by('hold_start')]
    class Meta:
        model = Task
        fields = '__all__'
    def validate(self, attrs):
        # ✅ نظّف null/فارغ قبل الفحص — الغياب مش قيمة
        if not attrs.get('project'): attrs.pop('project', None)
        if not attrs.get('stage'): attrs.pop('stage', None)
        if not attrs.get('supervision_project'): attrs.pop('supervision_project', None)
        if not attrs.get('review_stage'): attrs.pop('review_stage', None)

        task_type = attrs.get('task_type') or self.context['request'].data.get('task_type')
        if task_type == Task.TaskType.MAIN_DESIGN:
            a_proj = attrs.get('project')
            a_stage = attrs.get('stage')
            b_proj = attrs.get('supervision_project')
            b_stage = attrs.get('review_stage')

            if a_stage and a_stage != 'OTHER' and not attrs.get('discipline'):
               raise ValidationError('Discipline is required when Stage is selected.')
            if a_stage and not a_proj:
                raise ValidationError('Project Number is required when Stage is selected.')
            if b_proj and not b_stage:
                raise ValidationError('Review Stage is required when Supervision Project is selected.')
            if b_stage and not b_proj:
                raise ValidationError('Supervision Project is required when Review Stage is selected.')
            if (a_proj or a_stage) and (b_proj or b_stage):
                raise ValidationError('Please use either Project Number + Stage OR Supervision Project + Review Stage, not both.')
            if not a_proj and not b_proj:
                raise ValidationError('Please provide either Project Number + Stage OR Supervision Project + Review Stage.')

            # ✅ الخيار B: حوّل supervision_project → project للحفظ
            if b_proj:
                if not b_proj.internal_design_review_required:
                    raise ValidationError('Selected Supervision Project has no Internal Design Review.')
                attrs['project'] = b_proj
                attrs.pop('supervision_project', None)
                attrs.pop('review_stage', None)  # هيتعالج في _prepare_main_design_task
        return attrs
    def get_parent_project_name(self, obj):
        p = obj.project.parent_project
        return p.name if p else None

    def get_parent_project_no(self, obj):
        p = obj.project.parent_project
        return p.project_no if p else None

    def get_is_change_order(self, obj):
        return obj.project.parent_project_id is not None

class AssignmentHistorySerializer(serializers.ModelSerializer):
    old_engineer_name = serializers.CharField(source='old_engineer.get_full_name', read_only=True)
    new_engineer_name = serializers.CharField(source='new_engineer.get_full_name', read_only=True)

    class Meta:
        model = AssignmentHistory
        fields = '__all__'


class ReplacementRequestSerializer(serializers.ModelSerializer):
    # يمكنك الإبقاء على هذه الحقول إذا كنت تستخدمها في مكان آخر، أو يمكنك مسحها
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    suggested_engineer_name = serializers.CharField(source='suggested_engineer.get_full_name', read_only=True)
    responded_by_name = serializers.CharField(source='responded_by.get_full_name', read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)

    class Meta:
        model = ReplacementRequest
        fields = '__all__'
        read_only_fields = (
            'task',
            'requested_by',
            'status',
            'responded_by',
            'responded_at',
        )

    def to_representation(self, instance):
        # 1. استدعاء السلوك الافتراضي الذي يجلب الحقول والأرقام
        representation = super().to_representation(instance)
        
        # 2. تحويل بيانات المهندس صاحب الطلب إلى Object يطابق الفرونت إند
        if instance.requested_by:
            representation['requested_by'] = {
                'id': instance.requested_by.id,
                'first_name': instance.requested_by.first_name,
                'last_name': instance.requested_by.last_name,
            }

        # 3. تحويل بيانات المهندس المقترح إلى Object
        if instance.suggested_engineer:
            representation['suggested_engineer'] = {
                'id': instance.suggested_engineer.id,
                'first_name': instance.suggested_engineer.first_name,
                'last_name': instance.suggested_engineer.last_name,
            }

        # 4. تحويل بيانات المهمة والمشروع المرتبط بها إلى Object
        if instance.task:
            project = getattr(instance.task, 'project', None)
            representation['task'] = {
                'id': instance.task.id,
                'title': getattr(instance.task, 'title', ''),
                'discipline_name': getattr(instance.task, 'discipline_name', ''),
                'project': {
                    'id': project.id,
                    'project_no': project.project_no,
                    'name': project.name
                } if project else None
            }
            
        return representation
class StaffKPISerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = StaffKPI
        fields = '__all__'
class SupervisionTeamAssignmentSerializer(serializers.ModelSerializer):
    # ✅ حقول عرض للقراءة فقط (لا تدخل في التحقق عند الإنشاء)
    engineer_name = serializers.CharField(
        source='engineer.get_full_name',
        read_only=True
    )
    engineer_username = serializers.CharField(source='engineer.username', read_only=True)
    engineer_role = serializers.CharField(source='engineer.role', read_only=True)
    engineer_department = serializers.CharField(source='engineer.department', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_no = serializers.CharField(source='project.project_no', read_only=True)
    role_display = serializers.SerializerMethodField()

    class Meta:
        model = SupervisionTeamAssignment
        fields = "__all__"
        # ✅ الإصلاح الجوهري: project للقراءة فقط —
        #    يأتي من الـ URL (project_id) ويحقنه الـ View عبر save(project=project)
        #    لذلك لا يجب أن يكون مطلوباً في جسم الطلب أبداً
        read_only_fields = ("project", "created_at", "updated_at")

    def get_role_display(self, obj):
        # ✅ أسماء العرض لأدوار الإشراف الجديدة + القديمة
        labels = {
            'PM': 'PM',
            'SITE_ENGINEER': 'Site Engineer',
            'COORDINATOR': 'Coordinator',
            'INSPECTOR': 'Inspector',
            'SENIOR_ENGINEER': 'Senior Engineer',
            'ENGINEER': 'Engineer',
            'SUP_MGR': 'Supervision Manager',
        }
        return labels.get(obj.role, obj.role)

    def validate(self, attrs):
        # ✅ أتمتة: إذا كان الدور PM فإن is_pm = True تلقائياً
        role = attrs.get('role', getattr(self.instance, 'role', None))
        if role == 'PM':
            attrs['is_pm'] = True
        return attrs
class ActionRequestSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)

    class Meta:
        model = ActionRequest
        fields = '__all__'


# 5. Finance Module

class InvoicePaymentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)

    class Meta:
        model = InvoicePayment
        fields = '__all__'

class InvoiceSerializer(serializers.ModelSerializer):
    payments = InvoicePaymentSerializer(many=True, read_only=True)
    collected_amount = serializers.SerializerMethodField()
    outstanding_amount = serializers.SerializerMethodField()
    milestone_type_display = serializers.CharField(source='get_milestone_type_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    project_no   = serializers.CharField(source='project.project_no', read_only=True)
    delayed_days = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            'id', 'project', 'project_name', 'project_no',
            'title', 'milestone_type', 'milestone_type_display', 'total_amount',
            'status', 'issue_date', 'due_date', 'created_at', 'payments',
            'collected_amount', 'outstanding_amount', 'delayed_days',
        ]

    def get_delayed_days(self, obj):
        from django.utils import timezone
        if obj.status in ('ISSUED', 'PARTIALLY_PAID', 'OVERDUE') and obj.due_date:
            delta = (timezone.now().date() - obj.due_date).days
            return delta if delta > 0 else 0
        return 0
    def get_collected_amount(self, obj):
        return sum(payment.amount_paid for payment in obj.payments.all())

    def get_outstanding_amount(self, obj):
        return obj.total_amount - self.get_collected_amount(obj)


class SupervisionInvoiceSerializer(serializers.ModelSerializer):
    outstanding_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = SupervisionInvoice
        fields = '__all__'
        read_only_fields = ('project',)  # لضمان عدم طلبه من الـ Frontend

    def get_outstanding_amount(self, obj):
        # تحويل القيم إلى Decimal بشكل آمن لتجنب خطأ الطرح بين الأنواع المختلفة
        amount = Decimal(str(obj.amount or 0))
        amount_paid = Decimal(str(obj.amount_paid or 0))
        return amount - amount_paid
# 6. Audit, Comm & Files
class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)
    action_type_display = serializers.CharField(source='get_action_type_display', read_only=True)

    # ✅ الحقول الناقصة — سبب ظهور N/A
    project_name = serializers.SerializerMethodField()
    project_no = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = '__all__'

    def get_project_name(self, obj):
        return obj.project.name if obj.project else None

    def get_project_no(self, obj):
        return obj.project.project_no if obj.project else None
class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.get_full_name', read_only=True)

    class Meta:
        model = ChatMessage
        fields = '__all__'
        # room/sender يُحقنان من الباك‑إند؛ بدونهما يفشل is_valid عند الإرسال
        read_only_fields = ['sender', 'room', 'read_by']


class ChatRoomSerializer(serializers.ModelSerializer):
    """يُستخدم كـ «محادثة» في القائمة: اسم + أفاتار + آخر رسالة + غير مقروء"""
    messages = ChatMessageSerializer(many=True, read_only=True)
    display_name   = serializers.SerializerMethodField()
    other_user_id  = serializers.SerializerMethodField()
    avatar_tone    = serializers.SerializerMethodField()
    last_message   = serializers.SerializerMethodField()
    unread_count   = serializers.SerializerMethodField()
    participant_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = '__all__'

    def _me(self):
        return self.context.get('request').user

    def _other(self, obj):
        return obj.participants.exclude(id=self._me().id).first()

    def get_display_name(self, obj):
        if obj.room_type == 'DIRECT':
            o = self._other(obj)
            return (o.get_full_name() or o.username) if o else 'محادثة'
        if obj.room_type == 'PROJECT':
            return f"{obj.project.project_no} · {obj.project.name}" if obj.project else 'غرفة مشروع'
        # ✅ GENERAL: اسم الغرفة الفعلي المخزّن في الداتابيز
        return obj.name or 'الإعلانات العامة'
    
    def get_other_user_id(self, obj):
        if obj.room_type != 'DIRECT':
            return None
        o = self._other(obj)
        return o.id if o else None

    _ROLE_TONE = {
        'GM': 'amber', 'AGM': 'amber', 'DESIGN_MGR': 'sky', 'SUP_MGR': 'violet',
        'PM': 'violet', 'SENIOR_ENG': 'emerald', 'ENGINEER': 'sky',
        'DRAFTSMAN': 'emerald', 'ACCOUNTANT': 'rose', 'SECRETARY': 'amber',
    }
    def get_avatar_tone(self, obj):
        if obj.room_type == 'GENERAL':  return 'amber'
        if obj.room_type == 'PROJECT':  return 'sky'
        o = self._other(obj)
        return self._ROLE_TONE.get(o.role, 'slate') if o else 'slate'

    def get_last_message(self, obj):
        m = obj.messages.order_by('-created_at').first()
        if not m:
            return None
        return {
            'id': m.id, 'sender_id': m.sender_id,
            'sender_name': m.sender.get_full_name(),
            'message': (m.message or '')[:90],
            'has_attachment': bool(m.attachment),
            'created_at': m.created_at,
        }

    def get_unread_count(self, obj):
        me = self._me()
        return obj.messages.exclude(sender=me).exclude(read_by=me).count()

    def get_participant_count(self, obj):
        if obj.room_type == 'GENERAL':
            return User.objects.filter(is_active=True).count()
        if obj.room_type == 'DIRECT':
            return 2
        return obj.participants.count()
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
class ProjectNoteSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    mentioned_users = serializers.SerializerMethodField()

    class Meta:
        model = ProjectNote
        fields = ['id', 'project', 'user', 'user_name', 'content', 'mentions', 'mentioned_users', 'is_pinned', 'created_at']
        
        # أضف هذا السطر لتخطي التحقق من هذه الحقول في الـ request.data
        read_only_fields = ['project', 'user']
    def get_mentioned_users(self, obj):
        return [
            {"id": u.id, "username": u.username, "full_name": u.get_full_name()}
            for u in obj.mentions.all()
        ]
class ProjectFileSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)

    class Meta:
        model = ProjectFile
        fields = '__all__'

class ExternalLogSerializer(serializers.ModelSerializer):
    sub_type_display = serializers.CharField(source='get_sub_type_display', read_only=True)
    project_no = serializers.CharField(source='project.project_no', read_only=True)  # ✅ أضف هذا

    class Meta:
        model = ExternalLog
        fields = ['id', 'project','project_no', 'log_type', 'sub_type', 'sub_type_display', 'url', 'description', 'created_at']


# 7. The Core Project Serializers

class ProjectListSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    contractor_name = serializers.CharField(source='contractor.name', read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    application_type_display = serializers.CharField(source='get_application_type_display', read_only=True)

    class Meta:
        model = Project
        fields = [
            'id', 'project_no', 'name', 'client_name', 'contractor_name', 
            'scope', 'is_active', 'priority', 'start_date', 'permit_status',
            'progress_percentage',
                    'design_company', 'commencement_status', 'contractor','location',
            'application_type', 'application_type_display', 'internal_design_review_required'# ✅ الحقول الجديدة

        ]

    def get_progress_percentage(self, obj):
        total = obj.lifecycle_stages.count()
        if total == 0:
            return "0.0%"
        completed = obj.lifecycle_stages.filter(status='ACHIEVED').count()
        return f"{round((completed / total) * 100, 2)}%"


class ProjectDetailSerializer(serializers.ModelSerializer):
    client_details = ClientSerializer(source='client', read_only=True)
    contractor_details = ContractorSerializer(source='contractor', read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)   # ✅ اللي بتقرأه الصفحة
    lifecycle_stages = ProjectLifecycleStageSerializer(many=True, read_only=True)
    internal_reviews = InternalReviewStageSerializer(many=True, read_only=True)
    tendering = TenderingModuleSerializer(read_only=True)
    
    tasks = TaskSerializer(many=True, read_only=True)
    discipline_trackings = DisciplineTrackingSerializer(many=True, read_only=True)
    supervision_team = SupervisionTeamAssignmentSerializer(many=True, read_only=True)
    invoices = InvoiceSerializer(many=True, read_only=True)
    supervision_invoices = SupervisionInvoiceSerializer(many=True, read_only=True)
    
    notes = ProjectNoteSerializer(many=True, read_only=True)
    files = ProjectFileSerializer(many=True, read_only=True)
    external_logs = ExternalLogSerializer(many=True, read_only=True)
    
    sub_projects = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    dc1_status = serializers.SerializerMethodField()
    dc2_status = serializers.SerializerMethodField()
    structural_status = serializers.SerializerMethodField()
    ifc_status = serializers.SerializerMethodField()
    internal_review_assignees = InternalReviewAssigneeSerializer(many=True, read_only=True)
    internal_review_progress  = serializers.SerializerMethodField()
    end_date = serializers.SerializerMethodField()

    def get_end_date(self, obj):
        # ✅ المشاريع القديمة المحفوظة بـ NULL تُحسب لحظيًا للعرض
        return obj.end_date or obj.computed_end_date()
    class Meta:
        model = Project
        fields = '__all__'


    def get_internal_review_progress(self, obj):
        stages = obj.internal_reviews.all()
        total = stages.count()
        approved = stages.filter(status='APPROVED').count()
        return {
            'total': total, 'approved': approved,
            'all_approved': total > 0 and approved == total,
            'percentage': round((approved / total) * 100) if total else 0,
        }
    def get_sub_projects(self, obj):
        subs = obj.sub_projects.all()
        return ProjectListSerializer(subs, many=True).data

    def get_progress_percentage(self, obj):
        total = obj.lifecycle_stages.count()
        if total == 0:
            return "0.0%"
        completed = obj.lifecycle_stages.filter(status='ACHIEVED').count()
        return f"{round((completed / total) * 100, 2)}%"

    def get_dc1_status(self, obj):
        return self._get_stage_flag_status(obj, 'DC1')

    def get_dc2_status(self, obj):
        return self._get_stage_flag_status(obj, 'DC2')

    def _get_stage_flag_status(self, obj, stage):
        # ✅ الرقم الأول = المهام المضافة للمرحلة، والثاني = المعتمد منها
        tasks = obj.tasks.filter(stage=stage)
        total = tasks.count()
        approved = tasks.filter(status='APPROVED').count()
        if total == 0:
            return {"status": "NOT_STARTED", "completed": 0, "total": 0}
        return {
            "status": "COMPLETED" if approved == total else "IN_PROGRESS",
            "completed": approved,
            "total": total,
        }
    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = getattr(request, 'user', None)

        can_see_money = bool(
            user and getattr(user, 'is_authenticated', False)
            and getattr(user, 'role', None) in ['GM', 'AGM', 'ACCOUNTANT']
        )

        if not can_see_money:
            data.pop('contract_file', None)
            data.pop('contract_value', None)
            data['invoices'] = self._sanitize_invoices(data.get('invoices'))
            data['supervision_invoices'] = self._sanitize_invoices(data.get('supervision_invoices'))

        # ══ مالية الإشراف: تظهر فقط للمستخدمين المحددين ══
        can_view_supervision_finance = bool(
            user
            and getattr(user, 'is_authenticated', False)
            and getattr(user, 'username', None) in SUPERVISION_FINANCE_VIEW_USERNAMES
        )

        if not can_view_supervision_finance:
            data.pop('supervision_invoices', None)

        return data


    def _sanitize_invoices(self, invoices_data):
    
        if not invoices_data:
            return []
        out = []
        for inv in invoices_data:
            total = float(inv.get('total_amount') or 0)
            collected = float(inv.get('collected_amount') or 0)
            pct = round((collected / total) * 100) if total > 0 else 0
            out.append({
                'id': inv.get('id'),
                'title': inv.get('title'),
                'milestone_type': inv.get('milestone_type'),
                'milestone_type_display': inv.get('milestone_type_display'),
                'status': inv.get('status'),
                'payment_progress_percentage': pct,   # ← النسبة فقط، بلا أرقام
            })
        return out

    # ────────────────────────────────────────────────────────────
    #  تنقية الفواتير: إسقاط المبالغ مع إبقاء الاسم/الحالة/النسبة
    # ────────────────────────────────────────────────────────────

    def _sanitize_invoices(self, invoices):
        """نسخة واحدة فقط: تُسقط المبالغ وتُبقي الاسم/الحالة/النسبة."""
        return [
            {
                'id': inv.get('id'),
                'title': inv.get('title'),
                'milestone_type': inv.get('milestone_type'),
                'milestone_type_display': inv.get('milestone_type_display'),
                'status': inv.get('status'),
                'collection_percentage': self._collection_percentage(inv),
            }
            for inv in (invoices or [])
        ]

    @staticmethod
    def _collection_percentage(inv):
        """نسبة التحصيل تُحسب من البيانات الكاملة قبل إسقاطها."""
        try:
            total = float(inv.get('total_amount') or 0)
            collected = float(inv.get('collected_amount') or 0)
        except (TypeError, ValueError):
            return 0.0
        if total <= 0:
            return 0.0
        return round(min(collected / total, 1.0) * 100, 1)
    def get_structural_status(self, obj):
        tracking = obj.discipline_trackings.filter(
            discipline_item__stage='DC1', 
            discipline_item__department='STRUCT'
        ).first()
        if tracking:
            return {
                "status": tracking.status,
                "start_date": tracking.start_date,
                "end_date": tracking.end_date,
                "hold_date": tracking.hold_date,
                "hold_reason": tracking.hold_reason
            }
        return {"status": "NOT_STARTED"}

    def get_ifc_status(self, obj):
        tracking = obj.discipline_trackings.filter(
            discipline_item__stage='DC2', 
            discipline_item__name__icontains='IFC'
        ).first()
        if not tracking:
            tracking = obj.discipline_trackings.filter(
                discipline_item__stage='DC2', 
                discipline_item__department='ARCH',
                discipline_item__name__icontains='IFC'
            ).first()
        if tracking:
            return {
                "status": tracking.status,
                "start_date": tracking.start_date,
                "end_date": tracking.end_date
            }
        return {"status": "NOT_STARTED"}
    


class ProjectCardSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    contractor_name = serializers.CharField(source='contractor.name', read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    current_stage = serializers.SerializerMethodField()
    active_tasks_count = serializers.SerializerMethodField()
    latest_note = serializers.SerializerMethodField()
    offer_status_display = serializers.CharField(source='get_offer_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    lifecycle_summary = serializers.SerializerMethodField()
    application_type_display = serializers.CharField(source='get_application_type_display', read_only=True)  # ✅ جديد

    class Meta:
        model = Project
        fields = [
            'id', 'project_no', 'name', 'client_name', 'contractor_name',
            'scope', 'scope_display', 'is_active', 'priority', 'priority_display',
            'start_date', 'permit_status', 'offer_status', 'offer_status_display',
            'progress_percentage', 'current_stage', 'active_tasks_count',
            'latest_note', 'lifecycle_summary', 'created_at',
            'application_type', 'application_type_display',   # ✅ الحقلين
        ]
    def get_progress_percentage(self, obj):
        total = obj.lifecycle_stages.count()
        if total == 0:
            return "0.0%"
        completed = obj.lifecycle_stages.filter(status='ACHIEVED').count()
        return f"{round((completed / total) * 100, 2)}%"

    def get_current_stage(self, obj):
        current = obj.lifecycle_stages.filter(status__in=['UPCOMING', 'OVERDUE']).order_by('sequence_order').first()
        if current:
            return {
                'name': current.get_stage_name_display(),
                'status': current.status,
                'planned_date': current.planned_date,
            }
        achieved = obj.lifecycle_stages.filter(status='ACHIEVED').order_by('-sequence_order').first()
        if achieved:
            return {'name': achieved.get_stage_name_display(), 'status': 'ACHIEVED'}
        return None

    def get_active_tasks_count(self, obj):
        return obj.tasks.exclude(status__in=['COMPLETED', 'APPROVED']).count()

    def get_latest_note(self, obj):
        note = obj.notes.order_by('-created_at').first()
        if note:
            return {
                'content': note.content[:100],
                'user': note.user.get_full_name(),
                'date': note.created_at
            }
        return None

    def get_lifecycle_summary(self, obj):
        stages = obj.lifecycle_stages.all().order_by('sequence_order')
        return [
            {
                'name': s.get_stage_name_display(),
                'status': s.status,
                'planned_date': s.planned_date,
                'actual_date': s.actual_date,
                'is_achieved': s.status == 'ACHIEVED'
            }
            for s in stages
        ]


# 4. StaffKPIInsightSerializer - جديد
#
# يجمع إحصائيات شاملة لكل مهندس
class StaffKPIInsightSerializer(serializers.ModelSerializer):
    # ── الهوية (يحتاجها الكارد والمودال مباشرة) ──
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    username = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    department = serializers.CharField(read_only=True)

    # ── المقاييس ──
    total_days_worked = serializers.SerializerMethodField()
    total_tasks = serializers.SerializerMethodField()
    completed_tasks = serializers.SerializerMethodField()      # ✅ الإصلاح الجوهري
    on_hold_tasks = serializers.SerializerMethodField()
    active_tasks_count = serializers.SerializerMethodField()
    handover_count = serializers.SerializerMethodField()
    average_task_duration = serializers.SerializerMethodField()
    completion_rate = serializers.SerializerMethodField()       # ✅ يقرأ من Task

    # ── القوائم (للمودال) ──
    recent_handovers = serializers.SerializerMethodField()
    handover_logs = serializers.SerializerMethodField()
    active_tasks = serializers.SerializerMethodField()
    completed_tasks_list = serializers.SerializerMethodField()  # ✅ جديدة

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'role', 'role_display', 'department',
            'total_days_worked', 'total_tasks', 'completed_tasks', 'on_hold_tasks',
            'active_tasks_count', 'handover_count', 'average_task_duration', 'completion_rate',
            'recent_handovers', 'handover_logs', 'active_tasks', 'completed_tasks_list',
        ]

    def _tasks(self, obj):
        return Task.objects.filter(assigned_to=obj)

    def get_total_tasks(self, obj):
        return self._tasks(obj).count()

    def get_completed_tasks(self, obj):
        # ✅ COMPLETED و APPROVED معاً — هنا كان الباج
        return self._tasks(obj).filter(status__in=['COMPLETED', 'APPROVED']).count()

    def get_on_hold_tasks(self, obj):
        return self._tasks(obj).filter(is_on_hold=True).count()

    def get_active_tasks_count(self, obj):
        return self._tasks(obj).exclude(status__in=['COMPLETED', 'APPROVED']).count()

    def get_handover_count(self, obj):
        return StaffKPI.objects.filter(user=obj).count()

    def get_total_days_worked(self, obj):
        from django.db.models import Sum
        kpi_days = StaffKPI.objects.filter(user=obj).aggregate(t=Sum('days_worked'))['t'] or 0
        if kpi_days > 0:
            return kpi_days
        # احتياطي: من مدة المهام المنجزة إن لم توجد سجلات تسليم
        return self._tasks(obj).filter(
            status__in=['COMPLETED', 'APPROVED'], duration_days__gt=0
        ).aggregate(t=Sum('duration_days'))['t'] or 0

    def get_average_task_duration(self, obj):
        from django.db.models import Avg
        avg = self._tasks(obj).filter(
            status__in=['COMPLETED', 'APPROVED'], duration_days__gt=0
        ).aggregate(a=Avg('duration_days'))['a']
        return round(avg, 1) if avg else 0

    def get_completion_rate(self, obj):
        total = self.get_total_tasks(obj)
        if total == 0:
            return 0
        return round((self.get_completed_tasks(obj) / total) * 100, 1)

    def get_recent_handovers(self, obj):
        recent = StaffKPI.objects.filter(user=obj).select_related('project', 'task').order_by('-handover_date')[:5]
        return [{
            'project': k.project.name if k.project else None,
            'task': k.task.title if k.task else None,
            'days_worked': k.days_worked,
            'status_at_handover': k.status_at_handover,
            'handover_date': k.handover_date,
        } for k in recent]

    def get_handover_logs(self, obj):
        logs = StaffKPI.objects.filter(user=obj).select_related('project', 'task').order_by('-handover_date')
        return [{
            'project_name': k.project.name if k.project else '—',
            'task_title': k.task.title if k.task else '—',
            'task_discipline': k.task.discipline.name if (k.task and k.task.discipline) else '—',
            'days_worked': k.days_worked,
            'status_at_handover': k.status_at_handover,
            'handover_date': k.handover_date,
        } for k in logs]

    def get_active_tasks(self, obj):
        tasks = self._tasks(obj).exclude(status__in=['COMPLETED', 'APPROVED']).select_related('project', 'discipline')[:10]
        return [{
            'id': t.id,
            'title': t.title or (t.discipline.name if t.discipline else '—'),
            'discipline_name': t.discipline.name if t.discipline else '—',
            'project_name': t.project.name if t.project else '—',
            'project_no': t.project.project_no if t.project else '—',
            'progress_percentage': t.progress_percentage,
            'status': t.status,
        } for t in tasks]

    def get_completed_tasks_list(self, obj):
        tasks = self._tasks(obj).filter(status__in=['COMPLETED', 'APPROVED']).select_related('project', 'discipline').order_by('-approval_date', '-end_date')[:10]
        return [{
            'id': t.id,
            'title': t.title or (t.discipline.name if t.discipline else '—'),
            'discipline_name': t.discipline.name if t.discipline else '—',
            'project_name': t.project.name if t.project else '—',
            'project_no': t.project.project_no if t.project else '—',
            'status': t.status,
            'approval_date': t.approval_date or t.end_date,
        } for t in tasks]
# 5. ClientDirectorySerializer - جديد
#
# Client Directory مع الإحصائيات للمديرين

class ClientDirectorySerializer(serializers.ModelSerializer):
    active_projects_count = serializers.SerializerMethodField()
    closed_projects_count = serializers.SerializerMethodField()
    total_projects_count = serializers.SerializerMethodField()
    total_contract_value = serializers.SerializerMethodField()
    latest_project = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            'id', 'name', 'phone', 'email',
            'active_projects_count', 'closed_projects_count',
            'total_projects_count', 'total_contract_value',
            'latest_project', 'created_at'
        ]

    def get_active_projects_count(self, obj):
        return obj.projects.filter(is_active=True).count()

    def get_closed_projects_count(self, obj):
        return obj.projects.filter(is_active=False).count()

    def get_total_projects_count(self, obj):
        return obj.projects.count()

    def get_total_contract_value(self, obj):
        from django.db.models import Sum
        total = Invoice.objects.filter(
            project__client=obj
        ).exclude(status__in=['DRAFT', 'CANCELLED']).aggregate(
            total=Sum('total_amount')
        )['total']
        return total or 0

    def get_latest_project(self, obj):
        latest = obj.projects.order_by('-created_at').first()
        if latest:
            return {
                'id': latest.id,
                'name': latest.name,
                'project_no': latest.project_no,
                'status': 'Active' if latest.is_active else 'Closed'
            }
        return None


# 6. OfferStatusSerializer - جديد
#
# نموذج منفصل واضح لحالة العرض

class OfferStatusSerializer(serializers.ModelSerializer):
    offer_status_display = serializers.CharField(source='get_offer_status_display', read_only=True)
    contract_status_display = serializers.CharField(source='get_contract_status_display', read_only=True)
    can_upload_contract = serializers.SerializerMethodField()
    offer_history = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'project_no', 'name',
            'offer_status', 'offer_status_display',
            'contract_status', 'contract_status_display',
            'contract_file',
            'can_upload_contract',
            'offer_history'
        ]

    def get_can_upload_contract(self, obj):
        """
        رفع العقد مسموح فقط للإدارة والمحاسب
        """
        request = self.context.get('request')
        if request and request.user:
            return (request.user.role == 'SECRETARY' and request.user.department == 'Management')
        return False

    def get_offer_history(self, obj):
        """
        تاريخ التغييرات على حالة العرض من AuditLog
        """
        logs = AuditLog.objects.filter(
            project=obj,
            action_type__in=['PROJECT_UPDATED', 'PRIORITY_CHANGED']
        ).order_by('-created_at')[:5]
        return [
            {
                'action': log.action_type,
                'details': log.details,
                'by': log.user.get_full_name() if log.user else None,
                'date': log.created_at
            }
            for log in logs
        ]


# 7. SupervisionInternalReviewSerializer - جديد
#
# Serializer خاص لمهندسي الإشراف لتحديث Internal Design Review

class SupervisionInternalReviewSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    stage_display = serializers.CharField(source='get_stage_name_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    can_update = serializers.SerializerMethodField()

    class Meta:
        model = InternalReviewStage
        fields = [
            'id', 'project', 'project_name',
            'stage_name', 'stage_display',
            'status', 'status_display',
            'assigned_to', 'assigned_to_name',
            'reviewer', 'review_date',
            'can_update', 'created_at'
        ]
        read_only_fields = ['approved_by', 'approved_at']

    def get_can_update(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        user = request.user
        is_assigned = obj.assigned_to == user
        is_manager = user.role in ['SUP_MGR', 'PM', 'GM', 'AGM']
        return is_assigned or is_manager

    def update(self, instance, validated_data):
        if 'status' in validated_data:
            new_status = validated_data['status']
            if new_status == 'UNDER_REVIEW' and instance.status == 'PENDING':
                instance.reviewer = self.context['request'].user
                instance.review_date = timezone.now().date()
            elif new_status == 'APPROVED' and instance.status == 'UNDER_REVIEW':
                instance.approved_by = self.context['request'].user
                instance.approved_at = timezone.now()
        return super().update(instance, validated_data)


# 8. ContractFileUploadSerializer - جديد
#
# رفع ملف العقد مع الصلاحيات

class ContractFileUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'contract_file']


# 9. GlobalFilterSerializer - جديد

class GlobalFilterSerializer(serializers.Serializer):
    """
    Serializer للبحث الشامل مع فلاتر متعددة
    """
    query = serializers.CharField(required=False, allow_blank=True)
    scope = serializers.ChoiceField(
        choices=Project.Scope.choices,
        required=False,
        allow_blank=True
    )
    status = serializers.ChoiceField(
        choices=[('ACTIVE', 'Active'), ('CLOSED', 'Closed')],
        required=False,
        allow_blank=True
    )
    stage = serializers.CharField(required=False, allow_blank=True)
    priority = serializers.ChoiceField(
        choices=Project.PriorityStatus.choices,
        required=False,
        allow_blank=True
    )
    client_id = serializers.IntegerField(required=False, allow_null=True)
    permit_status = serializers.ChoiceField(
        choices=Project.PermitStatus.choices,
        required=False,
        allow_blank=True
    )
    start_date_from = serializers.DateField(required=False)
    start_date_to = serializers.DateField(required=False)



class SupervisionReplacementRequestSerializer(serializers.ModelSerializer):
    """
    Serializer لطلبات استبدال فريق الإشراف
    """
    # الحقول المرتبطة للقراءة
    assignment = SupervisionTeamAssignmentSerializer(read_only=True)
    assignment_id = serializers.PrimaryKeyRelatedField(
        queryset=SupervisionTeamAssignment.objects.all(),
        source='assignment',
        write_only=True,
        required=False
    )
    
    requested_by = UserSerializer(read_only=True)
    requested_by_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='requested_by',
        write_only=True,
        required=False
    )
    
    suggested_engineer = UserSerializer(read_only=True)
    suggested_engineer_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='suggested_engineer',
        write_only=True
    )
    
    responded_by = UserSerializer(read_only=True)
    responded_by_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='responded_by',
        write_only=True,
        required=False
    )
    
    # الحقول الإضافية
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = SupervisionReplacementRequest
        fields = [
            'id',
            'assignment',
            'assignment_id',
            'requested_by',
            'requested_by_id',
            'suggested_engineer',
            'suggested_engineer_id',
            'status',
            'status_display',
            'reason',
            'response_reason',
            'responded_by',
            'responded_by_id',
            'responded_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'requested_by',
            'status',
            'responded_by',
            'responded_at',
            'created_at',
            'updated_at',
        ]
    
    def create(self, validated_data):
        # تعيين المستخدم الحالي كـ requested_by تلقائياً
        if 'requested_by' not in validated_data:
            validated_data['requested_by'] = self.context['request'].user
        
        # الحالة الافتراضية PENDING
        if 'status' not in validated_data:
            validated_data['status'] = SupervisionReplacementRequest.Status.PENDING
        
        return super().create(validated_data)
    


class PaymentScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentSchedule
        fields = '__all__'

class InvoiceFileSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    
    class Meta:
        model = InvoiceFile
        fields = '__all__'

class LifecycleHistorySerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source='performed_by.get_full_name', read_only=True)
    stage_name = serializers.CharField(source='stage.stage_name', read_only=True)
    
    class Meta:
        model = LifecycleHistory
        fields = '__all__'


class ProjectCreateSerializer(serializers.ModelSerializer):
    # حقول المقاول المضمّن (للسكرتيرة الإشراف) — write_only
    contractor_name         = serializers.CharField(write_only=True, required=False, allow_blank=True)
    contractor_contact_person = serializers.CharField(write_only=True, required=False, allow_blank=True)
    contractor_phone        = serializers.CharField(write_only=True, required=False, allow_blank=True)
    contractor_email        = serializers.EmailField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Project
        fields = [
            'name', 'project_no', 'application_no', 'pin_no', 'scope',
            'client', 'contractor',                 # ← contractor قابل للكتابة
            'start_date', 'duration_days', 'location', 'building_type',
            'bua', 'plot_area', 'floors', 'priority',
            'permit_status', 'commencement_status',
            'offer_status', 'contract_status', 'internal_design_review_required',
            'contract_value', 'design_company',
            # ══ الحقول الناقصة ══
            'owner', 'supervision_consultant', 'permit_no', 'permit_date', 'permit_deadline',
            # ═════════════════════
            # الحقول المضمّنة
            'contractor_name', 'contractor_contact_person',
            'contractor_phone', 'contractor_email',
                    'apartments', 'shops', 'parking', 'description',             'application_type',
            'end_date' # ✅ اتضافوا
        ]





class MyInternalReviewProjectSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.SerializerMethodField()
    review_stages = InternalReviewStageSerializer(source='internal_reviews', many=True, read_only=True)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ['id', 'project_no', 'name', 'requested_by_name', 'review_stages', 'progress']

    def get_requested_by_name(self, obj):
        u = obj.internal_review_requested_by
        return u.get_full_name() if u else None

    def get_progress(self, obj):
        stages = obj.internal_reviews.all()
        total = stages.count()
        approved = stages.filter(status='APPROVED').count()
        return {
            'total': total, 'approved': approved,
            'all_approved': total > 0 and approved == total,
            'percentage': round((approved / total) * 100) if total else 0,
        }


# ═══════════════════════════════════════════════════════════════
#  Change Order / Revision — Serializers (إضافة صافية)
# ═══════════════════════════════════════════════════════════════
class ChangeOrderCreateSerializer(serializers.Serializer):
    """حقول الـ Revision الجديدة فقط؛ الباقي يُورَث من Parent داخل الـ service."""
    revision_number     = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    new_application_no  = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    revision_start_date = serializers.DateField(required=False, allow_null=True)
    change_order_reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    # تجاوزات اختيارية لاسم/رقم الـ sub (وإلا يولّدها الـ service من Parent)
    name                = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    project_no          = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ChangeOrderListSerializer(serializers.ModelSerializer):
    change_order_status_display = serializers.CharField(
        source='get_change_order_status_display', read_only=True, allow_null=True)
    parent_project_no   = serializers.CharField(source='parent_project.project_no', read_only=True)
    parent_project_name = serializers.CharField(source='parent_project.name', read_only=True)
    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'project_no', 'name', 'scope', 'is_active',
            'revision_number', 'new_application_no', 'revision_start_date',
            'change_order_reason', 'change_order_status', 'change_order_status_display',
            'parent_project', 'parent_project_no', 'parent_project_name',
            'progress_percentage', 'created_at',
        ]

    def get_progress_percentage(self, obj):
        total = obj.lifecycle_stages.count()
        if not total:
            return "0.0%"
        done = obj.lifecycle_stages.filter(status='ACHIEVED').count()
        return f"{round((done / total) * 100, 2)}%"


class ChangeOrderDetailSerializer(ChangeOrderListSerializer):
    client_name          = serializers.CharField(source='client.name', read_only=True)
    lifecycle_stages     = ProjectLifecycleStageSerializer(many=True, read_only=True)
    tasks_count          = serializers.SerializerMethodField()
    completed_tasks_count = serializers.SerializerMethodField()

    class Meta(ChangeOrderListSerializer.Meta):
        fields = ChangeOrderListSerializer.Meta.fields + [
            'client_name', 'start_date', 'lifecycle_stages',
            'tasks_count', 'completed_tasks_count',
        ]

    def get_tasks_count(self, obj):
        return obj.tasks.count()

    def get_completed_tasks_count(self, obj):
        return obj.tasks.filter(status__in=['COMPLETED', 'APPROVED']).count()


class ChangeOrderActionSerializer(serializers.Serializer):
    """payload لـ reject / cancel (reason مطلوب للرفض ويُتحقق منه في الـ view)."""
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)



class ChangeOrderOptionSerializer(serializers.ModelSerializer):
    parent_project_no   = serializers.CharField(source='parent_project.project_no', read_only=True)
    parent_project_name = serializers.CharField(source='parent_project.name', read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'project_no', 'name', 'revision_number',
                  'parent_project_no', 'parent_project_name', 'is_active']















class ReplacementRequestSerializer(serializers.ModelSerializer):
    # يمكنك الإبقاء على هذه الحقول إذا كنت تستخدمها في مكان آخر، أو يمكنك مسحها
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)
    suggested_engineer_name = serializers.CharField(source='suggested_engineer.get_full_name', read_only=True)
    responded_by_name = serializers.CharField(source='responded_by.get_full_name', read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)

    class Meta:
        model = ReplacementRequest
        fields = '__all__'
        read_only_fields = (
            'task',
            'requested_by',
            'status',
            'responded_by',
            'responded_at',
        )

    def to_representation(self, instance):
        # 1. استدعاء السلوك الافتراضي الذي يجلب الحقول والأرقام
        representation = super().to_representation(instance)
        
        # 2. تحويل بيانات المهندس صاحب الطلب إلى Object يطابق الفرونت إند
        if instance.requested_by:
            representation['requested_by'] = {
                'id': instance.requested_by.id,
                'first_name': instance.requested_by.first_name,
                'last_name': instance.requested_by.last_name,
            }

        # 3. تحويل بيانات المهندس المقترح إلى Object
        if instance.suggested_engineer:
            representation['suggested_engineer'] = {
                'id': instance.suggested_engineer.id,
                'first_name': instance.suggested_engineer.first_name,
                'last_name': instance.suggested_engineer.last_name,
            }

        # 4. تحويل بيانات المهمة والمشروع المرتبط بها إلى Object
        if instance.task:
            project = getattr(instance.task, 'project', None)
            representation['task'] = {
                'id': instance.task.id,
                'title': getattr(instance.task, 'title', ''),
                'discipline_name': getattr(instance.task, 'discipline_name', ''),
                'project': {
                    'id': project.id,
                    'project_no': project.project_no,
                    'name': project.name
                } if project else None
            }
            
        return representation





ExternalLogSerializer