from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from ..models import AuditLog, Project, Task
from .audit_service import AuditService
from .notification_service import NotificationService, NotificationType
from .lifecycle_service import LifecycleService

class ProjectService:
    """
    خدمة إدارة المشاريع
    """
    
    @staticmethod
    @transaction.atomic
    def create_change_order(project, data, user):
        """
        إنشاء Change Order (يحدد النوع تلقائياً)
        """
        if not project.is_active:
            return ProjectService.create_sub_project_change_order(project, data, user)
        else:
            return ProjectService.create_task_change_order(project, data, user)
    
    @staticmethod
    @transaction.atomic
    def create_sub_project_change_order(project, data, user):
        """
        إنشاء Sub Project للمشاريع المغلقة
        """
        sub_project = Project.objects.create(
            parent_project=project,
            name=f"{project.name} - Change Order",
            project_no=f"{project.project_no}-CO",
            revision_number=data.get('revision_number', 'Rev1'),
            new_application_no=data.get('new_application_no'),
            revision_start_date=data.get('revision_start_date'),
            change_order_reason=data.get('change_order_reason'),
            scope=project.scope,
            client=project.client,
            contractor=project.contractor,
            is_active=True
        )
        
        AuditService.log(
            project, user,
            AuditLog.ActionType.REVISION_CREATED,
            f"Sub-project created: {sub_project.project_no}"
        )
        
        NotificationService.notify_managers(
            project, user,
            NotificationType.REPLACEMENT_APPROVED,
            "Change Order Created",
            f"Sub-project created for closed project: {project.project_no}"
        )
        
        return sub_project
    
    @staticmethod
    @transaction.atomic
    def create_task_change_order(project, data, user):
        """
        إنشاء Tasks للمشاريع النشطة
        """
        tasks_data = data.get('tasks', [])
        created_tasks = []
        
        for task_data in tasks_data:
            task = Task.objects.create(
                project=project,
                task_type=Task.TaskType.CHANGE_ORDER,
                assigned_to_id=task_data.get('assigned_to'),
                discipline_id=task_data.get('discipline'),
                stage=task_data.get('stage'),
                title=task_data.get('title'),
                priority=task_data.get('priority', Project.PriorityStatus.MEDIUM),
                status=Task.Status.UNCHARTED
            )
            created_tasks.append(task)
        
        AuditService.log(
            project, user,
            AuditLog.ActionType.TASK_CREATED,
            f"{len(created_tasks)} change order tasks created"
        )
        
        return created_tasks
    
    @staticmethod
    def get_project_with_financials(project):
        """
        جلب المشروع مع البيانات المالية
        """
        from .invoice_service import InvoiceService
        
        financials = InvoiceService.calculate_outstanding(project)
        progress = LifecycleService.calculate_progress(project)
        
        return {
            'project': project,
            'financials': financials,
            'progress': progress
        }