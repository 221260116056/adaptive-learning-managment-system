from django.urls import path

from . import views

app_name = 'adminpanel'

urlpatterns = [
    path('', views.private_admin_home, name='home'),
    path('login/', views.private_admin_login, name='login'),
    path('logout/', views.private_admin_logout, name='logout'),
    path('profile/', views.private_admin_profile, name='profile'),
    path('dashboard/', views.private_admin_dashboard, name='dashboard'),
    path('users/', views.private_admin_users, name='users'),
    path('requests/', views.private_admin_requests, name='requests'),
    path('certificates/', views.private_admin_certificates, name='certificates'),
    path('certificates/<int:certificate_id>/view/', views.private_admin_certificate_view, name='certificate_view'),
    path('certificates/<int:certificate_id>/revoke/', views.private_admin_revoke_certificate, name='revoke_certificate'),
    path('certificates/<int:certificate_id>/approve/', views.private_admin_approve_certificate, name='approve_certificate'),
    path('certificates/<int:certificate_id>/reissue/', views.private_admin_reissue_certificate, name='reissue_certificate'),
    path('audit-logs/', views.private_admin_audit_logs, name='audit_logs'),
    path('system-config/', views.private_admin_system_config, name='system_config'),
    path('teacher-approvals/', views.private_admin_teacher_approvals, name='teacher_approvals'),
    path('teacher-approvals/approve/<int:user_id>/', views.approve_teacher, name='approve_teacher'),
    path('teacher-approvals/reject/<int:user_id>/', views.reject_teacher, name='reject_teacher'),
]
