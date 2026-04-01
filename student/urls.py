from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    path('', views.home_redirect, name='home'),
    path('landing/courses/', views.landing_courses_view, name='landing_courses'),
    path('landing/about/', views.landing_about_view, name='landing_about'),
    path('landing/contact/', views.landing_contact_view, name='landing_contact'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('courses/', views.my_courses, name='my_courses'),
    path('explore/', views.explore_view, name='explore'),
    path('player/module/<int:module_id>/', views.video_player, name='video_player'),
    path('stream/<int:module_id>/<str:filename>', views.stream_dash_video, name='stream_dash_video'),
    path('player/<int:course_id>/', views.player_course_view, name='player_course'),
    path('certificates/', views.certificates_view, name='certificates'),
    path('verify-certificate/<str:cert_id>/', views.verify_certificate, name='verify_certificate'),
    path('download-certificate/<str:cert_id>/', views.download_certificate, name='download_certificate'),
    path('profile/', views.profile_view, name='profile'),
    path('settings/', views.profile_settings, name='settings'),
    path('change-password/', views.change_password, name='change_password'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/delete/<int:notification_id>/', views.delete_notification, name='delete_notification'),
    path('login/', views.student_login_view, name='login'),
    path('signup/', views.student_signup_view, name='signup'),
    path('login/student/', views.student_login_view, name='student_login'),
    path('signup/student/', views.student_signup_view, name='student_signup'),
    
    # Placeholder for teacher panel

    path('enroll/<int:course_id>/', views.enroll_course, name='enroll_course'),
    path('logout/', views.logout_view, name='logout'),

    # APIs
    path('api/watch-event/', views.watch_event_api, name='watch_event_api'),
    path('api/unlock-module/<int:course_id>/', views.unlock_next_module_api, name='unlock_next_module_api'),
    path('api/update-progress/', api_views.update_progress_api, name='update_progress_api'),
    path('api/mark-complete/<int:module_id>/', api_views.mark_complete_api, name='mark_complete_api'),
    path('api/submit-quiz/', api_views.submit_quiz_api, name='submit_quiz_api'),
    path('api/submit-assignment/', views.submit_assignment_api, name='submit_assignment_api'),
    path('video/heartbeat/', views.video_heartbeat, name='video_heartbeat'),
    path('video/replay/', views.video_replay, name='video_replay'),
]

