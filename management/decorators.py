from functools import wraps

from django.shortcuts import redirect


def is_private_admin(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    try:
        return user.studentprofile.role == 'admin'
    except Exception:
        return False


def private_admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_private_admin(request.user):
            return redirect('adminpanel:login')
        return view_func(request, *args, **kwargs)

    return _wrapped
