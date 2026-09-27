from decimal import Decimal
from django.db import transaction
from django.db.models.aggregates import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from ..models import AuditLog, Invoice, InvoicePayment, Project
from .audit_service import AuditService
from .notification_service import NotificationService, NotificationType

ZERO = Decimal("0.00")

class InvoiceService:
    """
    خدمة إدارة الفواتير والمدفوعات
    """
    
    @staticmethod
    @transaction.atomic
    def record_payment(invoice, amount_paid, recorded_by):
        """
        تسجيل دفعة مع تحديث الحالة والإشعارات
        """
        if amount_paid <= ZERO:
            raise ValidationError("Payment amount must be greater than zero.")
        
        # حساب إجمالي المدفوع
        total_paid = InvoicePayment.objects.filter(
            invoice=invoice
        ).aggregate(total=Sum('amount_paid'))['total'] or ZERO
        
        new_total = total_paid + amount_paid
        
        if new_total > invoice.total_amount:
            raise ValidationError(
                f"Total payments ({new_total}) exceed invoice amount ({invoice.total_amount})."
            )
        
        # إنشاء الدفعة
        payment = InvoicePayment.objects.create(
            invoice=invoice,
            amount_paid=amount_paid,
            recorded_by=recorded_by
        )
        
        # تحديث حالة الفاتورة
        old_status = invoice.status
        if new_total >= invoice.total_amount:
            invoice.status = Invoice.Status.PAID
        else:
            invoice.status = Invoice.Status.PARTIALLY_PAID
        
        invoice.save()
        
        # Audit Log
        AuditService.log_invoice_payment(invoice, amount_paid, recorded_by)
        
        # Notification للمديرين
        NotificationService.notify_managers(
            invoice.project,
            recorded_by,
            NotificationType.PAYMENT_RECEIVED,
            "Payment Received",
            f"Payment of {amount_paid} received for {invoice.title}"
        )
        
        # التحقق من أول فاتورة مدفوعة لتحديث تاريخ بدء المشروع
        InvoiceService.check_first_payment_and_set_start_date(invoice.project)
        
        return payment
    
    @staticmethod
    def check_first_payment_and_set_start_date(project):
        """
        التحقق من أول فاتورة مدفوعة وتحديث تاريخ بدء المشروع
        """
        if project.start_date:
            return  # التاريخ موجود مسبقاً
        
        first_payment = InvoicePayment.objects.filter(
            invoice__project=project
        ).order_by('payment_date').first()
        
        if first_payment:
            project.start_date = first_payment.payment_date
            project.save(update_fields=['start_date'])
            
            AuditService.log(
                project, first_payment.recorded_by,
                AuditLog.ActionType.PROJECT_UPDATED,
                f"Project start date auto-set to {first_payment.payment_date}"
            )
    
    @staticmethod
    def calculate_outstanding(project):
        """
        حساب المبلغ المتبقي للمشروع
        """
        valid_invoices = Invoice.objects.filter(
            project=project
        ).exclude(
            status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED]
        )
        
        total_invoiced = valid_invoices.aggregate(
            total=Sum('total_amount')
        )['total'] or ZERO
        
        total_collected = InvoicePayment.objects.filter(
            invoice__in=valid_invoices
        ).aggregate(
            total=Sum('amount_paid')
        )['total'] or ZERO
        
        return {
            'total_invoiced': total_invoiced,
            'total_collected': total_collected,
            'outstanding': total_invoiced - total_collected
        }