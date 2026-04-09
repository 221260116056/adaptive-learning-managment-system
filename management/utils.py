from .models import AuditLog

def _write_audit_log(user, action, details=''):
    if user and getattr(user, 'is_authenticated', False):
        AuditLog.objects.create(user=user, action=action, details=details)
