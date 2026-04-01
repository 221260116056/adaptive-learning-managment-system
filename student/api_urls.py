from django.urls import path
from . import api_views

urlpatterns = [
    path('watch-event/', api_views.watch_event_api, name='watch_event_api'),
    path('update-progress/', api_views.update_progress_api, name='update_progress_api'),
    path('mark-complete/<int:module_id>/', api_views.mark_complete_api, name='mark_complete_api'),
    path('submit-quiz/', api_views.submit_quiz_api, name='submit_quiz_api'),
    path('certificate/<int:course_id>/', api_views.certificate_api, name='certificate_api'),
]
