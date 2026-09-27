
from django.db import migrations

def seed_discipline_items(apps, schema_editor):
    DisciplineItem = apps.get_model('erp', 'DisciplineItem')
    
    items = [
        # =================== CONCEPT DESIGN ===================
        {"name": "Sketch", "stage": "CONCEPT", "department": "ARCH"},
        {"name": "Perspectives", "stage": "CONCEPT", "department": "ARCH"},
        
        # =================== DC1 - ARCHITECTURE ===================
        {"name": "Infrastructure Planning", "stage": "DC1", "department": "ARCH"},
        {"name": "Life Safety Plan", "stage": "DC1", "department": "ARCH"},
        {"name": "MOTC", "stage": "DC1", "department": "ARCH"},
        {"name": "Qatar Rail Coordination", "stage": "DC1", "department": "ARCH"},
        {"name": "Site Plan", "stage": "DC1", "department": "ARCH"},
        {"name": "Floor Plans", "stage": "DC1", "department": "ARCH"},
        {"name": "Elevations", "stage": "DC1", "department": "ARCH"},
        {"name": "Sections", "stage": "DC1", "department": "ARCH"},
        {"name": "Material Schedule", "stage": "DC1", "department": "ARCH"},
        {"name": "Door & Window Schedule", "stage": "DC1", "department": "ARCH"},
        {"name": "Landscape Layout", "stage": "DC1", "department": "ARCH"},
        {"name": "Parking Layout", "stage": "DC1", "department": "ARCH"},
        {"name": "Reflected Ceiling Plan", "stage": "DC1", "department": "ARCH"},
        
        # =================== DC1 - STRUCTURAL ===================
        {"name": "Structural Concept", "stage": "DC1", "department": "STRUCT"},
        {"name": "Foundation Plan", "stage": "DC1", "department": "STRUCT"},
        {"name": "Structural Framing Plan", "stage": "DC1", "department": "STRUCT"},
        {"name": "Column Schedule", "stage": "DC1", "department": "STRUCT"},
        {"name": "Load Calculations", "stage": "DC1", "department": "STRUCT"},
        {"name": "Soil Investigation", "stage": "DC1", "department": "STRUCT"},
        
        # =================== DC1 - MECHANICAL ===================
        {"name": "HVAC Layout", "stage": "DC1", "department": "MECH"},
        {"name": "Plumbing Layout", "stage": "DC1", "department": "MECH"},
        {"name": "Fire Fighting System", "stage": "DC1", "department": "MECH"},
        {"name": "Drainage System", "stage": "DC1", "department": "MECH"},
        {"name": "Equipment Schedule", "stage": "DC1", "department": "MECH"},
        
        # =================== DC1 - ELECTRICAL ===================
        {"name": "Lighting Layout", "stage": "DC1", "department": "ELEC"},
        {"name": "Power Layout", "stage": "DC1", "department": "ELEC"},
        {"name": "Single Line Diagram", "stage": "DC1", "department": "ELEC"},
        {"name": "Fire Alarm Layout", "stage": "DC1", "department": "ELEC"},
        {"name": "Low Voltage Systems", "stage": "DC1", "department": "ELEC"},
        {"name": "Load Distribution", "stage": "DC1", "department": "ELEC"},
        {"name": "ELV / Data / Telecom", "stage": "DC1", "department": "ELEC"},
        
        # =================== DC2 - ARCHITECTURE ===================
        {"name": "Detailed Floor Plans", "stage": "DC2", "department": "ARCH"},
        {"name": "Detailed Elevations", "stage": "DC2", "department": "ARCH"},
        {"name": "Detailed Sections", "stage": "DC2", "department": "ARCH"},
        {"name": "Finishing Schedule", "stage": "DC2", "department": "ARCH"},
        {"name": "Kitchen & Bathroom Details", "stage": "DC2", "department": "ARCH"},
        {"name": "Staircase Details", "stage": "DC2", "department": "ARCH"},
        {"name": "Joinery Details", "stage": "DC2", "department": "ARCH"},
        {"name": "Swimming Pool Details", "stage": "DC2", "department": "ARCH"},
        {"name": "Boundary Wall Details", "stage": "DC2", "department": "ARCH"},
        {"name": "Ramps & Accessibility", "stage": "DC2", "department": "ARCH"},
        {"name": "Canopy & Shade Details", "stage": "DC2", "department": "ARCH"},
        {"name": "Landscape Detailing", "stage": "DC2", "department": "ARCH"},
        {"name": "Signage & Wayfinding", "stage": "DC2", "department": "ARCH"},
        
        # =================== DC2 - STRUCTURAL ===================
        {"name": "Structural Details", "stage": "DC2", "department": "STRUCT"},
        {"name": "Reinforcement Details", "stage": "DC2", "department": "STRUCT"},
        {"name": "Connection Details", "stage": "DC2", "department": "STRUCT"},
        {"name": "Retaining Wall Details", "stage": "DC2", "department": "STRUCT"},
        {"name": "Water Tank Structural", "stage": "DC2", "department": "STRUCT"},
        {"name": "Swimming Pool Structural", "stage": "DC2", "department": "STRUCT"},
        {"name": "Structural Calculation Sheets", "stage": "DC2", "department": "STRUCT"},
        
        # =================== DC2 - MECHANICAL ===================
        {"name": "HVAC Ductwork Details", "stage": "DC2", "department": "MECH"},
        {"name": "Plumbing Riser Diagram", "stage": "DC2", "department": "MECH"},
        {"name": "Sprinkler Layout", "stage": "DC2", "department": "MECH"},
        {"name": "Medical Gas (if applicable)", "stage": "DC2", "department": "MECH"},
        {"name": "Equipment Room Layout", "stage": "DC2", "department": "MECH"},
        {"name": "Water Supply Schematic", "stage": "DC2", "department": "MECH"},
        
        # =================== DC2 - ELECTRICAL ===================
        {"name": "Lighting Details", "stage": "DC2", "department": "ELEC"},
        {"name": "Power Details", "stage": "DC2", "department": "ELEC"},
        {"name": "Generator Sizing", "stage": "DC2", "department": "ELEC"},
        {"name": "UPS Layout", "stage": "DC2", "department": "ELEC"},
        {"name": "Earthing Layout", "stage": "DC2", "department": "ELEC"},
        {"name": "Lighting Protection", "stage": "DC2", "department": "ELEC"},
        {"name": "BMS / Smart Home", "stage": "DC2", "department": "ELEC"},
        {"name": "CCTV Layout", "stage": "DC2", "department": "ELEC"},
        {"name": "Access Control", "stage": "DC2", "department": "ELEC"},
        {"name": "Audio Visual Systems", "stage": "DC2", "department": "ELEC"},
        
        # =================== TENDER DOCUMENTS ===================
        {"name": "BOQ - Bill of Quantities", "stage": "TENDER", "department": "ARCH"},
        {"name": "Specifications", "stage": "TENDER", "department": "ARCH"},
        {"name": "Conditions of Contract", "stage": "TENDER", "department": "ARCH"},
        {"name": "Perspectives (Tender)", "stage": "TENDER", "department": "ARCH"},
        {"name": "Technical Submittals", "stage": "TENDER", "department": "ARCH"},
        {"name": "Tender Drawing Set", "stage": "TENDER", "department": "ARCH"},
    ]
    
    for item in items:
        DisciplineItem.objects.get_or_create(
            name=item["name"],
            stage=item["stage"],
            department=item["department"],
            defaults={"is_active": True}
        )


def reverse_seed(apps, schema_editor):
    DisciplineItem = apps.get_model('erp', 'DisciplineItem')
    DisciplineItem.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        # غيّر 'erp' لاسم التطبيق الفعلي
        # يجب أن يكون بعد migration إنشاء جدول DisciplineItem
            ('erp', '0002_alter_projectlifecyclestage_options_and_more'),

    ]

    operations = [
        migrations.RunPython(seed_discipline_items, reverse_seed),
    ]