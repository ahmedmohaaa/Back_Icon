from ..models import AuditLog

class AuditService:
    """
    خدمة موحدة لتسجيل الـ Audit Logs
    """
    
    @staticmethod
    def log(project, user, action_type, details=""):
        """
        تسجيل حدث في Audit Log
        """
        if not action_type:
            return None
            
        return AuditLog.objects.create(
            project=project,
            user=user,
            action_type=action_type,
            details=details
        )
    
    @staticmethod
    def log_project_created(project, user):
        return AuditService.log(
            project, user,
            AuditLog.ActionType.PROJECT_CREATED,
            f"Project '{project.name}' created"
        )
    
    @staticmethod
    def log_task_status_changed(task, old_status, new_status, user):
        return AuditService.log(
            task.project, user,
            AuditLog.ActionType.TASK_STATUS_CHANGED,
            f"Task '{task.title}': {old_status} → {new_status}"
        )
    
    @staticmethod
    def log_invoice_payment(invoice, amount, user):
        return AuditService.log(
            invoice.project, user,
            AuditLog.ActionType.INVOICE_STATUS_CHANGED,
            f"Payment {amount} recorded for '{invoice.title}'"
        )