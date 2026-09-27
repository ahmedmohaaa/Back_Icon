from datetime import timedelta

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_save
# 1. Base Models & Users
# ═══ خريطة: مرحلة المراجعة الداخلية ← مراحل الـ Discipline المعروضة ═══
# عدّلها من هنا فقط لتغيير ما يظهر في قائمة Discipline لكل مرحلة.
REVIEW_STAGE_TO_DISCIPLINE_STAGES = {
    'DESIGN_CRITERIA':  ['CONCEPT'],
    'CONCEPT_DESIGN':   ['CONCEPT', 'DC1'],
    'SCHEMATIC_DESIGN': ['DC1'],
    'DETAILED_DESIGN':  ['DC2'],
    'IFC_PACKAGE':      ['DC2', 'TENDER'],
}


SUPERVISION_TASK_MANAGER_USERNAMES = (
    'ahmed.zabady',
)

SUPERVISION_ENGINEER_USERNAMES = (
    # SUPERVISION - CIVIL
    'nader.bekhit',
    'syed.mahmoud',
    'muhammed.faisal',
    'eslam.mahdy',
    'ahmed.yosef',
    'saheer.parayil',
    'mahmoud.hamed',
    'waled.mohamed',
    'ahmed.zaki',
    'mohamed.salah',
    'loai.hamouda',
    'mohamed.elshenawy',

    # SUPERVISION - ELECTRICAL
    'ahmed.ghazy',
    'muammer.muhammed',
    'abdulrahim.ahmed',
    'ali.odeh',

    # SUPERVISION - MECHANICAL
    'noufal.thodi',
    'mohammed.shemseer',
    'mohammed.rashid',

    # SUPERVISION - ARCHITECT
    'mohamed.hisham',
    'mohamed.salem',

    # SUPERVISION - PLANNER
    'mani.kumar',

    # SUPERVISION - DC
    'jocelyn.mallilin',
    'allen.guanzon',
    'jason.cuison',
    'mostafa.zabady',
    'isuru.palliyaguruge',
    'faseela.foroth',
)

DESIGN_TASK_ASSIGNEE_USERNAMES = (
    # DESIGN ENGINEERS
    'salah.ahmad',
    'basem.taha',
    'vicky.jr',
    'mohammad.mostafa',
    'mohammad.alqadi',
    'mahmoud.aldemyati',
    'abdulhamid.ahmad',
    'jan.bina',
    'shaaban.karam',
    'basel.shaat',
    'israa.omran',
    'ahmad.alqadi',
    'yousef.amro',

    # DESIGN DRAFTSMEN
    'salman.saeed',
    'shahajan.puthi',
    'mohammad.raheem',
    'mohammad.lebbe',
    'shammer.pareeth',
    'mojib.rahiman',
    'md.hossain',
)
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class User(AbstractUser):
    class Role(models.TextChoices):
        GM = 'GM', _('General Manager')
        AGM = 'AGM', _('Technical Manager')
        DESIGN_MGR = 'DESIGN_MGR', _('Design Manager')
        SUP_MGR = 'SUP_MGR', _('Supervision Manager')
        SENIOR_ENG = 'SENIOR_ENG', _('Senior Engineer')
        ENGINEER = 'ENGINEER', _('Engineer')
        DRAFTSMAN = 'DRAFTSMAN', _('Draftsman')
        SECRETARY = 'SECRETARY', _('Secretary')
        ACCOUNTANT = 'ACCOUNTANT', _('Accountant')
        DOC_CONTROLLER = 'DOC_CONTROLLER', _('Document Controller')
        PM = 'PM', _('Project Manager')
    discipline = models.CharField(max_length=50, blank=True, null=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    department = models.CharField(max_length=50, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

class Client(TimeStampedModel):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

class Contractor(TimeStampedModel):
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)


# 2. Master Data

class MasterDiscipline(TimeStampedModel):
    class Stage(models.TextChoices):
        CONCEPT = 'CONCEPT', 'Concept Design'
        DC1 = 'DC1', 'DC1'
        DC2 = 'DC2', 'DC2'
        TENDER = 'TENDER', 'Tender Documents'
        OTHER = 'OTHER', 'Other'  # ✅ مهم جداً لإتاحة فلترة ومهام Other

    name = models.CharField(max_length=100)
    stage = models.CharField(max_length=20, choices=Stage.choices)

    def __str__(self):
        return f"{self.name} ({self.get_stage_display()})"


# NEW: Discipline Item (القائمة الكاملة لكل عناصر DC1/DC2)

class DisciplineItem(TimeStampedModel):
    class Stage(models.TextChoices):
        CONCEPT = 'CONCEPT', 'Concept Design'
        DC1 = 'DC1', 'DC1'
        DC2 = 'DC2', 'DC2'
        TENDER = 'TENDER', 'Tender Documents'

    class Department(models.TextChoices):
        ARCH = 'ARCH', 'Architecture'
        ELEC = 'ELEC', 'Electrical'
        MECH = 'MECH', 'Mechanical'
        STRUCT = 'STRUCT', 'Structural'

    name = models.CharField(max_length=100)
    stage = models.CharField(max_length=20, choices=Stage.choices)
    department = models.CharField(max_length=20, choices=Department.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['stage', 'department', 'name']
        unique_together = ['name', 'stage', 'department']

    def __str__(self):
        return f"{self.name} - {self.get_stage_display()} - {self.get_department_display()}"


# 3. Core Project
class Project(TimeStampedModel):
    class Scope(models.TextChoices):
        DESIGN = 'DESIGN', 'Design'
        SUPERVISION = 'SUPERVISION', 'Supervision'
        BOTH = 'BOTH', 'Both'

    class PriorityStatus(models.TextChoices):
        URGENT = 'URGENT', 'Urgent'
        HIGH = 'HIGH', 'High'
        MEDIUM = 'MEDIUM', 'Medium'
        LOW = 'LOW', 'Low'

    class GeneralStatus(models.TextChoices):
        NOT_SUBMITTED = 'NOT_SUBMITTED', 'Not submitted yet'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        APPROVED = 'APPROVED', 'Approved'

    class PermitStatus(models.TextChoices):
        NOT_ISSUED = 'NOT_ISSUED', 'Not Issued'
        PENDING_AUTHORITY = 'PENDING_AUTHORITY', 'Pending Authority'
        ISSUED = 'ISSUED', 'Approved/Issued'
    class ChangeOrderStatus(models.TextChoices):
        PENDING_CONFIRMATION = 'PENDING_CONFIRMATION', 'Pending Confirmation'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        REJECTED = 'REJECTED', 'Rejected'
        CANCELLED = 'CANCELLED', 'Cancelled'
    class ApplicationType(models.TextChoices):
       NEW_PERMIT = 'NEW_PERMIT', 'New Permit'
       MODIFICATION_PERMIT = 'MODIFICATION_PERMIT', 'Modification Permit'
       COMPLETION_CERTIFICATE = 'COMPLETION_CERTIFICATE', 'Completion Certificate'
       MAINTENANCE_DEMOLITION = 'MAINTENANCE_DEMOLITION', 'Maintenance and Demolition'
    name = models.CharField(max_length=255)
    project_no = models.CharField(max_length=100)
    application_no = models.CharField(max_length=100, blank=True, null=True)
    pin_no = models.CharField(max_length=100, blank=True, null=True)
    scope = models.CharField(max_length=20, choices=Scope.choices)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    
    location = models.CharField(max_length=255, blank=True, null=True)
    building_type = models.CharField(max_length=100, default='Residential')
    far = models.CharField(max_length=50, blank=True, null=True)
    bua = models.CharField(max_length=100, blank=True, null=True)
    plot_area = models.CharField(max_length=100, blank=True, null=True)
    floors = models.CharField(max_length=50, blank=True, null=True)
    parking = models.CharField(max_length=100, blank=True, null=True)
    apartments = models.IntegerField(default=0)
    shops = models.IntegerField(default=0)
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='projects')
    contractor = models.ForeignKey(Contractor, on_delete=models.SET_NULL, null=True, blank=True)
    contractors = models.ManyToManyField(
    Contractor, blank=True, related_name='projects_as_contractors',
    verbose_name='المقاولون (مشاريع الإشراف)')    
    start_date = models.DateField(null=True, blank=True)
    duration_days = models.IntegerField(default=0)
    permit_status = models.CharField(max_length=30, choices=PermitStatus.choices, default=PermitStatus.NOT_ISSUED)
    commencement_status = models.CharField(max_length=30, choices=PermitStatus.choices, blank=True, null=True)
    
    offer_status = models.CharField(
        max_length=50,
        choices=[
          ('NOT_SUBMITTED', 'Not Submitted'),
          ('SUBMITTED', 'Submitted'),
          ('PENDING_BY_CLIENT', 'Pending by Client'),
          ('PREPARATION', 'Preparation'),
          ('APPROVED_SIGNED_BY_CLIENT', 'Approved & Signed by Client'),
          ('DECLINED_BY_CLIENT', 'Declined by Client'),
    ],
    default='NOT_SUBMITTED',
    )

    contract_status = models.CharField(
        max_length=50,
        choices=[
          ('NOT_SUBMITTED', 'Not Submitted'),
          ('SUBMITTED', 'Submitted'),
          ('PENDING_BY_CLIENT', 'Pending by Client'),
          ('PREPARATION', 'Preparation'),
          ('APPROVED_SIGNED_BY_CLIENT', 'Approved & Signed by Client'),
          ('DECLINED_BY_CLIENT', 'Declined by Client'),
        ],
        default='NOT_SUBMITTED',
    )
    contract_file = models.FileField(upload_to='contracts/', blank=True, null=True)
    internal_design_review_required = models.BooleanField(default=False)
    # داخل class Project — بجانب internal_design_review_required
    internal_review_assignees = models.ManyToManyField(
      'User', related_name='internal_review_projects', blank=True,
      help_text="مهندسو التصميم المعيَّنون لمراجعة هذا المشروع"
    )
    internal_review_requested_by = models.ForeignKey(
      'User', on_delete=models.SET_NULL, null=True, blank=True,
       related_name='requested_internal_reviews',
       help_text="مدير الإشراف الذي طلب المراجعة (يُنبَّه عند الاعتماد الكامل)"
    )
    priority = models.CharField(max_length=20, choices=PriorityStatus.choices, default=PriorityStatus.MEDIUM)

    parent_project = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_projects')
    revision_number = models.CharField(max_length=50, blank=True, null=True)
    revision_start_date = models.DateField(null=True, blank=True)
    new_application_no = models.CharField(max_length=100, blank=True, null=True)
    change_order_reason = models.TextField(blank=True, null=True)
    change_order_status = models.CharField(max_length=50, null=True, blank=True) # أو النوع المناسب لك
    # ── حقول المحرك التلقائي ──
    manager_start_override = models.BooleanField(
        default=False,
        help_text="المدير يفرض البدء قبل استلام الدفعة الأولى"
    )
    delivered = models.BooleanField(default=False)
    delivered_date = models.DateField(null=True, blank=True)
    closed_date = models.DateField(null=True, blank=True)
    contract_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    design_company = models.CharField(max_length=255, blank=True, null=True)
    application_type = models.CharField(
        max_length=30, choices=ApplicationType.choices, blank=True, null=True)
    end_date = models.DateField(null=True, blank=True)
    owner = models.CharField(max_length=255, blank=True, null=True, verbose_name="Owner")
    supervision_consultant = models.CharField(max_length=255, blank=True, null=True, verbose_name="Supervision Consultant")
    permit_no = models.CharField(max_length=100, blank=True, null=True, verbose_name="Permit No.")
    permit_date = models.DateField(null=True, blank=True, verbose_name="Permit Date (If Issued)")
    permit_deadline = models.DateField(null=True, blank=True, verbose_name="Permit Deadline (Pending)")
    class ChangeOrderStatus(models.TextChoices):
        PENDING_CONFIRMATION = "PENDING_CONFIRMATION", "Pending Confirmation"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    def computed_end_date(self):
        """✅ مصدر حقيقة واحد: Start Date + Duration"""
        if self.start_date and self.duration_days:
            return self.start_date + timedelta(days=self.duration_days)
        return None

    def save(self, *args, **kwargs):
        self.end_date = self.computed_end_date() or self.end_date
        super().save(*args, **kwargs)

    # ... باقي الـfields

    @property
    def is_change_order(self):
        return self.parent_project_id is not None

    def activate_internal_design_review(self):
        if self.internal_design_review_required:
            stages = [
                ('CRITERIA', 1), ('CONCEPT', 2), ('SCHEMATIC', 3),
                ('DETAILED', 4), ('IFC', 5),
            ]
            for stage_name, order in stages:
                InternalReviewStage.objects.get_or_create(
                    project=self, stage_name=stage_name,
                    defaults={'sequence_order': order}
                )
            return True
        return False

    # ═══════════════ محرك دورة الحياة التلقائي ═══════════════
    DESIGN_ORDER = ['OFFER', 'CONTRACT_SUBMITTED', 'CONTRACT_SIGNED',
                    'CONCEPT', 'DC1', 'DC2', 'TENDER', 'CLOSED']
    SUPERVISION_ORDER = ['OFFER', 'CONTRACT_SUBMITTED', 'CONTRACT_SIGNED',
                         'COLLECTION', 'CLOSED']
    def lifecycle_order(self):
        return (self.SUPERVISION_ORDER if self.scope == self.Scope.SUPERVISION
                else self.DESIGN_ORDER)

    def _first_payment_received(self):
        return self.invoices.filter(
            milestone_type='DOWN_PAYMENT',
            status__in=['PAID', 'PARTIALLY_PAID']
        ).exists()

    def _stage_done_condition(self, name):
        """هل تحقّق شرط إنجاز المرحلة؟ (بدون فحص ما قبلها)"""
        if name == 'OFFER':
            return self.offer_status in ('SUBMITTED', 'APPROVED')
        if name == 'CONTRACT_SUBMITTED':
            return self.contract_status in ('SUBMITTED', 'APPROVED')
        if name == 'CONTRACT_SIGNED':
            return (self.contract_status == 'APPROVED' and
                    (self._first_payment_received() or self.manager_start_override))
        if name in ('CONCEPT', 'DC1', 'DC2', 'TENDER'):
            qs = self.tasks.filter(stage=name)
            return qs.exists() and qs.exclude(status='APPROVED').count() == 0
        if name == 'COLLECTION':
            return self.commencement_status == 'ISSUED'
        if name == 'CLOSED':
            return True
        return False
    def sync_contractual_lifecycle(self):
        """
        مزامنة حالات العرض/العقد مع مراحل الـ Lifecycle.
        - APPROVED_SIGNED_BY_CLIENT → تحقيق CONTRACT_SIGNED
        - SUBMITTED → تحقيق CONTRACT_SUBMITTED (إذا لم يتحقق)
        - APPROVED → تحقيق OFFER (إذا لم يتحقق)
        """
        from .models import ProjectLifecycleStage
        
        synced_stages = []
        
        # ✅ المرحلة الأولى: OFFER / RFQ
        if self.offer_status in ['SUBMITTED', 'PENDING_BY_CLIENT', 'PREPARATION', 'APPROVED_SIGNED_BY_CLIENT']:
            offer_stage = self.lifecycle_stages.filter(stage_name='OFFER').first()
            if offer_stage and offer_stage.status != 'ACHIEVED':
                offer_stage.status = 'ACHIEVED'
                offer_stage.actual_date = timezone.now().date()
                offer_stage.save()
                synced_stages.append('OFFER')
        
        # ✅ المرحلة الثانية: CONTRACT_SUBMITTED
        if self.contract_status in ['SUBMITTED', 'PENDING_BY_CLIENT', 'PREPARATION', 'APPROVED_SIGNED_BY_CLIENT']:
            contract_sub_stage = self.lifecycle_stages.filter(stage_name='CONTRACT_SUBMITTED').first()
            if contract_sub_stage and contract_sub_stage.status != 'ACHIEVED':
                contract_sub_stage.status = 'ACHIEVED'
                contract_sub_stage.actual_date = timezone.now().date()
                contract_sub_stage.save()
                synced_stages.append('CONTRACT_SUBMITTED')
        
        # ✅ المرحلة الثالثة: CONTRACT_SIGNED
        if self.contract_status == 'APPROVED_SIGNED_BY_CLIENT':
            contract_signed_stage = self.lifecycle_stages.filter(stage_name='CONTRACT_SIGNED').first()
            if contract_signed_stage and contract_signed_stage.status != 'ACHIEVED':
                contract_signed_stage.status = 'ACHIEVED'
                contract_signed_stage.actual_date = timezone.now().date()
                contract_signed_stage.save()
                synced_stages.append('CONTRACT_SIGNED')
        
        return synced_stages
    def _missing_reasons(self, name):
        """أسباب مفصّلة لعدم إنجاز مرحلة (لرسائل الرفض)."""
        r = []
        if name == 'OFFER' and self.offer_status not in ('SUBMITTED', 'APPROVED'):
            r.append('العرض لم يُرفع/يُعتمد بعد (Offer status)')
        if name == 'CONTRACT_SUBMITTED' and self.contract_status not in ('SUBMITTED', 'APPROVED'):
            r.append('العقد لم يُرفع بعد (Contract status)')
        if name == 'CONTRACT_SIGNED':
            if self.contract_status != 'APPROVED':
                r.append('العقد لم يُعتمد بعد')
            elif not (self._first_payment_received() or self.manager_start_override):
                r.append('الدفعة الأولى غير مستلمة، ولا يوجد تجاوز من المدير')
        if name in ('CONCEPT', 'DC1', 'DC2', 'TENDER'):
            qs = self.tasks.filter(stage=name)
            if not qs.exists():
                r.append(f'لا توجد مهام {name} بعد')
            else:
                for t in qs.exclude(status='APPROVED'):
                    r.append(f'مهمة {name} غير معتمدة: {t.title or t.discipline}')
        if name == 'COLLECTION' and self.commencement_status != 'ISSUED':
            r.append('تصريح بدء التنفيذ (Commencement) ليس Issued')
        return r
    def evaluate_and_advance_lifecycle(self, actor=None):
        """
        يمشي على المراحل بالترتيب: أي مرحلة شروطها تحققت وما قبلها منجز
        → يُنجزها تلقائياً (ACHIEVED + actual_date) ويستمر للتالية.
        يتوقف عند أول مرحلة غير مكتملة. يرجع قائمة المراحل التي تقدمت.
        """
        from django.utils import timezone
        today = timezone.now().date()
        order = self.lifecycle_order()
        advanced = []
        for idx, name in enumerate(order):
            stage = self.lifecycle_stages.filter(stage_name=name).first()
            if not stage:
                continue
            if stage.status == 'ACHIEVED':
                continue
            # كل ما قبلها يجب أن يكون منجزاً
            prev_ok = True
            for i in range(idx):
                ps = self.lifecycle_stages.filter(stage_name=order[i]).first()
                if not ps or ps.status != 'ACHIEVED':
                    prev_ok = False
                    break
            if not prev_ok:
                break
            if self._stage_done_condition(name):
                stage.status = 'ACHIEVED'
                if not stage.actual_date:
                    stage.actual_date = today
                stage.save(update_fields=['status', 'actual_date'])
                advanced.append(name)
                AuditLog.objects.create(
                    project=self, user=actor,
                    action_type=AuditLog.ActionType.STAGE_ACTUAL_DATE_UPDATED,
                    details=f"Stage {name} auto-achieved by engine"
                )
            else:
                break   # توقّف عند أول مرحلة غير مكتملة
        # بصرياً: علّم المرحلة الفعّالة التالية بـ IN_PROGRESS
        # بصرياً: علّم المرحلة الفعّالة التالية بـ IN_PROGRESS
        nxt = self.lifecycle_stages.filter(status='UPCOMING').order_by('sequence_order').first()
        if nxt:
            nxt.status = 'IN_PROGRESS'
            nxt.save(update_fields=['status'])

        # ⭐ إغلاق تلقائي: لو CLOSED أصبحت ACHIEVED، أقفل المشروع فوراً
        closed_stage = self.lifecycle_stages.filter(stage_name='CLOSED').first()
        if closed_stage and closed_stage.status == 'ACHIEVED' and self.is_active:
            self.is_active = False
            self.closed_date = today
            self.save(update_fields=['is_active', 'closed_date'])
            AuditLog.objects.create(
                project=self, user=actor,
                action_type=AuditLog.ActionType.PROJECT_UPDATED,
                details="Project automatically CLOSED after final stage (TENDER/COLLECTION) completed."
            )
            U = get_user_model()
            for u in U.objects.filter(role__in=['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR']):
                Notification.objects.create(
                    user=u, sender=actor, notification_type='PROJECT_CLOSED',
                    title='تم إغلاق المشروع تلقائياً',
                    message=f'المشروع {self.project_no} أُغلق بعد إنجاز المرحلة النهائية.',
                    related_link=f'/projects/{self.id}'
                )

        return advanced


    def sync_start_date_with_first_payment(self, actor=None):
        """
        Actual Start = تاريخ أول (أقدم) دفعة سجّلها المحاسب للمشروع
        (تصميم أو إشراف). يُحدَّث تلقائيًا عند تسجيل أي دفعة،
        ولا يكتب شيئًا ما لم يتغير التاريخ فعليًا.
        """
        dates = list(
            InvoicePayment.objects.filter(invoice__project=self)
            .values_list('payment_date', flat=True)
        ) + list(
            self.supervision_invoices.filter(amount_paid__gt=0)
            .exclude(payment_date=None)
            .values_list('payment_date', flat=True)
        )
        if not dates:
            return False
        first = min(dates)                 # تاريخ أول دفعة فعلية
        if self.start_date == first:       # لا تغيير؟ لا كتابة
            return False
        self.start_date = first
        self.save(update_fields=['start_date'])
        AuditLog.objects.create(
            project=self,
            user=actor,
            action_type=AuditLog.ActionType.PROJECT_UPDATED,
            details=f"Actual Start auto-synced to first payment date: {first}",
        )
        self.evaluate_and_advance_lifecycle(actor=actor)
        return True

    def can_close_reasons(self):
        """checklist الإغلاق — يرجع [] إن مسموح، وإلا قائمة الموانع."""
        reasons = []
        for name in self.lifecycle_order():
            s = self.lifecycle_stages.filter(stage_name=name).first()
            if not s or s.status != 'ACHIEVED':
                reasons.append(f'المرحلة {name} غير منجزة')
            elif not s.actual_date:
                reasons.append(f'المرحلة {name} بلا تاريخ فعلي')
        open_tasks = self.tasks.exclude(task_type='CHANGE_ORDER').exclude(status='APPROVED')
        if open_tasks.exists():
            reasons.append(f'{open_tasks.count()} مهمة (غير CO) غير معتمدة')
        open_inv = self.invoices.exclude(status__in=['PAID', 'CANCELLED'])
        if open_inv.exists():
            reasons.append(f'{open_inv.count()} فاتورة غير مسدّدة/ملغاة')
        if not self.delivered:
            reasons.append('المشروع لم يُعلَّم كمُسلَّم (Delivered)')
        if self.tasks.filter(task_type='CHANGE_ORDER').exclude(
                status__in=['APPROVED', 'COMPLETED']).exists():
            reasons.append('يوجد Change Order مفتوح')
        if self.sub_projects.filter(is_active=True).exists():
            reasons.append('يوجد Sub-Project (Change Order) نشط')
        return reasons

    def close_project(self, actor=None):
        from django.utils import timezone
        from django.contrib.auth import get_user_model
        reasons = self.can_close_reasons()
        if reasons:
            return False, reasons
        today = timezone.now().date()
        cs = self.lifecycle_stages.filter(stage_name='CLOSED').first()
        if cs:
            cs.status = 'ACHIEVED'
            cs.actual_date = today
            cs.save(update_fields=['status', 'actual_date'])
        self.is_active = False
        self.closed_date = today
        self.save(update_fields=['is_active', 'closed_date'])
        AuditLog.objects.create(
            project=self, user=actor,
            action_type=AuditLog.ActionType.PROJECT_UPDATED,
            details="Project CLOSED automatically after full checklist passed"
        )
        U = get_user_model()
        for u in U.objects.filter(role__in=['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR']):
            Notification.objects.create(
                user=u, sender=actor, notification_type='PROJECT_CLOSED',
                title='تم إغلاق المشروع',
                message=f'المشروع {self.project_no} أُغلق بعد اكتمال كل الشروط',
                related_link=f'/projects/{self.id}'
            )
        return True, [] 

    def calculate_planned_dates(self):
        if not self.start_date:
            return None
        from datetime import timedelta
        d = self.duration_days or 90         # يقرأ الحقل الفعلي أخيراً
        s = self.start_date
        return {
            'OFFER': s,
            'CONTRACT_SUBMITTED': s + timedelta(days=7),
            'CONTRACT_SIGNED': s + timedelta(days=14),
            'DESIGN_PHASE': s + timedelta(days=round(d * 0.5)),
            'COLLECTION': s + timedelta(days=round(d * 0.85)),
            'CLOSED': s + timedelta(days=d),
        }

    def auto_update_lifecycle_planned_dates(self):

        planned = self.calculate_planned_dates()
        if not planned:
            return
        for stage in self.lifecycle_stages.all():
            if stage.stage_name in planned and not stage.planned_date:
                stage.planned_date = planned[stage.stage_name]
                stage.save(update_fields=['planned_date'])



    def activate_internal_design_review(self, requested_by=None):
        """يُنشئ المراحل الخمس إن لم تُنشأ، ويُسجّل من طلب المراجعة."""
        self.internal_design_review_required = True
        if requested_by:
            self.internal_review_requested_by = requested_by
        self.save(update_fields=[
            'internal_design_review_required',
            *(['internal_review_requested_by'] if requested_by else []),
        ])
        for name, order in InternalReviewStage.ORDER.items():
            InternalReviewStage.objects.get_or_create(
                project=self, stage_name=name,
                defaults={'sequence_order': order, 'status': 'PENDING'},
            )
    def save(self, *args, **kwargs):
        if self.start_date and self.duration_days:
            self.end_date = self.start_date + timedelta(days=self.duration_days)
        super().save(*args, **kwargs)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["parent_project", "revision_number"],
                condition=models.Q(parent_project__isnull=False),
                name="unique_revision_per_parent",
            ),
        ]

class PriorityHistory(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='priority_history')
    priority = models.CharField(max_length=20, choices=Project.PriorityStatus.choices)
    reason = models.TextField()
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)



class ProjectLifecycleStage(TimeStampedModel):
    class StageNames(models.TextChoices):
        # ── مشتركة ──
        OFFER = 'OFFER', 'RFQ / Offer'
        CONTRACT_SUBMITTED = 'CONTRACT_SUBMITTED', 'Contract Submitted'
        CONTRACT_SIGNED = 'CONTRACT_SIGNED', 'Contract Signed'
        # ── مراحل التصميم (تفكيك Design Phase) → تكوّن الـ 7 مراحل ──
        CONCEPT = 'CONCEPT', 'Concept Design'
        DC1 = 'DC1', 'DC1'
        DC2 = 'DC2', 'DC2'
        TENDER = 'TENDER', 'Tender Documents'
        # ── مراحل الإشراف / إرثية ──
        DESIGN_PHASE = 'DESIGN_PHASE', 'Design Phase'   # مُبقاة للتوافق مع بيانات قديمة
        COLLECTION = 'COLLECTION', 'Collection'
        CLOSED = 'CLOSED', 'Closed'
    class Status(models.TextChoices):
        UPCOMING = 'UPCOMING', 'Upcoming'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'   
        ACHIEVED = 'ACHIEVED', 'Achieved'
        OVERDUE = 'OVERDUE', 'Overdue'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='lifecycle_stages')
    stage_name = models.CharField(max_length=50, choices=StageNames.choices)
    sequence_order = models.PositiveSmallIntegerField(default=0)
    planned_date = models.DateField(null=True, blank=True)
    planned_end_date = models.DateField(null=True, blank=True)
    actual_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPCOMING)

    class Meta:
        ordering = ['sequence_order']


class InternalReviewStage(models.Model):
    class StageName(models.TextChoices):
        DESIGN_CRITERIA  = 'DESIGN_CRITERIA',  'Design Criteria'
        CONCEPT_DESIGN   = 'CONCEPT_DESIGN',   'Concept Design'
        SCHEMATIC_DESIGN = 'SCHEMATIC_DESIGN', 'Schematic Design'
        DETAILED_DESIGN  = 'DETAILED_DESIGN',  'Detailed Design'
        IFC_PACKAGE      = 'IFC_PACKAGE',      'IFC Package'

    class Status(models.TextChoices):
        PENDING      = 'PENDING',      'Pending'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
        APPROVED     = 'APPROVED',     'Approved'

    ORDER = {  
        'DESIGN_CRITERIA': 1, 'CONCEPT_DESIGN': 2, 'SCHEMATIC_DESIGN': 3,
        'DETAILED_DESIGN': 4, 'IFC_PACKAGE': 5,
    }

    project      = models.ForeignKey('Project', on_delete=models.CASCADE, related_name='internal_reviews')
    stage_name   = models.CharField(max_length=20, choices=StageName.choices)
    status       = models.CharField(max_length=14, choices=Status.choices, default=Status.PENDING)
    sequence_order = models.PositiveIntegerField(default=0)
    updated_by   = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    updated_at   = models.DateTimeField(null=True, blank=True)
    notes        = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['sequence_order']
        unique_together = ('project', 'stage_name')

    def save(self, *args, **kwargs):
        if not self.sequence_order:
            self.sequence_order = self.ORDER.get(self.stage_name, 0)
        super().save(*args, **kwargs)

class TenderingModule(TimeStampedModel):
    class Status(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', 'Not Started'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'

    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='tendering')
    boq_status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    boq_notes = models.TextField(blank=True, null=True)
    specs_status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    specs_notes = models.TextField(blank=True, null=True)
    conditions_status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    conditions_notes = models.TextField(blank=True, null=True)

@receiver(post_save, sender=Project)
def create_tendering_module(sender, instance, created, **kwargs):
    """إنشاء TenderingModule تلقائياً عند إنشاء Project جديد"""
    if created:
        TenderingModule.objects.get_or_create(project=instance)
# NEW: Discipline Tracking (تتبع حالة كل عنصر)

class DisciplineTracking(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        APPROVED = 'APPROVED', 'Approved'
        ON_HOLD = 'ON_HOLD', 'On Hold'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='discipline_trackings')
    discipline_item = models.ForeignKey(DisciplineItem, on_delete=models.CASCADE, related_name='trackings')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='discipline_tasks')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    hold_reason = models.TextField(blank=True, null=True)
    hold_date = models.DateField(null=True, blank=True)
    expected_resume_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ['project', 'discipline_item']


# 5. Tasks & Supervision Tracking

class Task(TimeStampedModel):
    class Status(models.TextChoices):
        UNCHARTED = 'UNCHARTED', 'Uncharted'
        UNDER_STUDY = 'UNDER_STUDY', 'Under Study'
        COMMENT = 'COMMENT', 'Comment'
        ON_GOING = 'ON_GOING', 'On Going'
        COMPLETED = 'COMPLETED', 'Completed'
        APPROVED = 'APPROVED', 'Approved'
        ON_HOLD = 'ON_HOLD', 'On Hold'

    class TaskType(models.TextChoices):
        MAIN_DESIGN = 'MAIN_DESIGN', 'Main Design'
        CHANGE_ORDER = 'CHANGE_ORDER', 'Change Order'
        INTERNAL_REVIEW = 'INTERNAL_REVIEW', 'Internal Review'
        SUPERVISION = 'SUPERVISION', 'Supervision'
    class WorkType(models.TextChoices):
        DESIGN = 'DESIGN', 'Design'
        DESIGN_REVIEW = 'DESIGN_REVIEW', 'Design Review'
        DRAFTING = 'DRAFTING', 'Drafting'
        CALCULATION = 'CALCULATION', 'Calculation'
        REPORT = 'REPORT', 'Report'
        RENDERING_3D = 'RENDERING_3D', '3D Rendering'
        PRESENTATION = 'PRESENTATION', 'Presentation'
        PRINTING = 'PRINTING', 'Printing'
        FILE_OPENING = 'FILE_OPENING', 'File Opening'
        COORDINATED_PACKAGE = 'COORDINATED_PACKAGE', 'Coordinated Package'
    work_type = models.CharField(
        max_length=20,
        choices=WorkType.choices,
        blank=True, null=True,
        verbose_name="Work Type"
    )
    task_type = models.CharField(max_length=20, choices=TaskType.choices, default=TaskType.MAIN_DESIGN)
    internal_review_stage = models.ForeignKey(InternalReviewStage, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    discipline_tracking = models.ForeignKey(DisciplineTracking, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='tasks')

    description = models.TextField(blank=True, null=True)

    discipline = models.ForeignKey(DisciplineItem,on_delete=models.SET_NULL,null=True,blank=True)

    stage = models.CharField(max_length=20,choices=MasterDiscipline.Stage.choices,null=True,blank=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    priority = models.CharField(max_length=20, choices=Project.PriorityStatus.choices, default=Project.PriorityStatus.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNCHARTED)
    progress_percentage = models.IntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    duration_days = models.IntegerField(default=0)
    end_date = models.DateField(null=True, blank=True)
    status_date = models.DateField(null=True, blank=True)
    status_changed_at = models.DateTimeField(null=True, blank=True)
    approval_date = models.DateField(null=True, blank=True)
    is_on_hold = models.BooleanField(default=False)
    hold_reason = models.TextField(blank=True, null=True)
    hold_date = models.DateField(null=True, blank=True)
    expected_resume_date = models.DateField(null=True, blank=True)
    # ═══ حسابات المدد الآلية (KPIs عادلة) ═══
    @property
    def total_duration_days(self):
        """الإجمالي = الاعتماد (أو الآن) − الإنشاء"""
        if not self.start_date:
            return 0
        end = self.approval_date or self.end_date or timezone.now().date()
        return max((end - self.start_date).days, 0)

    @property
    def total_hold_days(self):
        """مجموع أيام كل فترات الإيقاف المؤقت"""
        return sum(p.duration_days for p in self.hold_periods.all())

    @property
    def net_duration_days(self):
        """المدة الفعلية للـ KPI = الإجمالي − الهولد"""
        return max(self.total_duration_days - self.total_hold_days, 0)


class TaskHoldPeriod(TimeStampedModel):
    """فترة إيقاف مؤقت واحدة (بداية + استئناف) — تُسجَّل وتُغلق آليًا."""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='hold_periods')
    hold_start = models.DateTimeField(default=timezone.now)
    release_at = models.DateTimeField(null=True, blank=True)

    @property
    def duration_days(self):
        end = self.release_at or timezone.now()
        return max((end - self.hold_start).days, 0)


@receiver(pre_save, sender=Task)
def automate_task_timing(sender, instance, **kwargs):
    """أتمتة كاملة: بدء / هولد / استئناف / اعتماد / مدة صافية — بدون تدخل يدوي."""
    now = timezone.now()

    # ١) تاريخ البدء = لحظة الضغط على زر إنشاء المهمة
    if not instance.pk:
        instance.start_date = now.date()
        return

    old = Task.objects.filter(pk=instance.pk).first()
    if not old:
        return

    # ٢) دخول الهولد → فتح فترة جديدة تلقائيًا
    if instance.status == Task.Status.ON_HOLD and old.status != Task.Status.ON_HOLD:
        instance.is_on_hold = True
        instance.hold_date = instance.hold_date or now.date()
        TaskHoldPeriod.objects.create(task=instance, hold_start=now)

    # ٣) الخروج من الهولد (Release) → إغلاق الفترة تلقائيًا
    elif old.status == Task.Status.ON_HOLD and instance.status != Task.Status.ON_HOLD:
        instance.is_on_hold = False
        instance.hold_periods.filter(release_at__isnull=True).update(release_at=now)

    # ٤) الاعتماد → تاريخ الانتهاء + المدة الصافية تُحفظ آليًا
    if instance.status == Task.Status.APPROVED and old.status != Task.Status.APPROVED:
        instance.approval_date = now.date()
        instance.end_date = now.date()
        instance.hold_periods.filter(release_at__isnull=True).update(release_at=now)
        instance.duration_days = instance.net_duration_days   # ✅ الـ KPI يستبعد أيام الهولد
class AssignmentHistory(TimeStampedModel):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='assignment_history')
    old_engineer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='past_assignments')
    new_engineer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='new_assignments')
    reason_for_change = models.TextField(blank=True, null=True)
    days_worked = models.IntegerField(default=0)
    status_at_handover = models.CharField(max_length=50)


# NEW: Replacement Request (طلبات الاستبدال المنفصلة)

class ReplacementRequest(TimeStampedModel):
    class Status(models.TextChoices):
      PENDING = 'PENDING', 'Pending'
      ENGINEER_RESPONDED = 'ENGINEER_RESPONDED', 'Engineer Responded'
      APPROVED = 'APPROVED', 'Approved'
      REJECTED = 'REJECTED', 'Rejected'

    engineer_response = models.CharField(max_length=20, choices=[('APPROVE','Approve'),('DECLINE','Decline')], blank=True, null=True)
    engineer_response_reason = models.TextField(blank=True, null=True)
    engineer_responded_at = models.DateTimeField(null=True, blank=True)

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='replacement_requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requested_replacements')
    suggested_engineer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='suggested_replacements')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reason = models.TextField()
    response_reason = models.TextField(blank=True, null=True)
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='responded_replacements')
    responded_at = models.DateTimeField(null=True, blank=True)


# NEW: Staff KPI (إحصائيات الموظفين)

class StaffKPI(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kpis')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='staff_kpis')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='kpis')
    days_worked = models.IntegerField(default=0)
    status_at_handover = models.CharField(max_length=50)
    handover_date = models.DateField(null=True, blank=True)


class SupervisionTeamAssignment(TimeStampedModel):
    # ✅ جديد: قائمة Roles معتمدة لقسم الإشراف
    class Role(models.TextChoices):
        PM = 'PM', 'PM'
        SITE_ENGINEER = 'SITE_ENGINEER', 'Site Engineer'
        COORDINATOR = 'COORDINATOR', 'Coordinator'
        INSPECTOR = 'INSPECTOR', 'Inspector'
        SENIOR_ENGINEER = 'SENIOR_ENGINEER', 'Senior Engineer'
        # ✅ للاحتفاظ بالتوافق مع البيانات القديمة
        ENGINEER = 'ENGINEER', 'Engineer'
        SUP_MGR = 'SUP_MGR', 'Supervision Manager'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='supervision_team')
    engineer = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # ✅ محدث: role الآن مقيد بـ choices + يقبل القيم القديمة (blank=True للبيانات القديمة)
    role = models.CharField(
        max_length=50,
        choices=Role.choices,
        default=Role.PM,
        blank=True
    )
    department = models.CharField(max_length=50, blank=True, null=True)
    is_pm = models.BooleanField(default=False)
    days_of_week = models.JSONField(help_text="e.g. ['Sun', 'Tue']")
    time_from = models.TimeField(null=True, blank=True)
    time_to = models.TimeField(null=True, blank=True)
    contract_percentage = models.FloatField(default=0.0)
    actual_percentage = models.FloatField(default=0.0)
    assignment_started_at = models.DateField(null=True, blank=True)
    assignment_ended_at = models.DateField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # ✅ أتمتة: لو الـ Role = PM، اجعل is_pm = True تلقائياً
        if self.role == self.Role.PM:
            self.is_pm = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.engineer.get_full_name()} - {self.get_role_display()} @ {self.project.project_no}"


class SupervisionReplacementRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
    assignment = models.ForeignKey(SupervisionTeamAssignment, on_delete=models.CASCADE, related_name='replacement_requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='supervision_requested_replacements')
    suggested_engineer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='supervision_suggested_replacements')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reason = models.TextField()
    response_reason = models.TextField(blank=True, null=True)
    responded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='supervision_responded_replacements')
    responded_at = models.DateTimeField(null=True, blank=True)

class SupervisionAssignmentHistory(TimeStampedModel):
    assignment = models.ForeignKey(SupervisionTeamAssignment, on_delete=models.CASCADE, related_name='history')
    old_engineer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='supervision_past_assignments')
    new_engineer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='supervision_new_assignments')
    assignment_started_at = models.DateField(null=True, blank=True)
    assignment_ended_at = models.DateField(null=True, blank=True)
    progress_at_handover = models.FloatField(default=0.0)
    reason_for_change = models.TextField(blank=True, null=True)

class ActionRequest(TimeStampedModel):
    class Status(models.TextChoices):
        STARTED = 'STARTED', 'Started'
        ON_GOING = 'ON_GOING', 'On Going'
        ON_HOLD = 'ON_HOLD', 'On Hold'
        COMPLETED = 'COMPLETED', 'Completed'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='action_requests')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_requests')
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_requests')
    description = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.STARTED)
    progress_percentage = models.IntegerField(default=0)
    hold_reason = models.TextField(blank=True, null=True)


# 6. Finance Module

class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        ISSUED = 'ISSUED', 'Issued'
        PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
        PAID = 'PAID', 'Paid'
        OVERDUE = 'OVERDUE', 'Overdue'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class MilestoneType(models.TextChoices):
        DOWN_PAYMENT = 'DOWN_PAYMENT', 'Down Payment / Advanced'
        DC1 = 'DC1', 'DC1 Payment'
        DC2 = 'DC2', 'DC2 Payment'
        TENDERING = 'TENDERING', 'Tendering Payment'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='invoices')
    title = models.CharField(max_length=100)
    milestone_type = models.CharField(max_length=20, choices=MilestoneType.choices, default=MilestoneType.DOWN_PAYMENT)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

class InvoicePayment(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(auto_now_add=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)


# NEW: Supervision Financial Module (فواتير الإشراف المنفصلة)

class SupervisionInvoice(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        ISSUED = 'ISSUED', 'Issued'
        PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
        PAID = 'PAID', 'Paid'
        OVERDUE = 'OVERDUE', 'Overdue'
        CANCELLED = 'CANCELLED', 'Cancelled'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='supervision_invoices')
    month_name = models.CharField(max_length=50)
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    payment_date = models.DateField(null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)


# 7. Audit, Comm & Files

class AuditLog(TimeStampedModel):
    class ActionType(models.TextChoices):
        PROJECT_CREATED = 'PROJECT_CREATED', 'Project Created'
        PROJECT_UPDATED = 'PROJECT_UPDATED', 'Project Updated'
        REVISION_CREATED = 'REVISION_CREATED', 'Revision Created'
        TASK_CREATED = 'TASK_CREATED', 'Task Created'
        TASK_ASSIGNED = 'TASK_ASSIGNED', 'Task Assigned'
        TASK_SELF_ASSIGNED = 'TASK_SELF_ASSIGNED', 'Task Self Assigned'
        TASK_STATUS_CHANGED = 'TASK_STATUS_CHANGED', 'Task Status Changed'
        TASK_COMPLETED = 'TASK_COMPLETED', 'Task Completed'
        TASK_APPROVED = 'TASK_APPROVED', 'Task Approved'
        ON_HOLD_SET = 'ON_HOLD_SET', 'On Hold Set'
        ON_HOLD_RESUMED = 'ON_HOLD_RESUMED', 'On Hold Resumed'
        REASSIGNMENT_REQUESTED = 'REASSIGNMENT_REQUESTED', 'Reassignment Requested'
        REASSIGNMENT_APPROVED = 'REASSIGNMENT_APPROVED', 'Reassignment Approved'
        INVOICE_ADDED = 'INVOICE_ADDED', 'Invoice Added'
        INVOICE_STATUS_CHANGED = 'INVOICE_STATUS_CHANGED', 'Invoice Status Changed'
        STAGE_ACTUAL_DATE_UPDATED = 'STAGE_ACTUAL_DATE_UPDATED', 'Stage Actual Date Updated'
        DISCIPLINE_STATUS_CHANGED = 'DISCIPLINE_STATUS_CHANGED', 'Discipline Status Changed'
        NOTE_ADDED = 'NOTE_ADDED', 'Note Added'
        PRIORITY_CHANGED = 'PRIORITY_CHANGED', 'Priority Changed'

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action_type = models.CharField(max_length=50, choices=ActionType.choices)
    details = models.TextField(blank=True, null=True)
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True)
class ChatRoom(TimeStampedModel):
    class RoomType(models.TextChoices):
        PROJECT = 'PROJECT', 'Project'
        DIRECT  = 'DIRECT',  'Direct Message'
        GENERAL = 'GENERAL', 'General / Broadcast'
    class Audience(models.TextChoices):
        ALL = 'ALL', 'Everyone'
        DESIGN = 'DESIGN', 'Design Team'
        SUPERVISION = 'SUPERVISION', 'Supervision Team'

    audience = models.CharField(
        max_length=20, choices=Audience.choices, default=Audience.ALL, blank=True
    )
    room_type = models.CharField(
        max_length=10, choices=RoomType.choices, default=RoomType.PROJECT
    )
    project = models.ForeignKey(           # كان OneToOne إجباري → صار اختياريًا
        Project, on_delete=models.CASCADE,
        null=True, blank=True, related_name='chat_rooms'
    )
    name = models.CharField(max_length=255, blank=True, null=True)
    participants = models.ManyToManyField(   # للـ DIRECT: الطرفان
        User, related_name='chat_rooms', blank=True
    )

    def __str__(self):
        return f"[{self.room_type}] {self.name or self.project or self.pk}"
class ChatMessage(TimeStampedModel):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    message = models.TextField()
    attachment = models.FileField(upload_to='chat_attachments/', blank=True, null=True)
    mentions = models.ManyToManyField(User, related_name='mentioned_in_chats', blank=True)
    read_by = models.ManyToManyField(User, related_name='read_chat_messages', blank=True)

class Notification(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_notifications')
    notification_type = models.CharField(max_length=50) 
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    related_link = models.URLField(blank=True, null=True)


class ProjectNote(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='notes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    mentions = models.ManyToManyField(
        User,
        related_name='mentioned_in_notes',
        blank=True
    )
    is_pinned = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_pinned', '-created_at']


class ProjectFile(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='files')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    file = models.FileField(upload_to='project_files/')
    file_type = models.CharField(max_length=50) 

class ExternalLog(TimeStampedModel):
    class LogSubType(models.TextChoices):
          PENDING_DOCUMENTS = 'PENDING_DOCUMENTS', 'Pending Documents Logs'
          CRITICAL = 'CRITICAL', 'Critical Logs'
          ATTENDANCE = 'ATTENDANCE', 'Attendance / Leaves'   # ← مُضاف
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='external_logs')
    log_type = models.CharField(max_length=50)
    sub_type = models.CharField(
        max_length=30,
        choices=LogSubType.choices,
        default=LogSubType.PENDING_DOCUMENTS
    )
    url = models.URLField()
    description = models.TextField(blank=True, null=True)

    def clean(self):
        # وداخل clean():
        valid_types = [self.LogSubType.PENDING_DOCUMENTS, self.LogSubType.CRITICAL, self.LogSubType.ATTENDANCE]

        if self.sub_type not in valid_types:
            raise ValidationError(f"Invalid sub_type. Must be one of: {valid_types}")
 
class PaymentSchedule(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='payment_schedules')
    installment_number = models.IntegerField()  # رقم الدفعة
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('INVOICED', 'Invoiced'),
        ('PAID', 'Paid'),
    ], default='PENDING')
    
    class Meta:
        ordering = ['installment_number']
        unique_together = ['project', 'installment_number'] 


class InvoiceFile(TimeStampedModel):
    """ملفات الفواتير (PDF)"""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='invoice_files/')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    file_type = models.CharField(max_length=20, default='PDF')




class LifecycleHistory(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='lifecycle_history')
    stage = models.ForeignKey(ProjectLifecycleStage, on_delete=models.CASCADE)
    action = models.CharField(max_length=50, choices=[
        ('STARTED', 'Stage Started'),
        ('COMPLETED', 'Stage Completed'),
        ('APPROVED', 'Stage Approved'),
        ('REOPENED', 'Stage Reopened'),
    ])
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']


# في آخر models.py (بعد كل الـ classes)
def sync_lifecycle_from_disciplines(project):
    """
    يزامن مراحل دورة الحياة (CONCEPT/DC1/DC2/TENDER) مع حالة الـ disciplines الفعلية،
    ويصلّح المراحل التعاقدية (OFFER/CONTRACT_SUBMITTED/CONTRACT_SIGNED)،
    ويقفل المشروع لو كل المراحل اتنجرت.
    يُستدعى تلقائيًا بعد كل تحديث DisciplineTracking، ومن سكربت الترحيل.
    """
    from django.utils import timezone

    # ١) كل مرحلة تصميم تاخد ACHIEVED لو كل تخصصاتها خلصت
    for stage_name in ['CONCEPT', 'DC1', 'DC2', 'TENDER']:
        trackings = DisciplineTracking.objects.filter(
            project=project, discipline_item__stage=stage_name
        )
        if not trackings.exists():
            continue
        lc = project.lifecycle_stages.filter(stage_name=stage_name).first()
        if not lc:
            continue
        all_done = trackings.exclude(status__in=['COMPLETED', 'APPROVED']).count() == 0
        if all_done and lc.status != 'ACHIEVED':
            lc.status = 'ACHIEVED'
            if not lc.actual_date:
                lc.actual_date = timezone.now().date()
            lc.save(update_fields=['status', 'actual_date'])

    # ٢) لو أي مرحلة تصميم اتنجرت، فالمراحل التعاقدية قبلها تمت حتمًا
    design_done = project.lifecycle_stages.filter(
        stage_name__in=['CONCEPT', 'DC1', 'DC2', 'TENDER'], status='ACHIEVED'
    ).exists()
    if design_done:
        project.lifecycle_stages.filter(
            stage_name__in=['OFFER', 'CONTRACT_SUBMITTED', 'CONTRACT_SIGNED'],
            status='UPCOMING',
        ).update(status='ACHIEVED', actual_date=timezone.now().date())

    # ٣) إغلاق تلقائي لو كل المراحل اتنجرت
    if (project.lifecycle_stages.exists()
            and not project.lifecycle_stages.exclude(status='ACHIEVED').exists()
            and project.is_active):
        project.is_active = False
        project.save(update_fields=['is_active'])



@receiver(post_save, sender=Task)
def sync_discipline_tracking_from_task(sender, instance, created, **kwargs):
    """
    كل ما Task تتغير (أو تتعمل جديدة)، زامن DisciplineTracking تلقائياً
    وشغّل المحرك عشان دورة الحياة تتقدم.
    """
    if instance.discipline:
        tracking, _ = DisciplineTracking.objects.get_or_create(
            project=instance.project,
            discipline_item=instance.discipline,
            defaults={
                'status': 'PENDING',
                'assigned_to': instance.assigned_to
            }
        )
        
        # زامن الحالة من Task → DisciplineTracking
        if instance.status in ['COMPLETED', 'APPROVED']:
            tracking.status = 'APPROVED'
            if not tracking.end_date:
                tracking.end_date = timezone.now().date()
        elif instance.status == 'ON_GOING':
            tracking.status = 'IN_PROGRESS'
            if not tracking.start_date:
                tracking.start_date = timezone.now().date()
        elif instance.status == 'ON_HOLD':
            tracking.status = 'ON_HOLD'
        
        if instance.assigned_to and not tracking.assigned_to:
            tracking.assigned_to = instance.assigned_to
        
        tracking.save()
        
        # ⭐ تشغيل المحرك الموحد
        instance.project.evaluate_and_advance_lifecycle(actor=instance.assigned_to)






def advance_internal_review_stage(project, stage, actor=None):

    from django.utils import timezone
    now = timezone.now()
    changed = False

    tasks = stage.tasks.all()
    if not tasks.exists():
        return False
    # لم تُنجز كل مهام المرحلة بعد → لا تفعل شيئاً
    if tasks.exclude(status__in=['COMPLETED', 'APPROVED']).exists():
        return False

    # ١) اعتماد المرحلة الحالية
    if stage.status != InternalReviewStage.Status.APPROVED:
        stage.status = InternalReviewStage.Status.APPROVED
        stage.updated_at = now
        stage.save(update_fields=['status', 'updated_at'])
        AuditLog.objects.create(
            project=project, user=actor,
            action_type=AuditLog.ActionType.TASK_APPROVED,
            details=f"Internal review stage '{stage.get_stage_name_display()}' auto-APPROVED (all its tasks done).",
        )
        changed = True

    # ٢) تفعيل المرحلة التالية
    nxt = InternalReviewStage.objects.filter(
        project=project, sequence_order=stage.sequence_order + 1
    ).first()
    if nxt and nxt.status == InternalReviewStage.Status.PENDING:
        nxt.status = InternalReviewStage.Status.UNDER_REVIEW
        nxt.updated_at = now
        nxt.save(update_fields=['status', 'updated_at'])
        # إشعار للمعيَّنين + مدير الإشراف/PM
        targets = set(project.internal_review_assignees.values_list('id', flat=True))
        targets |= set(
            User.objects.filter(role__in=['SUP_MGR', 'PM'])
            .values_list('id', flat=True)
        )
        targets.discard(actor.id if actor else None)
        for uid in targets:
            Notification.objects.create(
                user_id=uid, sender=actor,
                notification_type='INTERNAL_REVIEW_STAGE_ADVANCED',
                title=f"مرحلة مراجعة جديدة: {nxt.get_stage_name_display()}",
                message=f"اعتمدت مرحلة «{stage.get_stage_name_display()}» في {project.project_no}، وبدأت «{nxt.get_stage_name_display()}».",
                related_link=f'/projects/{project.id}',
            )
        changed = True

    # ٣) اكتمال المراجعة كلها ⇒ «جاهز للموقع»
    if not project.internal_reviews.exclude(status=InternalReviewStage.Status.APPROVED).exists():
        targets = set(User.objects.filter(role__in=['SUP_MGR', 'PM']).values_list('id', flat=True))
        if project.internal_review_requested_by_id:
            targets.add(project.internal_review_requested_by_id)
        targets.discard(actor.id if actor else None)
        for uid in targets:
            Notification.objects.create(
                user_id=uid, sender=actor,
                notification_type='INTERNAL_REVIEW_COMPLETED',
                title='التصميم جاهز للموقع',
                message=f'كل مراحل المراجعة الداخلية للمشروع {project.project_no} اعتمدت.',
                related_link=f'/projects/{project.id}',
            )
    return changed



 