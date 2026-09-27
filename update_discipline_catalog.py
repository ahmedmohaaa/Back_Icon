from django.db import transaction
from erp.models import DisciplineItem, DisciplineTracking, Project
# لو اسم التطبيق عندك مختلف عن erp غيّر السطر السابق فقط

# ═══ الكتالوج الكامل المطلوب (هو فقط اللي هيفضل موجود) ═══
DESIRED_CATALOG = {
    # ── Concept Design ──
    ('CONCEPT', 'ARCH'): [
        'Sketch',
        'Perspective',
    ],
    # ── Tender Documents ──
    ('TENDER', 'ARCH'): [
        'BOQ',
        'Specifications',
        'Conditions of contracts',
    ],
    # ── Architecture — DC1 ──
    ('DC1', 'ARCH'): [
        'Architecture',
        'Life Safety Plan / LSP',
        'Roads / Ashghal',
        'MOTC',
        'Civil Aviation / CAV',
        'Qatar Rail',
        'Infrastructure Planning',
        'Urban Planning',
        'Higher Education / MOEHE',
        'Technical Affairs / Private Eng. Office',
        'Ministry of Environment & Climate Change / MECC',
        'Ministry of Industry & Mineral Resources / MIMR',
        'Qatar Tourism / QTour',
        'Public Health / MOPH',
        'General Cleanliness Project',
        'Livestock Department',
        'IFC matching coordination',
    ],
    # ── Electrical Services — DC1 ──
    ('DC1', 'ELEC'): ['KAHRAMAA EL'],
    # ── Mechanical Services — DC1 ──
    ('DC1', 'MECH'): ['KAHRAMAA WS', 'Drainage'],
    # ── Architecture — DC2 ──
    ('DC2', 'ARCH'): ['Qatar Rail', 'MOTC'],
    # ── Electrical Services — DC2 ──
    ('DC2', 'ELEC'): [
        'KAHRAMAA EL',
        'Telecom / Ooredoo',
        'Fire Alarm / MOI',
        'CCTV / Security / Client Specialist',
        'Earthing',
        'Lightning Protection',
        'Public Address',
        'Access Control',
    ],
    # ── Mechanical Services — DC2 ──
    ('DC2', 'MECH'): [
        'Water Supply',
        'Drainage (Storm, Sewerage)',
        'Fire Fighting / MOI',
        'Ventilation / MOI',
        'Air Conditioning',
        'Gas Supply',
        'SNG',
        'LPG',
        'Garbage Chute',
    ],
}

# هل تريد إنشاء سجلات تتبع (PENDING) للعناصر الجديدة للمشاريع النشطة؟
# خلّيها False لو عايز تعدّل الـ Master Data فقط بدون لمس المشاريع.
CREATE_TRACKINGS_FOR_ACTIVE_PROJECTS = False

with transaction.atomic():
    # 1) إنشاء / تفعيل عناصر الكتالوج المطلوب فقط
    desired_ids = []
    created_count = 0
    for (stage, dept), names in DESIRED_CATALOG.items():
        for name in names:
            item, was_created = DisciplineItem.objects.update_or_create(
                name=name, stage=stage, department=dept,
                defaults={'is_active': True},
            )
            desired_ids.append(item.id)
            if was_created:
                created_count += 1

    # 2) حذف أي Discipline آخر غير موجود في الكتالوج (نهائيًا)
    deleted_count, _ = DisciplineItem.objects.exclude(id__in=desired_ids).delete()

    # 3) اختياري: تتبع العناصر في المشاريع النشطة
    trackings_created = 0
    if CREATE_TRACKINGS_FOR_ACTIVE_PROJECTS:
        items = DisciplineItem.objects.filter(id__in=desired_ids)
        for project in Project.objects.filter(is_active=True):
            for item in items:
                _, t_created = DisciplineTracking.objects.get_or_create(
                    project=project,
                    discipline_item=item,
                    defaults={'status': 'PENDING'},
                )
                if t_created:
                    trackings_created += 1

print('Created items        :', created_count)
print('Final catalog size   :', len(desired_ids))
print('Deleted other items  :', deleted_count)
print('Trackings created    :', trackings_created)