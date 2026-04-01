from django.urls import path
from . import views

app_name = 'teacher'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/refresh/', views.refresh_moodle_sync, name='refresh_sync'),
    
    path('courses/', views.course_list, name='course_list'),
    path('courses/create/', views.course_create, name='course_create'),
    path('courses/<int:course_id>/edit/', views.course_edit, name='course_edit'),
    path('courses/<int:course_id>/sync/', views.sync_course_to_moodle, name='sync_course_to_moodle'),
    path('courses/<int:course_id>/students/', views.course_students, name='course_students'),
    
    path('lessons/upload/', views.upload_lesson, name='upload_lesson'),
    path('courses/<int:course_id>/modules/', views.course_modules, name='course_modules'),
    path('courses/<int:course_id>/modules/reorder/', views.reorder_modules, name='reorder_modules'),
    path('modules/create/', views.create_module, name='create_module'),
    path('modules/<int:module_id>/edit/', views.edit_module, name='edit_module'),
    path('videos/', views.video_manager, name='video_manager'),
    path('settings/', views.profile_settings, name='settings'),
    path('courses/<int:course_id>/delete/', views.delete_course, name='delete_course'),
    path('courses/<int:course_id>/toggle-publish/', views.toggle_publish, name='toggle_publish'),

    # Certificate approval workflow
    path('certificates/', views.teacher_certificates, name='teacher_certificates'),
    path('certificates/<int:certificate_id>/approve/', views.teacher_approve_certificate, name='teacher_approve_certificate'),
    path('certificates/<int:certificate_id>/reject/', views.teacher_reject_certificate, name='teacher_reject_certificate'),

    # Teacher preview route for module player bypassing student enrollment gating
    path('module/<int:module_id>/preview/', views.preview_module, name='preview_module'),

    # Assignment review
    path('assignments/review/', views.review_assignments, name='review_assignments'),
    path('assignments/review/<int:submission_id>/', views.review_submission_api, name='review_submission_api'),
]
