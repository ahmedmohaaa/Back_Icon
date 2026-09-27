from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import ValidationError
from ..models import AuditLog, Task, DisciplineTracking, AssignmentHistory, StaffKPI
from .audit_service import AuditService
from .notification_service import NotificationService, NotificationType

class TaskStatusHandler:
    """
    Pattern للتعامل مع تغييرات حالة المهام
    """
    
    @staticmethod
    def handle_completed(task, user):
        """معالجة إكمال المهمة"""
        task.end_date = timezone.now().date()
        task.progress_percentage = 100
        task.save()
        
        # تحديث Discipline Tracking
        if task.discipline_tracking:
            task.discipline_tracking.status = DisciplineTracking.Status.COMPLETED
            task.discipline_tracking.end_date = timezone.now().date()
            task.discipline_tracking.save()
        
        AuditService.log(
            task.project, user,
            AuditLog.ActionType.TASK_COMPLETED,
            f"Task '{task.title}' completed"
        )
    
    @staticmethod
    def handle_approved(task, user):
        """معالجة اعتماد المهمة"""
        task.approval_date = timezone.now().date()
        task.progress_percentage = 100
        task.save()
        
        if task.discipline_tracking:
            task.discipline_tracking.status = DisciplineTracking.Status.APPROVED
            task.discipline_tracking.save()
        
        AuditService.log(
            task.project, user,
            AuditLog.ActionType.TASK_APPROVED,
            f"Task '{task.title}' approved"
        )
    
    @staticmethod
    def handle_on_hold(task, hold_reason, expected_resume_date, user):
        """معالجة إيقاف المهمة"""
        task.is_on_hold = True
        task.hold_reason = hold_reason
        task.hold_date = timezone.now().date()
        task.expected_resume_date = expected_resume_date
        task.save()
        
        AuditService.log(
            task.project, user,
            AuditLog.ActionType.ON_HOLD_SET,
            f"Task '{task.title}' on hold: {hold_reason}"
        )
    
    @staticmethod
    def handle_resume(task, user):
        """معالجة استئناف المهمة"""
        task.is_on_hold = False
        task.hold_reason = None
        task.hold_date = None
        task.expected_resume_date = None
        task.save()
        
        AuditService.log(
            task.project, user,
            AuditLog.ActionType.ON_HOLD_RESUMED,
            f"Task '{task.title}' resumed"
        )


class TaskService:
    """
    خدمة إدارة المهام
    """
    
    STATUS_HANDLERS = {
        Task.Status.COMPLETED: TaskStatusHandler.handle_completed,
        Task.Status.APPROVED: TaskStatusHandler.handle_approved,
    }
    
    @staticmethod
    @transaction.atomic
    def update_status(task, new_status, user, **kwargs):
        """
        تحديث حالة المهمة مع معالجة جميع الآثار الجانبية
        """
        old_status = task.status
        
        if old_status == new_status:
            return task
        
        task.status = new_status
        task.status_date = timezone.now().date()
        task.status_changed_at = timezone.now()
        
        # معالجة الحالة الجديدة
        handler = TaskService.STATUS_HANDLERS.get(new_status)
        if handler:
            handler(task, user)
        
        # معالجة On Hold
        if kwargs.get('is_on_hold') and not task.is_on_hold:
            TaskStatusHandler.handle_on_hold(
                task,
                kwargs.get('hold_reason'),
                kwargs.get('expected_resume_date'),
                user
            )
        elif not kwargs.get('is_on_hold') and task.is_on_hold:
            TaskStatusHandler.handle_resume(task, user)
        
        task.save()
        
        # Audit Log
        AuditService.log_task_status_changed(task, old_status, new_status, user)
        
        return task
    
    @staticmethod
    @transaction.atomic
    def reassign(task, new_engineer, reason, user):
        """
        إعادة تعيين المهمة لمهندس آخر
        """
        old_engineer = task.assigned_to
        
        if old_engineer == new_engineer:
            raise ValidationError("Cannot reassign to the same engineer.")
        
        # حساب أيام العمل
        days_worked = 0
        if task.start_date:
            days_worked = (timezone.now().date() - task.start_date).days
            days_worked = max(days_worked, 0)
        
        # إنشاء سجل التعيين
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
        
        AuditService.log(
            task.project, user,
            AuditLog.ActionType.TASK_ASSIGNED,
            f"Task reassigned from {old_engineer} to {new_engineer}. Reason: {reason}"
        )
        
        NotificationService.notify_engineer(
            new_engineer, task.project, user,
            NotificationType.TASK_ASSIGNED,
            "Task Assigned",
            f"You have been assigned to task: {task.title}"
        )
        
        return task