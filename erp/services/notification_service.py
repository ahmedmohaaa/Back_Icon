from ..models import Notification, User

class NotificationType:
    """ثوابت أنواع الإشعارات"""
    PAYMENT_RECEIVED = 'PAYMENT_RECEIVED'
    TASK_ASSIGNED = 'TASK_ASSIGNED'
    TASK_COMPLETED = 'TASK_COMPLETED'
    REPLACEMENT_REQUEST = 'REPLACEMENT_REQUEST'
    REPLACEMENT_APPROVED = 'REPLACEMENT_APPROVED'
    STAGE_COMPLETED = 'STAGE_COMPLETED'
    PROJECT_CLOSED = 'PROJECT_CLOSED'
    INVOICE_OVERDUE = 'INVOICE_OVERDUE'

class NotificationService:
    """
    خدمة موحدة لإرسال الإشعارات
    """
    
    @staticmethod
    def send(project, sender, notification_type, title, message, user=None, users=None):
        """
        إرسال إشعار لمستخدم واحد أو مجموعة
        """
        notifications = []
        
        if user:
            notifications.append(Notification(
                user=user,
                sender=sender,
                notification_type=notification_type,
                title=title,
                message=message,
                related_link=f"/projects/{project.id}/" if project else None
            ))
        
        if users:
            for u in users:
                notifications.append(Notification(
                    user=u,
                    sender=sender,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    related_link=f"/projects/{project.id}/" if project else None
                ))
        
        if notifications:
            Notification.objects.bulk_create(notifications)
        
        return notifications
    
    @staticmethod
    def notify_managers(project, sender, notification_type, title, message):
        """
        إرسال إشعار لجميع المديرين
        """
        managers = User.objects.filter(
            role__in=['GM', 'AGM', 'DESIGN_MGR', 'SUP_MGR']
        )
        return NotificationService.send(
            project, sender, notification_type, title, message, users=managers
        )
    
    @staticmethod
    def notify_engineer(engineer, project, sender, notification_type, title, message):
        """
        إرسال إشعار لمهندس محدد
        """
        return NotificationService.send(
            project, sender, notification_type, title, message, user=engineer
        )