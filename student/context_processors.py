from .models import Notification, StudentProfile, Certificate, Course, AssignmentSubmission

def notification_processor(request):
    """
    Context processor to provide unread notification count and latest notifications
    to all templates (used in navbar and sidebars).
    """
    data = {
        'unread_notifications_count': 0,
        'latest_notifications': [],
        'admin_pending_teachers_count': 0,
        'admin_pending_certificates_count': 0,
        'teacher_pending_certificates_count': 0,
        'teacher_pending_assignments_count': 0,
    }

    if request.user.is_authenticated:
        # Student Notifications
        data['unread_notifications_count'] = Notification.objects.filter(user=request.user, is_read=False).count()
        data['latest_notifications'] = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]

        # Admin Counts
        if request.user.is_staff or request.user.is_superuser:
            data['admin_pending_teachers_count'] = StudentProfile.objects.filter(role='teacher', approval_status='pending').count()
            data['admin_pending_certificates_count'] = Certificate.objects.filter(status='pending_admin').count()

        # Teacher Counts
        if hasattr(request.user, 'studentprofile') and request.user.studentprofile.role == 'teacher':
            data['teacher_pending_certificates_count'] = Certificate.objects.filter(
                course__teacher=request.user, 
                status='pending_teacher'
            ).count()
            data['teacher_pending_assignments_count'] = AssignmentSubmission.objects.filter(
                module__course__teacher=request.user, 
                status='pending'
            ).count()

    return data
