from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views

urlpatterns = [
    path("login/", views.LoginTokenView.as_view()),   # ✅ تسجّل آخر دخول حقيقي
    path("refresh/", TokenRefreshView.as_view()),
]

user_urlpatterns = [
    path('users/me/', views.CurrentUserAPIView.as_view(), name='user-me'),
    path('users/create/', views.UserCreateAPIView.as_view(), name='user-create'),
    path('users/', views.UserListAPIView.as_view(), name='user-list'),
    path('users/<int:pk>/', views.UserRetrieveAPIView.as_view(), name='user-detail'),
    path('users/<int:pk>/update/', views.UserUpdateAPIView.as_view(), name='user-update'),
    path('users/<int:pk>/delete/', views.UserDeleteAPIView.as_view(), name='user-delete'),
    path('users/change-password/', views.ChangePasswordAPIView.as_view(), name='change-password'),
path('auth/login/', views.LoginTokenView.as_view(), name='login'),
]

client_urlpatterns = [
    path('clients/', views.ClientListCreateAPIView.as_view(), name='client-list-create'),
    path('clients/<int:pk>/', views.ClientRetrieveUpdateDestroyAPIView.as_view(), name='client-detail'),
    path('clients/<int:pk>/projects/', views.ClientProjectsAPIView.as_view(), name='client-projects'),
]

contractor_urlpatterns = [
    path('contractors/', views.ContractorListCreateAPIView.as_view(), name='contractor-list-create'),
    path('contractors/<int:pk>/', views.ContractorRetrieveUpdateDestroyAPIView.as_view(), name='contractor-detail'),
    path('contractors/<int:pk>/projects/', views.ContractorProjectsAPIView.as_view(), name='contractor-projects'),
]

project_urlpatterns = [
    path('projects/active/', views.ActiveProjectsAPIView.as_view(), name='project-active-list'),
    path('projects/closed/', views.ClosedProjectsAPIView.as_view(), name='project-closed-list'),
    path('projects/pending/', views.PendingProjectsAPIView.as_view(), name='project-pending-list'),
    path('projects/design/', views.DesignProjectsAPIView.as_view(), name='project-design-list'),
    path('projects/supervision/', views.SupervisionProjectsAPIView.as_view(), name='project-supervision-list'),
    path('projects/shared/', views.SharedProjectsAPIView.as_view(), name='project-shared-list'),
    path('projects/create/', views.ProjectCreateAPIView.as_view(), name='project-create'),
    path('projects/', views.ProjectListAPIView.as_view(), name='project-list'),
    path('projects/<int:pk>/', views.ProjectDetailAPIView.as_view(), name='project-detail'),
    path('projects/<int:pk>/update/', views.ProjectUpdateAPIView.as_view(), name='project-update'),
    path('projects/<int:pk>/delete/', views.ProjectDeleteAPIView.as_view(), name='project-delete'),
    path('projects/<int:pk>/priority/', views.ProjectPriorityAPIView.as_view(), name='project-priority'),
    path('projects/<int:pk>/priority-history/', views.PriorityHistoryAPIView.as_view(), name='project-priority-history'),
    path('projects/<int:pk>/change-order/', views.ProjectChangeOrderAPIView.as_view(), name='project-change-order'),
    path('projects/<int:pk>/revision/', views.ProjectRevisionAPIView.as_view(), name='project-revision'),
    path('projects/<int:pk>/sub-projects/', views.SubProjectsAPIView.as_view(), name='project-sub-projects'),
    path('projects/<int:pk>/dc1-status/', views.DC1StatusAPIView.as_view(), name='project-dc1-status'),
    path('projects/<int:pk>/dc2-status/', views.DC2StatusAPIView.as_view(), name='project-dc2-status'),
    path('projects/<int:pk>/structural-status/', views.StructuralStatusAPIView.as_view(), name='project-structural-status'),
    path('projects/<int:pk>/ifc-status/', views.IFCStatusAPIView.as_view(), name='project-ifc-status'),
    path('projects/<int:pk>/progress/', views.ProjectProgressAPIView.as_view(), name='project-progress'),
path('projects/<int:pk>/change-order/create/', views.CreateChangeOrderAPIView.as_view(),name='project-change-order-create'),


path('lifecycle/<int:pk>/advance/', views.LifecycleAdvanceAPIView.as_view(), name='lifecycle-advance'),
path('projects/<int:pk>/mark-delivered/', views.MarkDeliveredAPIView.as_view(), name='mark-delivered'),
path('projects/<int:pk>/close/', views.CloseProjectAPIView.as_view(), name='close-project'),

    path('projects/<int:parent_pk>/change-orders/',
         views.ChangeOrderListCreateForParentAPIView.as_view(), name='change-order-list-create'),
    path('change-orders/<int:pk>/',
         views.ChangeOrderDetailAPIView.as_view(), name='change-order-detail'),
    path('change-orders/<int:pk>/confirm/',
         views.ChangeOrderConfirmAPIView.as_view(), name='change-order-confirm'),
    path('change-orders/<int:pk>/reject/',
         views.ChangeOrderRejectAPIView.as_view(), name='change-order-reject'),
    path('change-orders/<int:pk>/cancel/',
         views.ChangeOrderCancelAPIView.as_view(), name='change-order-cancel'),
         path('change-orders/active/', views.ChangeOrderActiveAPIView.as_view(), name='change-orders-active'),

path('my-supervision-projects/', views.MySupervisionProjectsAPIView.as_view(), name='my-supervision-projects'),
path('supervision-replacement-requests/<int:pk>/respond/', views.SupervisionReplacementRespondAPIView.as_view(), name='supervision-replacement-respond'),
path('supervision-team/replacement-request/',
     views.SupervisionReplacementRequestCreateAPIView.as_view(),
     name='supervision-replacement-request'),
]

lifecycle_urlpatterns = [
    path('lifecycle/analytics/', views.LifecycleAnalyticsAPIView.as_view(), name='lifecycle-analytics'),
    path('lifecycle/', views.LifecycleListAPIView.as_view(), name='lifecycle-list'),
    path('lifecycle/<int:pk>/update/', views.LifecycleUpdateAPIView.as_view(), name='lifecycle-update'),
]

internal_review_urlpatterns = [
    path('internal-reviews/', views.InternalReviewListAPIView.as_view(), name='internal-review-list'),
    path('internal-reviews/<int:pk>/update/', views.InternalReviewUpdateAPIView.as_view(), name='internal-review-update'),
    path('internal-reviews/<int:pk>/approve/', views.InternalReviewApproveAPIView.as_view(), name='internal-review-approve'),
path('projects/<int:pk>/internal-design-review/activate/',views.ActivateInternalDesignReviewAPIView.as_view(),name='internal-design-review-activate'),
path('projects/<int:pk>/internal-review/',        views.InternalReviewDetailAPIView.as_view(), name='internal-review-detail'),
path('projects/<int:pk>/internal-review/assign/', views.InternalReviewAssignAPIView.as_view(), name='internal-review-assign'),
path('internal-review/<int:pk>/update/',          views.InternalReviewStageUpdateAPIView.as_view(), name='internal-review-stage-update'),
path('projects/<int:pk>/activate-internal-review/',
     views.ActivateInternalReviewAPIView.as_view(), name='activate-internal-review'),
     path('my-internal-reviews/', views.MyInternalReviewsAPIView.as_view(), name='my-internal-reviews'),
path('internal-review/stages/<int:pk>/', views.InternalReviewStageUpdateAPIView.as_view(), name='internal-review-stage-update'),
]

tendering_urlpatterns = [
    path('projects/<int:project_id>/tendering/', views.TenderingDetailAPIView.as_view(), name='tendering-detail'),
    path('projects/<int:project_id>/tendering/update/', views.TenderingUpdateAPIView.as_view(), name='tendering-update'),
path('projects/<int:project_id>/tendering/create/', views.TenderingCreateAPIView.as_view(), name='tendering-create'),
]

task_urlpatterns = [
    path('tasks/my-tasks/', views.MyTasksAPIView.as_view(), name='task-my-tasks'),
    path('tasks/my-internal-reviews/', views.InternalReviewTasksAPIView.as_view(), name='task-my-internal-reviews'),
    path('tasks/my-change-orders/', views.ChangeOrderTasksAPIView.as_view(), name='task-my-change-orders'),
    path('tasks/create/', views.TaskCreateAPIView.as_view(), name='task-create'),
    path('tasks/', views.TaskListAPIView.as_view(), name='task-list'),
    path('tasks/<int:pk>/', views.TaskDetailAPIView.as_view(), name='task-detail'),
    path('tasks/<int:pk>/update/', views.TaskUpdateAPIView.as_view(), name='task-update'),
    path('tasks/<int:pk>/delete/', views.TaskDeleteAPIView.as_view(), name='task-delete'),
    path('tasks/<int:pk>/status/', views.TaskStatusAPIView.as_view(), name='task-status'),
    path('tasks/<int:pk>/assign/', views.TaskAssignAPIView.as_view(), name='task-assign'),
    path('tasks/<int:pk>/reassign/', views.TaskReassignAPIView.as_view(), name='task-reassign'),
    path('tasks/<int:pk>/assignment-history/', views.AssignmentHistoryAPIView.as_view(), name='task-assignment-history'),
    path('tasks/<int:pk>/replacement-request/', views.ReplacementRequestCreateAPIView.as_view(), name='task-replacement-request'),
    path('replacement-requests/<int:pk>/respond/', views.ReplacementRequestRespondAPIView.as_view(), name='replacement-request-respond'),
    
path('replacement-requests/', views.TaskReplacementRequestListAPIView.as_view(), name='replacement-request-list'),
path('supervision-replacement-requests/', views.SupervisionReplacementRequestListAPIView.as_view(), name='supervision-replacement-request-list'),
path('replacement-requests/<int:pk>/engineer-respond/',
     views.ReplacementRequestEngineerRespondAPIView.as_view(),
     name='replacement-request-engineer-respond'),

     path('tasks/form-options/', views.TaskFormOptionsAPIView.as_view(), name='task-form-options'),
     ]

discipline_urlpatterns = [
    path('discipline-items/', views.DisciplineItemListAPIView.as_view(), name='discipline-item-list'),
    path('projects/<int:project_id>/discipline-trackings/', views.DisciplineTrackingListAPIView.as_view(), name='discipline-tracking-list'),
    path('discipline-trackings/<int:pk>/update/', views.DisciplineTrackingUpdateAPIView.as_view(), name='discipline-tracking-update'),
]

supervision_urlpatterns = [
    path('projects/<int:project_id>/supervision-team/', views.SupervisionTeamAPIView.as_view(), name='supervision-team-list'),
    path('projects/<int:project_id>/supervision-team/assign/', views.AssignEngineerAPIView.as_view(), name='supervision-team-assign'),
    path('projects/<int:project_id>/action-requests/', views.ActionRequestAPIView.as_view(), name='action-request-list-create'),
    path('supervision-team/<int:pk>/update/', views.UpdateEngineerAPIView.as_view(), name='supervision-team-update'),
    path('supervision-team/<int:pk>/remove/', views.RemoveEngineerAPIView.as_view(), name='supervision-team-remove'),
    path('action-requests/<int:pk>/update/', views.ActionRequestUpdateAPIView.as_view(), name='action-request-update'),
]

invoice_urlpatterns = [
    path('financial-dashboard/', views.FinancialDashboardAPIView.as_view(), name='financial-dashboard'),
    path('invoices/payment/', views.InvoicePaymentAPIView.as_view(), name='invoice-payment'),
    path('invoices/create/', views.InvoiceCreateAPIView.as_view(), name='invoice-create'),
    path('invoices/', views.InvoiceListAPIView.as_view(), name='invoice-list'),
    path('invoices/<int:pk>/', views.InvoiceDetailAPIView.as_view(), name='invoice-detail'),
    path('invoices/<int:pk>/update/', views.InvoiceUpdateAPIView.as_view(), name='invoice-update'),
    path('invoices/<int:pk>/delete/', views.InvoiceDeleteAPIView.as_view(), name='invoice-delete'),
    path('projects/<int:project_id>/invoices/statistics/', views.InvoiceStatisticsAPIView.as_view(), name='invoice-statistics'),
    path('projects/<int:project_id>/supervision-invoices/', views.SupervisionInvoiceListCreateAPIView.as_view(), name='supervision-invoice-list-create'),
    path('supervision-invoices/<int:pk>/update/', views.SupervisionInvoiceUpdateAPIView.as_view(), name='supervision-invoice-update'),
    path('supervision-invoices/<int:pk>/delete/', views.SupervisionInvoiceDeleteAPIView.as_view(), name='supervision-invoice-delete'),
    path('projects/<int:project_id>/supervision-invoices/statistics/', views.SupervisionInvoiceStatisticsAPIView.as_view(), name='supervision-invoice-statistics'),
]

chat_urlpatterns = [
    path('chat/conversations/', views.ChatConversationsAPIView.as_view(), name='chat-conversations'),
    path('chat/direct/<int:user_id>/', views.ChatDirectAPIView.as_view(), name='chat-direct'),
    path('chat/general/', views.ChatGeneralAPIView.as_view(), name='chat-general'),
    path('chat/<int:room_id>/messages/', views.ChatMessagesAPIView.as_view(), name='chat-messages'),
    path('chat/<int:room_id>/send/', views.SendMessageAPIView.as_view(), name='chat-send'),
    path('projects/<int:project_id>/chat/', views.ChatRoomAPIView.as_view(), name='chat-room'),
]

notification_urlpatterns = [
    path('notifications/mark-all-read/', views.MarkNotificationReadAPIView.as_view(), name='notification-mark-all-read'),
    path('notifications/', views.NotificationListAPIView.as_view(), name='notification-list'),
    path('notifications/<int:pk>/read/', views.MarkNotificationReadAPIView.as_view(), name='notification-mark-read'),
]

files_urlpatterns = [
    path('projects/<int:project_id>/files/', views.ProjectFilesAPIView.as_view(), name='project-files'),
    path('projects/<int:project_id>/files/upload/', views.UploadProjectFileAPIView.as_view(), name='project-file-upload'),
]

notes_urlpatterns = [
    path('projects/<int:project_id>/notes/', views.ProjectNotesAPIView.as_view(), name='project-notes'),
    path('projects/<int:project_id>/notes/add/', views.AddProjectNoteAPIView.as_view(), name='project-note-add'),
]

logs_urlpatterns = [
    path('external-logs/', views.ExternalLogsAPIView.as_view(), name='external-logs'),
    path('audit-logs/', views.AuditLogAPIView.as_view(), name='audit-logs'),
]

dashboard_urlpatterns = [
    path('dashboard/', views.DashboardAPIView.as_view(), name='dashboard'),
    path('statistics/', views.StatisticsAPIView.as_view(), name='statistics'),
    path('search/', views.GlobalSearchAPIView.as_view(), name='global-search'),
]

project_additions_urlpatterns = [
    path('projects/cards/', views.ProjectCardsAPIView.as_view(), name='project-cards'),
    
    path('projects/<int:pk>/offer-status/', views.OfferStatusAPIView.as_view(), name='project-offer-status'),
    
    path('projects/<int:pk>/contract-file/upload/', views.ContractFileUploadAPIView.as_view(), name='project-contract-upload'),
    
    path('projects/<int:pk>/calculate-planned-dates/', views.PlannedDatesAutoCalculationAPIView.as_view(), name='project-calculate-planned-dates'),
]



client_directory_urlpatterns = [
    path('client-directory/', views.ClientDirectoryAPIView.as_view(), name='client-directory-list'),
    path('client-directory/<int:pk>/', views.ClientDirectoryDetailAPIView.as_view(), name='client-directory-detail'),
]



staff_kpi_urlpatterns = [
    path('staff/kpi-insights/', views.StaffKPIInsightsAPIView.as_view(), name='staff-kpi-insights'),
    path('staff/<int:pk>/kpi-detail/', views.EngineerKPIDetailAPIView.as_view(), name='staff-kpi-detail'),
]



internal_design_review_urlpatterns = [
    path('projects/<int:project_id>/internal-design-review/', views.SupervisionInternalDesignReviewAPIView.as_view(), name='supervision-internal-design-review'),
path('internal-review/active-projects/',
     views.InternalReviewActiveProjectsAPIView.as_view(), name='internal-review-active-projects'),
path('internal-review/discipline-items/',
     views.InternalReviewDisciplineItemsAPIView.as_view(), name='internal-review-discipline-items'),
]



task_additions_urlpatterns = [
    path('tasks/<int:pk>/self-assign/', views.TaskSelfAssignAPIView.as_view(), name='task-self-assign'),
]



global_filter_urlpatterns = [
    path('projects/filter/', views.GlobalFilterBarAPIView.as_view(), name='global-filter-bar'),

]
payment_schedule_urlpatterns = [
    path('projects/<int:project_id>/payment-schedules/', 
         views.PaymentScheduleListCreateAPIView.as_view(), 
         name='payment-schedule-list'),
    path('payment-schedules/<int:pk>/update/', 
         views.PaymentScheduleUpdateAPIView.as_view(), 
         name='payment-schedule-update'),
]

invoice_file_urlpatterns = [
    path('invoices/<int:invoice_id>/files/upload/', 
         views.InvoiceFileUploadAPIView.as_view(), 
         name='invoice-file-upload'),
    path('invoices/<int:invoice_id>/files/', 
         views.InvoiceFileListAPIView.as_view(), 
         name='invoice-file-list'),
]

lifecycle_history_urlpatterns = [
    path('projects/<int:project_id>/lifecycle-history/', 
         views.LifecycleHistoryAPIView.as_view(), 
         name='lifecycle-history'),
]

reports_urlpatterns = [
    path('reports/projects/', 
         views.ProjectReportAPIView.as_view(), 
         name='project-report'),
    path('reports/tasks/', 
         views.TaskReportAPIView.as_view(), 
         name='task-report'),
    path('reports/employees/', 
         views.EmployeeReportAPIView.as_view(), 
         name='employee-report'),
    path('reports/financial/', 
         views.FinancialReportAPIView.as_view(), 
         name='financial-report'),
]
dashboard_charts_urlpatterns = [
    path('dashboard/charts/', 
         views.DashboardChartsAPIView.as_view(), 
         name='dashboard-charts'),
]

urlpatterns = (
    urlpatterns +
    user_urlpatterns +
    client_urlpatterns +
    client_directory_urlpatterns +        
    contractor_urlpatterns +
    project_urlpatterns +
    project_additions_urlpatterns +       
    global_filter_urlpatterns +           
    lifecycle_urlpatterns +
    internal_review_urlpatterns +
    internal_design_review_urlpatterns +  
    tendering_urlpatterns +
    task_urlpatterns +
    task_additions_urlpatterns +          
    discipline_urlpatterns +
    supervision_urlpatterns +
    invoice_urlpatterns +
    staff_kpi_urlpatterns +               
    chat_urlpatterns +
    notification_urlpatterns +
    files_urlpatterns +
    notes_urlpatterns +
    logs_urlpatterns +
    dashboard_urlpatterns+
        payment_schedule_urlpatterns +
    invoice_file_urlpatterns +
    lifecycle_history_urlpatterns +
    reports_urlpatterns +
    dashboard_charts_urlpatterns
)


