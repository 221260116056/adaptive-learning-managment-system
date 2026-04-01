from django.urls import path
from . import views

app_name = 'management'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('users/', views.user_list, name='user_list'),
    path('courses/', views.course_list, name='course_list'),
    path('stats/', views.system_stats, name='system_stats'),
    path('settings/', views.platform_settings, name='platform_settings'),
    path('certificates/', views.certificate_registry, name='certificate_registry'),
    path('certificates/<int:certificate_id>/revoke/', views.revoke_certificate, name='revoke_certificate'),
    path('exports/watch-logs.csv', views.export_watch_logs, name='export_watch_logs'),
]
