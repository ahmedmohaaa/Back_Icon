"""
change_order_service.py  —  Step 2 (Service layer فقط)
=====================================================
منطق الـ Change Order / Revision / Sub-Project كمصدر حقيقة واحد.

نطاق هذا الملف (وما لا يفعله عن قصد):
- يحتوي: next_revision_number, create_change_order, confirm_change_order,
  reject_change_order, cancel_change_order, assert_can_create_tasks.
- يستخدم: transaction.atomic() + select_for_update() لمنع السباقات،
  وUniqueConstraint المشروط (من Step 1) كخط دفاع أخير.
- لا يُنشئ مراحل دورة الحياة (lifecycle stages) ولا سجلات التتبع
  (discipline trackings): هذه مسؤولية طبقة الـ view في Step 3، لتجنّب
  تكرار المنطق الموجود في ProjectCreateAPIView._create_lifecycle_stages /
  _create_discipline_trackings (قاعدة: لا تكرّر Business Logic).
- لا يُرسل أي Notification، ولا يكتب AuditLog، ولا يستدعي أي Serializer/View.
- لا يعدّل الـ Parent Project عند إنشاء Change Order أبدًا.

ملاحظة استدعاء: الدوال التي تمرّر lock=True (next_revision_number ضمنياً،
وكل دوال الانتقال) يجب أن تُنفَّذ داخل transaction.atomic()؛ وإلا يرفع
Django خطأ TransactionManagementError عند select_for_update — وهذا مقصود
لضمان الأمان. دالة create_change_order تفتح atomic بنفسها.
"""
import re

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from erp.models import Project


# ═══════════════════════════════════════════════════════════════
#  ثوابت داخلية
# ═══════════════════════════════════════════════════════════════

# النمط المقبول لرقم الـ Revision: البادئة "Rev" (بأي حالة) + أرقام،
# مع السماح بمسافات اختيارية بينهما. يغطي الصيغ الموجودة فعلياً
# (Rev1, rev2, REV 10 ...) ويرفض أي صيغة غير متوقعة.
_REV_RE = re.compile(r'^rev\s*(\d+)$', re.IGNORECASE)

# الحقول الفيزيائية/السياقية الموروثة من الـ Parent عند إنشاء CO.
# (تطابق ما ورّثه ProjectChangeOrderAPIView القديم + location/building_type
#  كتحسين معقول؛ أي منها يمكن تجاوزه عبر data في create_change_order.)
_INHERITED_FIELDS = ('scope', 'client', 'contractor', 'location', 'building_type')


# ═══════════════════════════════════════════════════════════════
#  أدوات داخلية
# ═══════════════════════════════════════════════════════════════

def _is_blank(value):
    """True إن كانت القيمة مفقودة فعلياً (None / فارغة بعد القص)."""
    return value is None or str(value).strip() == ''


def _assert_change_order(sub):
    """يتحقق أن السجل هو Change Order فعلاً (له Parent)."""
    if sub.parent_project_id is None:
        raise ValidationError(
            f"Project id={sub.id} is an original project, not a Change Order."
        )


# ═══════════════════════════════════════════════════════════════
#  1) next_revision_number
# ═══════════════════════════════════════════════════════════════

def next_revision_number(parent, *, preferred=None, lock=True):
    """
    يحسب رقم الـ Revision التالي الآمن تحت parent، أو يتحقق من رقم مفضَّل.

    القواعد (مطابقة للمتطلبات ١–٧):
    ١) يقرأ كل الـ Revisions التابعة لنفس الـ Parent (الأبناء المباشرون).
    ٢) يستخرج الرقم الحقيقي من كل قيمة عبر النمط _REV_RE.
    ٣) يدعم الصيغة الحالية (Rev1/Rev2/Rev10) بدون تغيير نوع الحقل.
    ٤) لا يعتمد على sub_projects.count() إطلاقاً.
    ٥) Rev1,Rev2,Rev10  ⇒  النتيجة Rev11 (max + 1).
    ٦) أي قيمة *موجودة* بصيغة غير قابلة للتحليل ⇒ ValidationError واضح
       (لا تخمين). القيم الفارغة/null تُتجاهل بأمان (غياب قيمة ≠ صيغة سيئة).
    ٧) لا يُعيد استخدام رقم سابق حتى لو كان ملغياً/مرفوضاً، لأن الحساب
       يأخذ max على *كل* الأبناء بغض النظر عن change_order_status.

    المعامل preferred:
    - إن مُرّر: يُتحقق من نمطه، ومن عدم تكراره (مقارنة case-insensitive
      بعد القص)؛ إن كان صالحاً يُعاد كما هو. إن مكرر أو سيء النمط ⇒ خطأ.
    - إن لم يُمرَّر: يُعاد f"Rev{max+1}".

    lock=True ⇒ select_for_update على صفوف الأبناء (يتطلب atomic خارجي).
    """
    children = Project.objects.filter(parent_project_id=parent.id)
    if lock:
        # يقفل صفوف الأبناء الموجودة؛ الـ UniqueConstraint يحمي من الإدراج المتزامن.
        children = children.select_for_update()

    pref_norm = None if _is_blank(preferred) else str(preferred).strip()
    if pref_norm is not None and not _REV_RE.match(pref_norm):
        raise ValidationError(
            f"Preferred revision number '{preferred}' has an unexpected format "
            f"(expected e.g. 'Rev1')."
        )

    max_num = 0
    for sub in children:
        rn = sub.revision_number
        if _is_blank(rn):
            continue  # غياب قيمة ⇒ تجاهل بأمان (لا يُساهم برقم ولا يُخطئ)
        rn_str = str(rn).strip()
        m = _REV_RE.match(rn_str)
        if not m:
            raise ValidationError(
                f"Existing revision number '{rn}' on sub-project id={sub.id} "
                f"has an unexpected format and cannot be parsed safely. "
                f"Resolve it before creating a new revision."
            )
        # منع التكرار للرقم المفضَّل (مقارنة موحّدة)
        if pref_norm is not None and rn_str.lower() == pref_norm.lower():
            raise ValidationError(
                f"Revision '{preferred}' already exists for parent "
                f"project '{parent.project_no}'."
            )
        n = int(m.group(1))
        if n > max_num:
            max_num = n

    return pref_norm if pref_norm is not None else f"Rev{max_num + 1}"


# ═══════════════════════════════════════════════════════════════
#  2) create_change_order
# ═══════════════════════════════════════════════════════════════

def create_change_order(parent_id, data, *, actor=None):
    """
    يُنشئ سجل Change Order (Sub-Project) تحت Parent، ذرياً وبأمان.

    - Case 1 (Parent مغلق / is_active=False) ⇒ الحالة الابتدائية CONFIRMED
      (الـ CO جاهز للعمل مباشرة، بلا بوابة تأكيد — مطابق للوثيقة).
    - Case 2 (Parent نشط / is_active=True)  ⇒ الحالة الابتدائية
      PENDING_CONFIRMATION (يحتاج confirm_change_order قبل أي tasks).
    - يورث الحقول الفيزيائية/السياقية من Parent (_INHERITED_FIELDS)،
      مع السماح لـ data بتجاوز name / project_no / الحقول الموروثة.
    - يولّد revision_number عبر next_revision_number إن لم يُمرَّر،
      وإلا يتحقق منه. يمنع التكرار (فحص + UniqueConstraint).
    - يقفل الـ Parent (select_for_update)؛ لا يعدّله إطلاقاً.
    - لا يُنشئ lifecycle stages / discipline trackings (مسؤولية الـ view).
    - لا يُرسل إشعارات ولا يكتب تدقيقاً.

    يُرجع كائن الـ Sub-Project المُنشأ.
    """
    COStatus = Project.ChangeOrderStatus
    provided = data.get('revision_number')

    try:
        with transaction.atomic():
            # قفل صف الـ Parent (يمنع سباق الإنشاء تحت نفس الأب).
            parent = Project.objects.select_for_update().get(id=parent_id)

            # رقم الـ Revision الآمن (يقفل الأبناء + يتحقق من الصيغ/التكرار).
            rev = next_revision_number(parent, preferred=provided, lock=True)

            # الحالة الابتدائية حسب حالة الـ Parent (Case 1 / Case 2).
            initial_status = (
                COStatus.CONFIRMED
                if not parent.is_active
                else COStatus.PENDING_CONFIRMATION
            )

            # تجميع الحقول الموروثة مع التجاوزات من data.
            inherited = {
                f: getattr(parent, f)
                for f in _INHERITED_FIELDS
                if data.get(f) is None  # لا نطغى على تجاوز صريح
            }
            # التجاوزات الصريحة للحقول الموروثة (إن وُجدت في data).
            for f in _INHERITED_FIELDS:
                if data.get(f) is not None:
                    inherited[f] = data[f]

            sub = Project.objects.create(
                parent_project=parent,
                revision_number=rev,
                change_order_status=initial_status,
                name=data.get('name') or f"{parent.name} ({rev})",
                project_no=data.get('project_no') or f"{parent.project_no}-{rev}",
                new_application_no=data.get('new_application_no'),
                revision_start_date=data.get('revision_start_date'),
                change_order_reason=data.get('change_order_reason'),
                is_active=True,
                **inherited,
            )
            # ملاحظة: لا تعديل على parent هنا إطلاقاً.
    except IntegrityError:
        # خط الدفاع الأخير (سباق إدراج نادر أو تعارض project_no/revision).
        raise ValidationError(
            "Could not create the Change Order: a revision or project number "
            "conflict occurred (possibly concurrent creation). Retry, or change "
            "the revision/project number."
        )

    return sub


# ═══════════════════════════════════════════════════════════════
#  3) confirm_change_order
# ═══════════════════════════════════════════════════════════════

def confirm_change_order(sub_id, *, actor=None):
    """
    PENDING_CONFIRMATION  ⇒  CONFIRMED   (Case 2: بوابة مدير التصميم).
    بعد هذه النقطة فقط يُسمح بإنشاء مهام الـ CO (assert_can_create_tasks).
    """
    COStatus = Project.ChangeOrderStatus
    with transaction.atomic():
        sub = Project.objects.select_for_update().get(id=sub_id)
        _assert_change_order(sub)
        if sub.change_order_status != COStatus.PENDING_CONFIRMATION:
            raise ValidationError(
                f"Cannot confirm: current status is '{sub.change_order_status}', "
                f"expected 'PENDING_CONFIRMATION'."
            )
        sub.change_order_status = COStatus.CONFIRMED
        sub.save(update_fields=['change_order_status'])
    return sub


# ═══════════════════════════════════════════════════════════════
#  4) reject_change_order
# ═══════════════════════════════════════════════════════════════

def reject_change_order(sub_id, *, actor=None):
    """
    PENDING_CONFIRMATION  ⇒  REJECTED  (+ is_active=False).
    الـ CO المرفوض لا تُنشأ له أعمال؛ يُغلق ليختفي من النشط.
    ملاحظة: سبب الرفض (reason) لا يُخزَّن في النموذج هنا (لا حقل مخصّص)؛
    يُتوقع تمريره لطبقة الـ view لتسجيله في AuditLog (Step 3).
    """
    COStatus = Project.ChangeOrderStatus
    with transaction.atomic():
        sub = Project.objects.select_for_update().get(id=sub_id)
        _assert_change_order(sub)
        if sub.change_order_status != COStatus.PENDING_CONFIRMATION:
            raise ValidationError(
                f"Cannot reject: current status is '{sub.change_order_status}', "
                f"expected 'PENDING_CONFIRMATION'."
            )
        sub.change_order_status = COStatus.REJECTED
        sub.is_active = False
        sub.save(update_fields=['change_order_status', 'is_active'])
    return sub


# ═══════════════════════════════════════════════════════════════
#  5) cancel_change_order
# ═══════════════════════════════════════════════════════════════

def cancel_change_order(sub_id, *, actor=None):
    """
    {PENDING_CONFIRMATION, CONFIRMED}  ⇒  CANCELLED  (+ is_active=False).
    لا يمكن إلغاء CO مرفوض أو ملغى مسبقاً.
    """
    COStatus = Project.ChangeOrderStatus
    cancellable = {COStatus.PENDING_CONFIRMATION, COStatus.CONFIRMED}
    with transaction.atomic():
        sub = Project.objects.select_for_update().get(id=sub_id)
        _assert_change_order(sub)
        if sub.change_order_status not in cancellable:
            raise ValidationError(
                f"Cannot cancel: current status is '{sub.change_order_status}'. "
                f"Only PENDING_CONFIRMATION or CONFIRMED can be cancelled."
            )
        sub.change_order_status = COStatus.CANCELLED
        sub.is_active = False
        sub.save(update_fields=['change_order_status', 'is_active'])
    return sub


# ═══════════════════════════════════════════════════════════════
#  6) assert_can_create_tasks
# ═══════════════════════════════════════════════════════════════

def assert_can_create_tasks(sub):
    """
    حارس إنشاء مهام الـ CO: يرفع ValidationError إن لم يُسمح.
    - إن كان السجل مشروعاً أصلياً (change_order_status is None) ⇒ لا يمنع
      (الحارس لا ينطبق؛ تُستخدم قواعد المهام العادية).
    - إن كان CO ⇒ يسمح فقط عندما change_order_status == CONFIRMED.
      هذا يمنع إنشاء مهام قبل التأكيد (Case 2) وبعد الرفض/الإلغاء.
    قراءة فقط؛ لا تعديل. آمن للاستدعاء داخل atomic الخاص بإنشاء المهمة.
    """
    COStatus = Project.ChangeOrderStatus
    if sub.change_order_status is None:
        return  # مشروع أصلي — لا قيد من هذا الحارس
    if sub.change_order_status != COStatus.CONFIRMED:
        raise ValidationError(
            f"Cannot create tasks: Change Order status is "
            f"'{sub.change_order_status}'. Tasks are allowed only after the "
            f"Change Order is CONFIRMED."
        )