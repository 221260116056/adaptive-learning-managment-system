from .models import Notification

def notification_processor(request):
    """
    Context processor to provide unread notification count and latest notifications
    to all templates (used in navbar).
    """
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        latest_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        return {
            'unread_notifications_count': unread_count,
            'latest_notifications': latest_notifications
        }
    return {
        'unread_notifications_count': 0,
        'latest_notifications': []
    }
