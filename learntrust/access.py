from functools import wraps

from django.shortcuts import redirect


def get_user_role(user):
    if not getattr(user, 'is_authenticated', False):
        return None
    try:
        return user.studentprofile.role
    except Exception:
        return None


def redirect_for_role(user):
    role = get_user_role(user)
    if role == 'teacher':
        return redirect('teacher:dashboard')
    if role == 'admin':
        return redirect('management:dashboard')
    return redirect('dashboard')


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            role = get_user_role(request.user)
            if role in allowed_roles:
                return view_func(request, *args, **kwargs)
            return redirect_for_role(request.user)

        return _wrapped_view

    return decorator


student_required = role_required('student')
teacher_required = role_required('teacher')
admin_required = role_required('admin')
