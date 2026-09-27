from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import ValidationError
from ..models import AuditLog, AuditLog, ProjectLifecycleStage, Project
from .audit_service import AuditService
from .notification_service import NotificationService, NotificationType

class LifecycleService:
    """
    خدمة إدارة دورة حياة المشروع
    """
    
    STAGE_SEQUENCES = {
        'OFFER': 1,
        'CONTRACT_SUBMITTED': 2,
        'CONTRACT_SIGNED': 3,
        'DESIGN_PHASE': 4,
        'COLLECTION': 5,
        'CLOSED': 6,
    }
    
    STAGE_DURATIONS = {
        'OFFER': 0,
        'CONTRACT_SUBMITTED': 7,
        'CONTRACT_SIGNED': 14,
        'DESIGN_PHASE': 30,
        'COLLECTION': 60,
        'CLOSED': 90,
    }
    
    @staticmethod
    def start_stage(stage, user):
        """
        بدء مرحلة جديدة
        """
        if stage.status != ProjectLifecycleStage.Status.UPCOMING:
            raise ValidationError("Stage is not upcoming.")
        
        # التحقق من المراحل السابقة
        LifecycleService.validate_sequence(stage)
        
        stage.status = ProjectLifecycleStage.Status.IN_PROGRESS
        stage.actual_date = timezone.now().date()
        stage.save()
        
        AuditService.log(
            stage.project, user,
            AuditLog.ActionType.STAGE_ACTUAL_DATE_UPDATED,
            f"Stage '{stage.stage_name}' started"
        )
        
        return stage
    
    @staticmethod
    def complete_stage(stage, user):
        """
        إكمال مرحلة
        """
        if stage.status not in [
            ProjectLifecycleStage.Status.UPCOMING,
            ProjectLifecycleStage.Status.IN_PROGRESS
        ]:
            raise ValidationError("Stage cannot be completed.")
        
        LifecycleService.validate_sequence(stage)
        
        stage.status = ProjectLifecycleStage.Status.ACHIEVED
        stage.actual_end_date = timezone.now().date()
        stage.save()
        
        # حساب التأخير/التقدم
        delay = LifecycleService.calculate_delay(stage)
        
        AuditService.log(
            stage.project, user,
            AuditLog.ActionType.STAGE_ACTUAL_DATE_UPDATED,
            f"Stage '{stage.stage_name}' completed. Delay: {delay} days"
        )
        
        # إشعار المديرين
        NotificationService.notify_managers(
            stage.project, user,
            NotificationType.STAGE_COMPLETED,
            "Stage Completed",
            f"Stage '{stage.stage_name}' completed for project {stage.project.project_no}"
        )
        
        # بدء المرحلة التالية تلقائياً
        LifecycleService.auto_start_next_stage(stage)
        
        return stage
    
    @staticmethod
    def approve_stage(stage, user):
        """
        اعتماد مرحلة
        """
        if stage.status != ProjectLifecycleStage.Status.ACHIEVED:
            raise ValidationError("Stage must be completed before approval.")
        
        stage.status = ProjectLifecycleStage.Status.APPROVED
        stage.save()
        
        AuditService.log(
            stage.project, user,
            AuditLog.ActionType.STAGE_ACTUAL_DATE_UPDATED,
            f"Stage '{stage.stage_name}' approved"
        )
        
        return stage
    
    @staticmethod
    def reopen_stage(stage, user):
        """
        إعادة فتح مرحلة
        """
        if stage.status != ProjectLifecycleStage.Status.APPROVED:
            raise ValidationError("Only approved stages can be reopened.")
        
        stage.status = ProjectLifecycleStage.Status.IN_PROGRESS
        stage.save()
        
        AuditService.log(
            stage.project, user,
            AuditLog.ActionType.STAGE_ACTUAL_DATE_UPDATED,
            f"Stage '{stage.stage_name}' reopened"
        )
        
        return stage
    
    @staticmethod
    def close_project(project, user):
        """
        إغلاق المشروع
        """
        # التحقق من إكمال جميع المراحل
        incomplete_stages = project.lifecycle_stages.exclude(
            status__in=[
                ProjectLifecycleStage.Status.ACHIEVED,
                ProjectLifecycleStage.Status.APPROVED
            ]
        )
        
        if incomplete_stages.exists():
            raise ValidationError("Cannot close project. Incomplete stages exist.")
        
        project.is_active = False
        project.save(update_fields=['is_active'])
        
        AuditService.log(
            project, user,
            AuditLog.ActionType.PROJECT_UPDATED,
            "Project closed"
        )
        
        NotificationService.notify_managers(
            project, user,
            NotificationType.PROJECT_CLOSED,
            "Project Closed",
            f"Project '{project.name}' has been closed"
        )
        
        return project
    
    @staticmethod
    def calculate_delay(stage):
        """
        حساب التأخير أو التقدم في المرحلة
        """
        if not stage.planned_end_date or not stage.actual_end_date:
            return 0
        
        delta = (stage.actual_end_date - stage.planned_end_date).days
        return delta
    
    @staticmethod
    def calculate_progress(project):
        """
        حساب نسبة إنجاز المشروع
        """
        total_stages = project.lifecycle_stages.count()
        if total_stages == 0:
            return 0.0
        
        completed_stages = project.lifecycle_stages.filter(
            status__in=[
                ProjectLifecycleStage.Status.ACHIEVED,
                ProjectLifecycleStage.Status.APPROVED
            ]
        ).count()
        
        return round((completed_stages / total_stages) * 100, 2)
    
    @staticmethod
    def validate_sequence(stage):
        """
        التحقق من تسلسل المراحل
        """
        current_seq = LifecycleService.STAGE_SEQUENCES.get(stage.stage_name, 0)
        
        previous_stages = stage.project.lifecycle_stages.filter(
            sequence_order__lt=stage.sequence_order
        ).exclude(
            status__in=[
                ProjectLifecycleStage.Status.ACHIEVED,
                ProjectLifecycleStage.Status.APPROVED
            ]
        )
        
        if previous_stages.exists():
            unachieved = [s.get_stage_name_display() for s in previous_stages]
            raise ValidationError(
                f"Cannot update this stage. Previous stages must be completed first: {', '.join(unachieved)}"
            )
    
    @staticmethod
    def auto_start_next_stage(current_stage):
        """
        بدء المرحلة التالية تلقائياً
        """
        next_stage = current_stage.project.lifecycle_stages.filter(
            sequence_order=current_stage.sequence_order + 1
        ).first()
        
        if next_stage and next_stage.status == ProjectLifecycleStage.Status.UPCOMING:
            next_stage.status = ProjectLifecycleStage.Status.IN_PROGRESS
            next_stage.save()
    
    @staticmethod
    def calculate_planned_dates(project):
        """
        حساب التواريخ المخططة للمراحل
        """
        if not project.start_date:
            return None
        
        planned_dates = {}
        for stage_name, duration in LifecycleService.STAGE_DURATIONS.items():
            planned_dates[stage_name] = project.start_date + timedelta(days=duration)
        
        return planned_dates
    
    @staticmethod
    def auto_update_planned_dates(project):
        """
        تحديث التواريخ المخططة تلقائياً
        """
        planned_dates = LifecycleService.calculate_planned_dates(project)
        if not planned_dates:
            return
        
        for stage in project.lifecycle_stages.all():
            if stage.stage_name in planned_dates and not stage.planned_date:
                stage.planned_date = planned_dates[stage.stage_name]
                stage.save(update_fields=['planned_date'])