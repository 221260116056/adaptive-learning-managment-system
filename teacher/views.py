import os
import json

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from .decorators import teacher_required
from student.models import Course, CourseCertificateTemplate, Enrollment, QuizAttempt, Module, StudentProfile, WatchEvent, Certificate, Notification, AssignmentSubmission, Quiz, Question, ModuleProgress
from django.db.models import Count, Max, Q
from django.utils import timezone
from .moodle_manager import MoodleTeacherManager
from .video_processing import convert_to_dash, trigger_dash_transcode
from django.conf import settings


def _ensure_moodle_course(course):
    if course.moodle_course_id:
        return course.moodle_course_id

    mm = MoodleTeacherManager()
    result = mm.create_course(
        full_name=course.title,
        short_name=course.short_name or course.title[:20],
        category_id=course.category_id,
        visible=1 if course.visibility else 0,
        start_date=course.start_date,
    )
    moodle_id = result.get('id') if isinstance(result, dict) else None
    if moodle_id:
        course.moodle_course_id = moodle_id
        course.moodle_sync_status = 'synced'
        course.moodle_last_error = ''
        course.save(update_fields=['moodle_course_id', 'moodle_sync_status', 'moodle_last_error'])
        return moodle_id

    course.moodle_sync_status = 'failed'
    course.moodle_last_error = result.get('error', 'Unknown Moodle sync error') if isinstance(result, dict) else 'Unknown Moodle sync error'
    course.save(update_fields=['moodle_sync_status', 'moodle_last_error'])
    return None

@teacher_required
def dashboard(request):
    courses = Course.objects.filter(teacher=request.user).annotate(
        student_count=Count('enrollment', distinct=True)
    ).order_by('-created_at')
    course_list_recent = courses[:5]
    
    total_lessons = Module.objects.filter(course__teacher=request.user).count()
    total_students = Enrollment.objects.filter(course__teacher=request.user).values('student').distinct().count()
    total_watch_events = WatchEvent.objects.filter(module__course__teacher=request.user).count()
    total_quiz_attempts = QuizAttempt.objects.filter(module__course__teacher=request.user).count()
    
    context = {
        'courses': courses,
        'course_list_recent': course_list_recent,
        'course_count': courses.count(),
        'total_lessons': total_lessons,
        'total_students': total_students,
        'total_watch_events': total_watch_events,
        'total_quiz_attempts': total_quiz_attempts,
        'active_menu': 'dashboard'
    }
    return render(request, 'teacher/dashboard.html', context)

@teacher_required
def refresh_moodle_sync(request):
    # Logic to manually pull updates from Moodle if needed
    return redirect('teacher:dashboard')

@teacher_required
def course_list(request):
    courses = Course.objects.filter(teacher=request.user).annotate(student_count=Count('enrollment'))
    return render(request, 'teacher/course_list.html', {'courses': courses, 'active_menu': 'courses'})

@teacher_required
def course_create(request):
    mm = MoodleTeacherManager()
    categories = mm.get_categories()
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        short_name = request.POST.get('short_name') or full_name[:20]
        category_id = int(request.POST.get('category_id', 1))
        visibility = request.POST.get('visibility') == '1'
        start_date_str = request.POST.get('start_date')
        
        start_date = None
        if start_date_str:
            try:
                start_date = timezone.datetime.fromisoformat(start_date_str)
                if timezone.is_naive(start_date):
                    start_date = timezone.make_aware(start_date, timezone.get_current_timezone())
            except ValueError:
                start_date = None
        
        # 1. Create in Django
        course = Course.objects.create(
            title=full_name,
            short_name=short_name,
            category_id=category_id,
            visibility=visibility,
            start_date=start_date,
            teacher=request.user,
            price=float(request.POST.get('price', 0.0)),
            certificate_signer_name=request.POST.get('signer_name', "Coordinator / Authority"),
            certificate_signer_title=request.POST.get('signer_title', "Head of Department"),
            certificate_auto_issue=request.POST.get('certificate_auto_issue') == 'on',
        )
        if request.FILES.get('thumbnail'):
            course.thumbnail = request.FILES['thumbnail']
            course.save(update_fields=['thumbnail'])
        CourseCertificateTemplate.objects.create(
            course=course,
            signer_name=request.POST.get('signer_name', 'Coordinator / Authority'),
            signer_title=request.POST.get('signer_title', 'Head of Department'),
            qr_verify_base_url=request.build_absolute_uri('/certificates/'),
            auto_issue=course.certificate_auto_issue,
        )
        
        # 2. Attempt Moodle sync — auto-suffix short_name if conflict
        moodle_id = None
        moodle_short_name = short_name
        for attempt in range(5):  # try up to 5 suffix variants
            result = mm.create_course(
                full_name=full_name,
                short_name=moodle_short_name,
                category_id=category_id,
                visible=1 if visibility else 0,
                start_date=start_date
            )
            moodle_id = result.get('id') if isinstance(result, dict) else None
            if moodle_id:
                break
            error_msg = result.get('error', '') if isinstance(result, dict) else ''
            if 'short name' in error_msg.lower() or 'already used' in error_msg.lower():
                import time
                moodle_short_name = f"{short_name[:15]}_{int(time.time()) % 10000}"
            else:
                break  # non-recoverable Moodle error
        
        if moodle_id:
            course.moodle_course_id = moodle_id
            course.moodle_sync_status = 'synced'
            course.moodle_last_error = ''
            course.save(update_fields=['moodle_course_id', 'moodle_sync_status', 'moodle_last_error'])
            messages.success(request, 'Course created in Django and synced to Moodle.')
        else:
            course.moodle_sync_status = 'failed'
            course.moodle_last_error = result.get('error', 'Unknown Moodle sync error') if isinstance(result, dict) else 'Unknown Moodle sync error'
            course.save(update_fields=['moodle_sync_status', 'moodle_last_error'])
            messages.warning(
                request,
                f"Course was created only in Django. Moodle sync failed: {course.moodle_last_error}",
            )
            
        return redirect('teacher:course_list')
    
    return render(request, 'teacher/course_form.html', {
        'active_menu': 'courses',
        'categories': categories if isinstance(categories, list) else [],
        'certificate_template': None,
    })

@teacher_required
def course_edit(request, course_id):
    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    mm = MoodleTeacherManager()
    categories = mm.get_categories()
    certificate_template, _ = CourseCertificateTemplate.objects.get_or_create(course=course)
    
    if request.method == 'POST':
        course.title = request.POST.get('full_name')
        course.short_name = request.POST.get('short_name')
        course.category_id = int(request.POST.get('category_id', 1))
        course.visibility = request.POST.get('visibility') == '1'
        course.price = float(request.POST.get('price', 0.0))
        course.certificate_auto_issue = request.POST.get('certificate_auto_issue') == 'on'
        if request.FILES.get('thumbnail'):
            course.thumbnail = request.FILES['thumbnail']
        course.certificate_signer_name = request.POST.get('signer_name', course.certificate_signer_name)
        course.certificate_signer_title = request.POST.get('signer_title', course.certificate_signer_title)
        course.save()
        return redirect('teacher:course_list')
    
    return render(request, 'teacher/course_form.html', {
        'course': course, 
        'categories': categories if isinstance(categories, list) else [],
        'active_menu': 'courses',
        'certificate_template': certificate_template,
    })

@teacher_required
def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    if request.method == 'POST':
        title = course.title
        # 1. Delete from Moodle first (if synced)
        if course.moodle_course_id:
            mm = MoodleTeacherManager()
            result = mm.delete_course(course.moodle_course_id)
            if isinstance(result, dict) and result.get('error'):
                # If delete fails, at least hide the course in Moodle
                hide_result = mm.update_course_visibility(course.moodle_course_id, False)
                if isinstance(hide_result, dict) and hide_result.get('error'):
                    messages.warning(
                        request,
                        f'Course "{title}" deleted from Django, but Moodle deletion failed and could not be hidden: {result["error"]}'
                    )
                else:
                    messages.warning(
                        request,
                        f'Course "{title}" deleted from Django. Moodle deletion failed, so it was hidden instead.'
                    )
            else:
                messages.success(request, f'Course "{title}" deleted from Django and Moodle.')
        else:
            messages.success(request, f'Course "{title}" has been deleted.')
        # 2. Delete from Django
        course.delete()
    return redirect('teacher:dashboard')

@teacher_required
def toggle_publish(request, course_id):
    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    course.is_published = not course.is_published
    course.save(update_fields=['is_published'])
    status = 'published' if course.is_published else 'unpublished'
    if course.moodle_course_id:
        mm = MoodleTeacherManager()
        mm.update_course_visibility(course.moodle_course_id, course.is_published)
    messages.success(request, f'Course "{course.title}" has been {status}.')
    return redirect('teacher:dashboard')



def _sync_module_to_moodle(module):
    """
    Placeholder: Module sync to Moodle is disabled for stability. 
    Lessons are handled exclusively by the Django LMS.
    """
    return {'status': 'skipped', 'message': 'Module sync disabled for stability'}

@teacher_required
def sync_course_to_moodle(request, course_id):
    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    moodle_id = _ensure_moodle_course(course)
    
    if not moodle_id:
        messages.error(request, f'Failed to sync "{course.title}" to Moodle: {course.moodle_last_error}')
        return redirect('teacher:dashboard')

    # Hybrid Solution: Add a single "Start Learning" URL in Moodle
    mm = MoodleTeacherManager()
    section_num = 1
    
    # 1. Create section to hold the link
    mm.create_section(moodle_id, section_num, "Official Course Content")

    # 2. Add the redirect URL using core_course_create_modules logic
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
    player_url = f"{site_url}/student/player/{course.id}/"
    
    sync_res = mm.create_url(moodle_id, section_num, "START LEARNING (Launch LearnTrust Player)", player_url)

    if isinstance(sync_res, dict) and 'error' in sync_res:
         messages.warning(request, f'Course synced, but failed to add the "Start Learning" button: {sync_res["error"]}. Your Moodle may need the core_course_create_modules function enabled.')
    else:
         messages.success(request, f'"{course.title}" synced successfully! Moodle now contains a "Start Learning" link to your Django LMS.')
    
    return redirect('teacher:dashboard')

@teacher_required
def upload_lesson(request):
    courses = Course.objects.filter(teacher=request.user)

    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        course = get_object_or_404(Course, id=course_id, teacher=request.user)

        title = request.POST.get('title')
        module_type = request.POST.get('module_type')
        next_order = (Module.objects.filter(course=course).aggregate(Max('order'))['order__max'] or 0) + 1

        module = Module.objects.create(
            course=course,
            title=title,
            type=module_type,
            order=next_order,
            is_published=True
        )

        # Create specific module details
        if module_type == 'video':
            video_file = request.FILES.get('video_file')
            
            if not video_file:
                module.delete()
                messages.error(request, 'Video file is required for video modules.')
                return redirect('teacher:upload_lesson')

            # Basic extension validation
            ext = os.path.splitext(video_file.name)[1].lower()
            if ext not in ['.mp4', '.webm', '.ogg']:
                module.delete()
                messages.error(request, 'Invalid video format. Only MP4, WebM, and OGG are supported.')
                return redirect('teacher:upload_lesson')
            
            module.video_file = video_file
            module.save()
            
            trigger_dash_transcode(module.id)
            messages.success(request, 'Video module uploaded and queued for processing.')

        elif module_type == 'theory':
            content = request.POST.get('theory_content', '')
            file = request.FILES.get('pdf_file') or request.FILES.get('image_file')
            
            module.content = content
            if file:
                module.file = file
            module.save()
            
            messages.success(request, 'Theory module created successfully.')

        elif module_type == 'quiz':
            # Create the Quiz container
            quiz = Quiz.objects.create(module=module)
            
            # Fetch dynamic lists from the form
            q_texts = request.POST.getlist('quiz_question_text[]')
            q_a = request.POST.getlist('quiz_option_a[]')
            q_b = request.POST.getlist('quiz_option_b[]')
            q_c = request.POST.getlist('quiz_option_c[]')
            q_d = request.POST.getlist('quiz_option_d[]')
            q_correct = request.POST.getlist('quiz_correct_answer[]')

            # Loop through and create Questions
            for i in range(len(q_texts)):
                if q_texts[i].strip():
                    Question.objects.create(
                        quiz=quiz,
                        text=q_texts[i],
                        option_a=q_a[i] if i < len(q_a) else "",
                        option_b=q_b[i] if i < len(q_b) else "",
                        option_c=q_c[i] if i < len(q_c) else "",
                        option_d=q_d[i] if i < len(q_d) else "",
                        correct_answer=q_correct[i] if i < len(q_correct) else "A",
                        order=i
                    )
            
            messages.success(request, 'Quiz module created with multiple questions.')


        elif module_type == 'assignment':
            assignment_file = request.FILES.get('assignment_file')
            if assignment_file:
                module.assignment_task_file = assignment_file
            module.save()
            messages.success(request, 'Assignment module created successfully.')

        else:
            messages.error(request, 'Invalid module type')
            module.delete()
            return redirect('teacher:upload_lesson')

        # Module sync to Moodle is disabled for stability
        messages.success(request, 'Module created successfully in LearnTrust.')
        return redirect('teacher:course_modules', course_id=course.id)

    return render(request, 'teacher/upload_lesson.html', {
        'courses': courses,
        'active_menu': 'upload_lesson'
    })

@teacher_required
def video_manager(request):
    modules = Module.objects.filter(course__teacher=request.user).filter(
        Q(type='video')
    )
    return render(request, 'teacher/video_manager.html', {
        'modules': modules,
        'active_menu': 'video_manager'
    })

@teacher_required
def course_modules(request, course_id):
    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    modules = Module.objects.filter(course=course).order_by('order')
    return render(request, 'teacher/course_modules.html', {
        'course': course,
        'modules': modules,
        'active_menu': 'course_modules'
    })

from django.http import JsonResponse

@teacher_required
def reorder_modules(request, course_id):
    if request.method == 'POST':
        course = get_object_or_404(Course, id=course_id, teacher=request.user)
        try:
            data = json.loads(request.body)
            module_ids = data.get('module_ids', [])
            
            for index, m_id in enumerate(module_ids, start=1):
                Module.objects.filter(id=m_id, course=course).update(order=index)
                
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'invalid method'}, status=405)

@teacher_required
def teacher_certificates(request):
    certificates = Certificate.objects.filter(
        course__teacher=request.user,
        status__in=['pending_teacher', 'pending_admin']
    ).select_related('user', 'course')
    return render(request, 'teacher/certificates.html', {
        'certificates': certificates,
        'active_menu': 'certificates'
    })

@teacher_required
def teacher_approve_certificate(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id, course__teacher=request.user)
    if certificate.status == 'pending_teacher':
        certificate.status = 'pending_admin'
        certificate.save(update_fields=['status', 'updated_at'])
        
        Notification.objects.get_or_create(
            user=certificate.user,
            message=f"Your certificate request for {certificate.course.title} has been approved by the teacher and is now awaiting final admin verification.",
            link=reverse('certificates')
        )
        messages.success(request, f"Certificate request for {certificate.user.username} approved and sent to admin for final issuance.")
            
        Notification.objects.get_or_create(
            user=certificate.user,
            message=f"Congratulations! Your certificate for {certificate.course.title} has been issued.",
            link=reverse('certificates')
        )
    return redirect('teacher:teacher_certificates')

@teacher_required
def teacher_reject_certificate(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id, course__teacher=request.user)
    if certificate.status in ['pending_teacher', 'pending_admin']:
        certificate.status = 'rejected'
        certificate.save(update_fields=['status', 'updated_at'])
        Notification.objects.get_or_create(
            user=certificate.user,
            message=f"Certificate for {certificate.course.title} has been rejected by teacher.",
            link=reverse('certificates')
        )
    return redirect('teacher:teacher_certificates')

@teacher_required
def preview_module(request, module_id):
    from student.moodle_api import get_module_content, get_course_modules
    from student.views import _ensure_module_quiz, _quiz_payload
    from student.models import ModuleProgress

    module = get_object_or_404(Module, id=module_id, course__teacher=request.user)

    # Provide a direct instructor preview path without requiring enrollment.
    moodle_module = get_module_content(module.order % 100)

    # Setup media/embedding state
    is_youtube = False
    is_hls = False
    is_external_page = False
    embed_url = None
    dash_manifest = module.dash_manifest or ""

    if dash_manifest:
        manifest_path = os.path.join(settings.MEDIA_ROOT, dash_manifest)
        if not os.path.exists(manifest_path):
            dash_manifest = ""

    if module.type == 'video':
        if module.video_file:
            embed_url = module.video_file.url
        elif dash_manifest:
            embed_url = f"/media/{dash_manifest}"

    if embed_url and ('youtube.com' in embed_url or 'youtu.be' in embed_url):
        is_youtube = True
        if 'youtu.be/' in embed_url:
            video_id = embed_url.split('youtu.be/')[1].split('?')[0]
            embed_url = f"https://www.youtube.com/embed/{video_id}"
        elif 'youtube.com/watch?v=' in embed_url:
            video_id = embed_url.split('v=')[1].split('&')[0]
            embed_url = f"https://www.youtube.com/embed/{video_id}"
    elif embed_url and embed_url.lower().endswith('.m3u8'):
        is_hls = True
    elif embed_url and not any(ext in embed_url.lower() for ext in ['.mp4', '.webm', '.ogg']):
        is_external_page = True

    all_modules = Module.objects.filter(course=module.course).order_by('order')
    course_modules = get_course_modules(module.course.moodle_course_id) if module.course.moodle_course_id else []

    module_progress, _ = ModuleProgress.objects.get_or_create(user=request.user, module=module)
    total_modules = all_modules.count()
    completed_modules = ModuleProgress.objects.filter(user=request.user, module__course=module.course, is_completed=True).count()
    course_progress_percent = int((completed_modules / total_modules) * 100) if total_modules else 0
    quiz = _ensure_module_quiz(module)
    next_module = all_modules.filter(order__gt=module.order).first()

    return render(request, 'student/video_player.html', {
        'module': module,
        'all_modules': all_modules,
        'last_sequence_number': 0,
        'is_youtube': is_youtube,
        'is_hls': is_hls,
        'is_external_page': is_external_page,
        'embed_url': embed_url,
        'moodle_module': moodle_module,
        'course_modules': course_modules,
        'is_locked': False,
        'lock_reason': '',
        'progress': None,
        'module_progress': module_progress,
        'module_progress_percent': int(module_progress.video_progress),
        'attempts_remaining': 3,
        'course_progress_percent': course_progress_percent,
        'completed_modules_count': completed_modules,
        'total_modules_count': total_modules,
        'quiz_payload': _quiz_payload(quiz, request.user),
        'next_module_url': reverse('teacher:preview_module', kwargs={'module_id': next_module.id}) if next_module else reverse('teacher:course_modules', kwargs={'course_id': module.course.id}),
        'allow_seek': True,
        'disable_fast_forward': module.video_details.disable_fast_forward if hasattr(module, 'video_details') and module.video_details else True,
        'enable_checkpoints': module.video_details.enable_checkpoints if hasattr(module, 'video_details') and module.video_details else False,
        'checkpoint_interval': module.video_details.checkpoint_interval if hasattr(module, 'video_details') and module.video_details else 30,
        'min_watch_percent': module.video_details.min_watch_percent if hasattr(module, 'video_details') and module.video_details else 80,
        'dash_manifest': dash_manifest,
        'preview': True,
    })

@teacher_required
def profile_settings(request):
    profile, created = StudentProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name')
        request.user.last_name = request.POST.get('last_name')
        request.user.email = request.POST.get('email')
        request.user.save()
        
        profile.expertise = request.POST.get('expertise')
        profile.auto_sync_enabled = request.POST.get('auto_sync') == 'on'
        
        if 'profile_image' in request.FILES:
            profile.profile_image = request.FILES['profile_image']
            
        profile.save()
        return redirect('teacher:settings')
        
    return render(request, 'teacher/settings.html', {
        'profile': profile,
        'active_menu': 'settings'
    })

@teacher_required
def course_students(request, course_id):
    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    enrollments = Enrollment.objects.filter(course=course).select_related('student')
    
    # Real-time progress calculation
    total_modules = Module.objects.filter(course=course).count()
    for enrollment in enrollments:
        completed_count = ModuleProgress.objects.filter(
            user=enrollment.student,
            module__course=course,
            is_completed=True
        ).count()
        if total_modules > 0:
            enrollment.progress_percent = int((completed_count / total_modules) * 100)
        else:
            enrollment.progress_percent = 0
            
    return render(request, 'teacher/course_students.html', {
        'course': course, 
        'enrollments': enrollments, 
        'active_menu': 'courses'
    })

@teacher_required
def student_course_detail(request, course_id, student_id):
    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    student = get_object_or_404(User, id=student_id)
    enrollment = get_object_or_404(Enrollment, student=student, course=course)
    
    modules = Module.objects.filter(course=course).order_by('order')
    module_progress = ModuleProgress.objects.filter(user=student, module__course=course)
    
    # Map progress to modules for easy lookup
    progress_map = {mp.module_id: mp for mp in module_progress}
    
    detailed_modules = []
    completed_count = 0
    for m in modules:
        progress = progress_map.get(m.id)
        is_completed = progress.is_completed if progress else False
        if is_completed:
            completed_count += 1
            
        detailed_modules.append({
            'module': m,
            'is_completed': is_completed,
            'video_progress': progress.video_progress if progress else 0,
            'updated_at': progress.updated_at if progress else None
        })
        
    total_modules = modules.count()
    overall_progress = int((completed_count / total_modules) * 100) if total_modules > 0 else 0
    
    # Quiz attempts and scores
    quiz_attempts = QuizAttempt.objects.filter(student=student, module__course=course).select_related('module').order_by('-submitted_at')
    has_passed_any_quiz = quiz_attempts.filter(passed=True).exists()
    
    # Assignment submissions
    assignments = AssignmentSubmission.objects.filter(student=student, module__course=course).select_related('module').order_by('-submitted_at')
    
    return render(request, 'teacher/student_course_detail.html', {
        'course': course,
        'student': student,
        'enrollment': enrollment,
        'detailed_modules': detailed_modules,
        'overall_progress': overall_progress,
        'completed_count': completed_count,
        'total_modules': total_modules,
        'quiz_attempts': quiz_attempts,
        'has_passed_any_quiz': has_passed_any_quiz,
        'assignments': assignments,
        'active_menu': 'courses'
    })

@login_required
def create_module(request):
    courses = Course.objects.filter(teacher=request.user)

    if request.method == "POST":
        module = Module.objects.create(
            course_id=request.POST.get("course"),
            title=request.POST.get("title"),
            type=request.POST.get("type"),
        )

        # VIDEO
        if module.type == "video":
            video_file = request.FILES.get("video")
            if video_file:
                module.video_file = video_file
                module.save()
                # Trigger asynchronous transcoding to prevent timeout
                trigger_dash_transcode(module.id)
                messages.success(request, "Video module created and processing in background.")
            else:
                module.delete()
                messages.error(request, "Video file is required.")
                return redirect("teacher:create_module")

        # THEORY
        elif module.type == "theory":
            module.content = request.POST.get("content")
            if request.FILES.get("file"):
                module.file = request.FILES.get("file")
            module.save()
            messages.success(request, "Theory module created successfully.")

        # QUIZ
        elif module.type == "quiz":
            quiz = Quiz.objects.create(module=module)
            q_texts = request.POST.getlist('quiz_question_text[]')
            q_a = request.POST.getlist('quiz_option_a[]')
            q_b = request.POST.getlist('quiz_option_b[]')
            q_c = request.POST.getlist('quiz_option_c[]')
            q_d = request.POST.getlist('quiz_option_d[]')
            q_correct = request.POST.getlist('quiz_correct_answer[]')

            for i in range(len(q_texts)):
                if q_texts[i].strip():
                    Question.objects.create(
                        quiz=quiz,
                        text=q_texts[i],
                        option_a=q_a[i] if i < len(q_a) else "",
                        option_b=q_b[i] if i < len(q_b) else "",
                        option_c=q_c[i] if i < len(q_c) else "",
                        option_d=q_d[i] if i < len(q_d) else "",
                        correct_answer=q_correct[i] if i < len(q_correct) else "A",
                        order=i
                    )
            module.save()
            messages.success(request, "Quiz module created successfully.")

        # ASSIGNMENT
        elif module.type == "assignment":
            if request.FILES.get("assignment_file"):
                module.assignment_task_file = request.FILES.get("assignment_file")
            module.save()
            messages.success(request, "Assignment module created successfully.")

        else:
            module.save()
            messages.success(request, "Module created successfully.")
            
        return redirect("teacher:course_modules", course_id=module.course_id)

    return render(request, "teacher/create_module.html", {
        "courses": courses,
        "active_menu": "modules"
    })

@login_required
def edit_module(request, module_id):
    module = get_object_or_404(Module, id=module_id, course__teacher=request.user)

    if request.method == "POST":
        module.title = request.POST.get("title")

        # VIDEO RE-UPLOAD
        if module.type == "video":
            video_file = request.FILES.get("video")
            if video_file:
                # Delete old file
                if module.video_file:
                    module.video_file.delete()

                module.video_file = video_file
                module.save()

                # Async processing to prevent UI lockup
                trigger_dash_transcode(module.id)
                messages.success(request, "Video file updated and processing in background.")
            elif module.video_file and not module.dash_manifest:
                # If no new upload but streaming chunks are missing, rebuild in background.
                trigger_dash_transcode(module.id)
            elif not module.video_file:
                messages.error(request, "Video module must have a video file.")

        # THEORY
        elif module.type == "theory":
            module.content = request.POST.get("content")

            if request.FILES.get("file"):
                if module.file:
                    module.file.delete()
                module.file = request.FILES.get("file")

        # QUIZ
        elif module.type == "quiz":
            quiz, _ = Quiz.objects.get_or_create(module=module)
            # Clear existing questions for sync
            quiz.questions.all().delete()
            
            q_texts = request.POST.getlist('quiz_question_text[]')
            q_a = request.POST.getlist('quiz_option_a[]')
            q_b = request.POST.getlist('quiz_option_b[]')
            q_c = request.POST.getlist('quiz_option_c[]')
            q_d = request.POST.getlist('quiz_option_d[]')
            q_correct = request.POST.getlist('quiz_correct_answer[]')

            for i in range(len(q_texts)):
                if q_texts[i].strip():
                    Question.objects.create(
                        quiz=quiz,
                        text=q_texts[i],
                        option_a=q_a[i] if i < len(q_a) else "",
                        option_b=q_b[i] if i < len(q_b) else "",
                        option_c=q_c[i] if i < len(q_c) else "",
                        option_d=q_d[i] if i < len(q_d) else "",
                        correct_answer=q_correct[i] if i < len(q_correct) else "A",
                        order=i
                    )


        # ASSIGNMENT
        elif module.type == "assignment":
            if request.FILES.get("assignment_file"):
                if module.assignment_task_file:
                    module.assignment_task_file.delete()
                module.assignment_task_file = request.FILES.get("assignment_file")

        module.save()
        return redirect("teacher:course_modules", course_id=module.course_id)

    quiz = module.quizzes.first()
    questions = list(quiz.questions.all().order_by('order').values(
        'text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer'
    )) if quiz else []

    return render(request, "teacher/edit_module.html", {
        "module": module,
        "questions": questions,
        "active_menu": "modules"
    })


@teacher_required
def delete_module(request, module_id):
    module = get_object_or_404(Module, id=module_id, course__teacher=request.user)
    course_id = module.course_id
    title = module.title
    
    if request.method == 'POST':
        module.delete()
        messages.success(request, f'Module "{title}" has been deleted.')
    else:
        messages.error(request, "Invalid request method for deletion.")
        
    return redirect('teacher:course_modules', course_id=course_id)


@teacher_required
def review_assignments(request):
    # This view lists all submissions that need review for courses owned by this teacher
    submissions = AssignmentSubmission.objects.filter(
        module__course__teacher=request.user
    ).order_by('-submitted_at')
    
    return render(request, 'teacher/assignment_review.html', {
        'submissions': submissions,
        'active_menu': 'assignments'
    })

@teacher_required
def review_submission_api(request, submission_id):
    if request.method == 'POST':
        submission = get_object_or_404(AssignmentSubmission, id=submission_id, module__course__teacher=request.user)
        
        status = request.POST.get('status')
        feedback = request.POST.get('feedback', '')
        
        if status in ['approved', 'rejected']:
            submission.status = status
            submission.feedback = feedback
            submission.reviewed_at = timezone.now()
            submission.save()
            
            # Create notification for student
            Notification.objects.get_or_create(
                user=submission.student,
                message=f"Your assignment for {submission.module.title} has been {status}.",
                link=reverse('video_player', args=[submission.module.id])
            )
            
            # If approved, update module progress for student
            if status == 'approved':
                from student.models import ModuleProgress
                mp, _ = ModuleProgress.objects.get_or_create(user=submission.student, module=submission.module)
                mp.is_completed = True
                mp.save()
                
                # Check for course completion/certificate
                from student.views import _issue_certificate_if_eligible
                _issue_certificate_if_eligible(submission.student, submission.module.course)
                
            messages.success(request, f"Assignment {status} successfully.")
        
        return redirect('teacher:review_assignments')
    return HttpResponseForbidden("Invalid method")
