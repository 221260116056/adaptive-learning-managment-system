import base64
import csv

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import get_template
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from management.models import AuditLog
from management.decorators import is_private_admin, private_admin_required
from teacher.decorators import admin_required
from student.models import (
    Certificate,
    Course,
    Enrollment,
    IssuedCertificate,
    PlatformSetting,
    QuizAttempt,
    StudentProfile,
    WatchEvent,
    Notification,
)
from student.utils import generate_qr_code


def _write_audit_log(user, action, details=''):
    if user and getattr(user, 'is_authenticated', False):
        AuditLog.objects.create(user=user, action=action, details=details)

@admin_required
def dashboard(request):
    total_students = StudentProfile.objects.filter(role='student').count()
    total_teachers = StudentProfile.objects.filter(role='teacher').count()
    total_courses = Course.objects.count()
    total_enrollments = Enrollment.objects.count()
    
    recent_users = User.objects.order_by('-date_joined')[:5]
    
    context = {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_courses': total_courses,
        'total_enrollments': total_enrollments,
        'recent_users': recent_users,
        'active_menu': 'dashboard'
    }
    return render(request, 'management/dashboard.html', context)

@admin_required
def user_list(request):
    users = User.objects.all().select_related('studentprofile')
    return render(request, 'management/user_list.html', {'users': users, 'active_menu': 'users'})

@admin_required
def course_list(request):
    courses = Course.objects.all().annotate(student_count=Count('enrollment'))
    return render(request, 'management/course_list.html', {'courses': courses, 'active_menu': 'courses'})

@admin_required
def system_stats(request):
    course_engagement = Course.objects.annotate(
        student_count=Count('enrollment', distinct=True),
        module_count=Count('module', distinct=True),
    ).order_by('-student_count', 'title')[:10]
    recent_attempts = QuizAttempt.objects.select_related('student', 'module').order_by('-submitted_at')[:10]
    recent_events = WatchEvent.objects.select_related('student', 'module').order_by('-created_at')[:10]
    active_certificates = IssuedCertificate.objects.filter(is_active=True).count()
    revoked_certificates = IssuedCertificate.objects.filter(is_active=False).count()

    return render(request, 'management/stats.html', {
        'active_menu': 'stats',
        'course_engagement': course_engagement,
        'recent_attempts': recent_attempts,
        'recent_events': recent_events,
        'active_certificates': active_certificates,
        'revoked_certificates': revoked_certificates,
    })


@admin_required
def platform_settings(request):
    config, _ = PlatformSetting.objects.get_or_create(id=1)
    if request.method == 'POST':
        config.video_host = request.POST.get('video_host', '')
        config.signed_url_secret = request.POST.get('signed_url_secret', '')
        config.certificate_signer = request.POST.get('certificate_signer', '')
        config.token_ttl_seconds = request.POST.get('token_ttl_seconds', 300) or 300
        config.attention_monitoring_enabled = request.POST.get('attention_monitoring_enabled') == 'on'
        config.siem_endpoint = request.POST.get('siem_endpoint', '')
        config.blockchain_anchor_enabled = request.POST.get('blockchain_anchor_enabled') == 'on'
        config.save()
        messages.success(request, 'Platform settings updated.')
        return redirect('management:platform_settings')

    return render(request, 'management/settings.html', {
        'active_menu': 'settings',
        'config': config,
    })


@admin_required
def certificate_registry(request):
    certificates = IssuedCertificate.objects.select_related('student', 'course', 'revoked_by').order_by('-issued_at')
    return render(request, 'management/certificates.html', {
        'active_menu': 'certificates',
        'certificates': certificates,
    })


@admin_required
def revoke_certificate(request, certificate_id):
    certificate = get_object_or_404(IssuedCertificate, id=certificate_id)
    if request.method == 'POST' and certificate.is_active:
        certificate.revoke(
            revoked_by=request.user,
            reason=request.POST.get('reason', 'Revoked by admin'),
        )
        messages.success(request, 'Certificate revoked.')
    return redirect('management:certificate_registry')


@admin_required
def export_watch_logs(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="watch_logs.csv"'
    writer = csv.writer(response)
    writer.writerow(['Student', 'Course', 'Module', 'Event Type', 'Current Time', 'Created At'])
    for event in WatchEvent.objects.select_related('student', 'module', 'module__course').order_by('-created_at')[:5000]:
        writer.writerow([
            event.student.username,
            event.module.course.title,
            event.module.title,
            event.event_type,
            event.current_time,
            event.created_at.isoformat(),
        ])
    return response


def private_admin_home(request):
    if is_private_admin(request.user):
        return redirect('adminpanel:dashboard')
    return redirect('adminpanel:login')


def private_admin_login(request):
    if is_private_admin(request.user):
        return redirect('adminpanel:dashboard')

    if request.method == 'POST':
        identity = request.POST.get('identity', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=identity, password=password)

        if user is not None and is_private_admin(user):
            login(request, user)
            _write_audit_log(user, 'Admin login', f'Private admin session started from {request.META.get("REMOTE_ADDR", "unknown IP")}')
            return redirect('adminpanel:dashboard')

        messages.error(request, 'Authentication failed. Use an admin account with valid credentials.')

    return render(request, 'adminpanel/login.html')


@private_admin_required
def private_admin_logout(request):
    _write_audit_log(request.user, 'Admin logout', 'Private admin session closed')
    logout(request)
    return redirect('adminpanel:login')


@private_admin_required
def private_admin_dashboard(request):
    total_users = User.objects.count()
    pending_approvals = StudentProfile.objects.filter(role='teacher', approval_status='pending').count()
    superusers = User.objects.filter(is_superuser=True).count()
    recent_logs = AuditLog.objects.select_related('user')[:8]

    context = {
        'active_menu': 'dashboard',
        'total_users': total_users,
        'pending_approvals': pending_approvals,
        'superusers': superusers,
        'recent_logs': recent_logs,
    }
    return render(request, 'adminpanel/dashboard.html', context)


@private_admin_required
def private_admin_profile(request):
    profile = getattr(request.user, 'studentprofile', None)
    audit_events = AuditLog.objects.filter(user=request.user)[:10]

    return render(request, 'adminpanel/profile.html', {
        'active_menu': 'profile',
        'profile': profile,
        'audit_events': audit_events,
    })


@private_admin_required
def private_admin_users(request):
    if request.method == 'POST':
        target = get_object_or_404(User, id=request.POST.get('user_id'))
        if target == request.user:
            messages.error(request, 'You cannot deactivate your own admin session account.')
        else:
            target.is_active = not target.is_active
            target.save(update_fields=['is_active'])
            action = 'Activated user' if target.is_active else 'Deactivated user'
            _write_audit_log(request.user, action, f'{target.username} ({target.email})')
            messages.success(request, f'{target.username} is now {"active" if target.is_active else "inactive"}.')
        return redirect('adminpanel:users')

    role_filter = request.GET.get('role', '').strip()
    users = User.objects.select_related('studentprofile').all().order_by('-date_joined')
    if role_filter:
        users = users.filter(studentprofile__role=role_filter)

    return render(request, 'adminpanel/users.html', {
        'active_menu': 'users',
        'users': users,
        'role_filter': role_filter,
    })


@private_admin_required
def private_admin_requests(request):
    if request.method == 'POST':
        profile = get_object_or_404(StudentProfile.objects.select_related('user'), id=request.POST.get('profile_id'))
        decision = request.POST.get('decision')

        if decision == 'approve':
            profile.role = 'teacher'
            profile.approval_status = 'approved'
            profile.user.is_active = True
            profile.user.save(update_fields=['is_active'])
            profile.save(update_fields=['role', 'approval_status'])
            _write_audit_log(request.user, 'Approved teacher request', f'{profile.user.username} ({profile.user.email})')
            messages.success(request, f'{profile.user.username} has been approved as a teacher.')
        elif decision == 'reject':
            profile.approval_status = 'rejected'
            profile.user.is_active = False
            profile.user.save(update_fields=['is_active'])
            profile.save(update_fields=['approval_status'])
            _write_audit_log(request.user, 'Rejected teacher request', f'{profile.user.username} ({profile.user.email})')
            messages.success(request, f'{profile.user.username} has been rejected.')
        return redirect('adminpanel:requests')

    pending_profiles = StudentProfile.objects.select_related('user').filter(
        role='teacher',
        approval_status='pending',
    ).order_by('user__date_joined')

    return render(request, 'adminpanel/requests.html', {
        'active_menu': 'requests',
        'pending_profiles': pending_profiles,
    })


@private_admin_required
def private_admin_certificates(request):
    certificates = IssuedCertificate.objects.select_related('student', 'course').all()
    pending_requests = Certificate.objects.filter(status='pending_admin').select_related('user', 'course')
    return render(request, 'adminpanel/certificates.html', {
        'active_menu': 'certificates',
        'certificates': certificates,
        'pending_requests': pending_requests,
    })


@private_admin_required
def private_admin_approve_certificate(request, certificate_id):
    cert = get_object_or_404(Certificate, id=certificate_id, status='pending_admin')
    cert.approve()

    # Create issued certificate record
    issued_cert, created = IssuedCertificate.objects.get_or_create(
        student=cert.user,
        course=cert.course,
        defaults={
            'certificate_number': f'ALMS-{cert.course.id}-{cert.user.id}',
            'verification_hash': IssuedCertificate.build_verification_hash(cert.user.id, cert.course.id, f'ALMS-{cert.course.id}-{cert.user.id}'),
        },
    )

    Notification.objects.get_or_create(
        user=cert.user,
        message=f"Certificate for {cert.course.title} has been approved by admin and is now available.",
    )

    return redirect('adminpanel:certificates')


@private_admin_required
def private_admin_certificate_view(request, certificate_id):
    issued_certificate = get_object_or_404(
        IssuedCertificate.objects.select_related('student', 'course'),
        id=certificate_id,
    )
    certificate, _ = Certificate.objects.get_or_create(
        user=issued_certificate.student,
        course=issued_certificate.course,
        defaults={'certificate_id': issued_certificate.certificate_number},
    )
    verification_url = request.build_absolute_uri(
        reverse('verify_certificate', kwargs={'cert_id': certificate.certificate_id})
    )
    qr_buffer = generate_qr_code(verification_url)
    qr_code_base64 = base64.b64encode(qr_buffer.getvalue()).decode('utf-8')

    return render(request, 'certificates/certificate.html', {
        'user': issued_certificate.student,
        'course': issued_certificate.course,
        'certificate': certificate,
        'qr_code_base64': qr_code_base64,
        'verification_url': verification_url,
    })


@private_admin_required
def private_admin_revoke_certificate(request, certificate_id):
    issued_certificate = get_object_or_404(IssuedCertificate, id=certificate_id)
    if request.method == 'POST' and issued_certificate.is_active:
        reason = request.POST.get('reason', 'Revoked from private admin panel')
        issued_certificate.revoke(revoked_by=request.user, reason=reason)
        _write_audit_log(
            request.user,
            'Revoked certificate',
            f'{issued_certificate.certificate_number} for {issued_certificate.student.username}',
        )
        messages.success(request, 'Certificate revoked successfully.')
    return redirect('adminpanel:certificates')


@private_admin_required
def private_admin_reissue_certificate(request, certificate_id):
    issued_cert = get_object_or_404(IssuedCertificate, id=certificate_id)
    if not issued_cert.is_active:
        # Re-activate in registry
        issued_cert.is_active = True
        issued_cert.revoked_at = None
        issued_cert.revoked_by = None
        issued_cert.revoke_reason = ''
        issued_cert.save()

        # Re-activate student's access status
        from student.models import Certificate
        cert = Certificate.objects.filter(user=issued_cert.student, course=issued_cert.course).first()
        if cert:
            cert.status = 'approved'
            cert.save(update_fields=['status', 'updated_at'])

        _write_audit_log(
            request.user, 
            'Reissued certificate', 
            f'{issued_cert.certificate_number} for {issued_cert.student.username}'
        )
        messages.success(request, f'Certificate {issued_cert.certificate_number} has been successfully reissued.')
    return redirect('adminpanel:certificates')


@private_admin_required
def private_admin_audit_logs(request):
    query = request.GET.get('q', '').strip()
    date_filter = request.GET.get('date', '').strip()

    logs = AuditLog.objects.select_related('user').all()
    if query:
        logs = logs.filter(
            Q(user__email__icontains=query) |
            Q(user__username__icontains=query) |
            Q(action__icontains=query) |
            Q(details__icontains=query)
        )
    if date_filter:
        logs = logs.filter(timestamp__date=date_filter)

    return render(request, 'adminpanel/audit_logs.html', {
        'active_menu': 'audit_logs',
        'logs': logs[:200],
        'query': query,
        'date_filter': date_filter,
    })


@private_admin_required
def private_admin_system_config(request):
    config, _ = PlatformSetting.objects.get_or_create(id=1)
    if request.method == 'POST':
        config.platform_name = request.POST.get('platform_name', 'Adaptive Learning LMS').strip() or 'Adaptive Learning LMS'
        config.maintenance_mode = request.POST.get('maintenance_mode') == 'on'
        config.email_from_address = request.POST.get('email_from_address', '').strip()
        config.smtp_host = request.POST.get('smtp_host', '').strip()
        config.smtp_port = int(request.POST.get('smtp_port') or 587)
        config.video_host = request.POST.get('video_host', '').strip()
        config.certificate_signer = request.POST.get('certificate_signer', '').strip()
        config.save()
        _write_audit_log(request.user, 'Updated system config', f'Platform name set to {config.platform_name}')
        messages.success(request, 'System configuration updated.')
        return redirect('adminpanel:system_config')

    return render(request, 'adminpanel/system_config.html', {
        'active_menu': 'system_config',
        'config': config,
    })

@private_admin_required
def private_admin_teacher_approvals(request):
    if not request.user.is_superuser:
        messages.error(request, 'Access denied.')
        return redirect('adminpanel:dashboard')
    
    pending_teachers = StudentProfile.objects.filter(role='teacher', approval_status='pending').select_related('user')
    
    return render(request, 'adminpanel/teacher_approvals.html', {
        'active_menu': 'teacher_approvals',
        'pending_teachers': pending_teachers,
    })

@private_admin_required
def approve_teacher(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, 'Access denied.')
        return redirect('adminpanel:dashboard')
    
    user = get_object_or_404(User, id=user_id)
    profile = get_object_or_404(StudentProfile, user=user, role='teacher')
    profile.approval_status = 'approved'
    profile.save()
    _write_audit_log(request.user, 'Approved teacher', f'Approved teacher {user.username}')
    messages.success(request, f'Teacher {user.username} has been approved.')
    return redirect('adminpanel:teacher_approvals')

@private_admin_required
def reject_teacher(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, 'Access denied.')
        return redirect('adminpanel:dashboard')
    
    user = get_object_or_404(User, id=user_id)
    profile = get_object_or_404(StudentProfile, user=user, role='teacher')
    profile.approval_status = 'rejected'
    profile.save()
    _write_audit_log(request.user, 'Rejected teacher', f'Rejected teacher {user.username}')
    messages.success(request, f'Teacher {user.username} has been rejected.')
    return redirect('adminpanel:teacher_approvals')
