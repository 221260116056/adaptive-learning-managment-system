from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models import Avg, Count
from django.urls import reverse
from django.http import JsonResponse, FileResponse, Http404, HttpResponseForbidden, HttpResponse
import uuid
import os
from django.template.loader import get_template, render_to_string
import base64
import hashlib
import json
from learntrust.access import get_user_role, redirect_for_role, student_required
from .models import (
    Certificate,
    Course,
    CourseCertificateTemplate,
    Enrollment,
    IssuedCertificate,
    ModuleProgress,
    Module,
    Notification,
    Option,
    PlatformSetting,
    Question,
    Quiz,
    QuizAttempt,
    StudentProgress,
    StudentProfile,
    WatchEvent,
    AssignmentSubmission,
)
from .forms import CustomUserCreationForm
from .utils import generate_qr_code


def _landing_context():
    # Only count courses that have at least one module (actual learning content)
    course_query = Course.objects.annotate(
        module_count=Count('module')
    ).filter(
        is_active=True,
        module_count__gt=0,
    )
    
    featured_courses = Course.objects.annotate(
        module_count=Count('module'),
        learner_count=Count('enrollment', distinct=True),
    ).filter(
        is_active=True,
        module_count__gt=0,
    ).order_by('-learner_count', 'title')[:6]

    active_students = StudentProfile.objects.filter(role='student', user__is_active=True).count()
    active_teachers = StudentProfile.objects.filter(role='teacher', user__is_active=True).count()
    total_courses = course_query.count()

    return {
        'featured_courses': featured_courses,
        'category_labels': ['Data Science', 'AI/ML', 'DSA', 'Design', 'Finance', 'DevOps'],
        'stats': {
            'courses': total_courses,
            'learners': active_students,
            'teachers': active_teachers,
            'secure_learning': '100%',
        },
    }


def _normalize_quiz_answer(value):
    if value is None:
        return ''
    return str(value).strip().lower()


def _module_quiz_questions(module):
    if module.type == 'quiz':
        # For new unified model
        if module.question:
            return [{
                'question': module.question,
                'options': [module.option_a, module.option_b, module.option_c, module.option_d],
                'answer': module.correct_answer
            }]
        return []

    # Fallback for old model structure
    if hasattr(module, 'quiz_details'):
        return [
            {
                'question': q.question,
                'options': [q.option_a, q.option_b, q.option_c, q.option_d],
                'answer': q.correct_answer
            }
            for q in module.quiz_details.questions.all().order_by('id')
        ]

    quiz_data = getattr(module, 'quiz_data', None) or {}
    questions = quiz_data.get('questions')
    if isinstance(questions, list) and questions:
        return questions

    if quiz_data.get('question'):
        return [{
            'question': quiz_data.get('question'),
            'options': quiz_data.get('options', []),
            'answer': quiz_data.get('answer'),
        }]
    return []


def _question_answer_label(index):
    return chr(ord('a') + index)


def _ensure_module_quiz(module):
    if module.type != 'quiz':
        return None

    quiz, _ = Quiz.objects.get_or_create(module=module)
    if quiz.questions.exists():
        return quiz

    questions = _module_quiz_questions(module)
    for question_data in questions:
        question = Question.objects.create(
            quiz=quiz,
            text=question_data.get('question', 'Quiz Question'),
        )
        expected_answer = _normalize_quiz_answer(question_data.get('answer'))
        options = question_data.get('options') or []

        for index, option_text in enumerate(options):
            normalized_option = _normalize_quiz_answer(option_text)
            option_label = _question_answer_label(index)
            is_correct = normalized_option == expected_answer or option_label == expected_answer
            Option.objects.create(
                question=question,
                text=str(option_text),
                is_correct=is_correct,
            )

    return quiz


def _quiz_payload(quiz):
    if quiz is None:
        return None

    return {
        'id': quiz.id,
        'questions': [
            {
                'id': question.id,
                'text': question.text,
                'options': [
                    {
                        'id': option.id,
                        'text': option.text,
                    }
                    for option in question.options.all().order_by('id')
                ],
            }
            for question in quiz.questions.prefetch_related('options').all().order_by('id')
        ],
    }


def _evaluate_quiz_submission(module, answers):
    questions = _module_quiz_questions(module)
    if not questions:
        return 100.0, True

    total = len(questions)
    correct = 0
    for index, question in enumerate(questions):
        expected = _normalize_quiz_answer(question.get('answer'))
        submitted = answers.get(str(index), answers.get(index, answers.get('answer')))
        normalized_submitted = _normalize_quiz_answer(submitted)
        options = question.get('options') or []

        accepted_answers = {expected}
        if expected in {'a', 'b', 'c', 'd'}:
            option_index = ord(expected) - ord('a')
            if 0 <= option_index < len(options):
                accepted_answers.add(_normalize_quiz_answer(options[option_index]))

        if normalized_submitted in accepted_answers:
            correct += 1

    score = (correct / total) * 100 if total else 0
    return score, score >= 70  # Default passing score of 70%


def _module_completion_ready(progress, module):
    if module.type == 'video':
        # For new unified model, video completion is based on progress
        return progress.video_progress >= 80  # Default 80% watch requirement
    elif module.type == 'quiz':
        return progress.quiz_passed
    elif module.type == 'theory':
        return progress.theory_completed
    elif module.type == 'assignment':
        return AssignmentSubmission.objects.filter(student=progress.student, module=module, status='approved').exists()
    return True


def _sync_completion_state(progress):
    if _module_completion_ready(progress, progress.module) and not progress.is_completed:
        progress.mark_completed()
        Notification.objects.get_or_create(
            user=progress.student,
            message=f"Module completed: {progress.module.title}",
            link=reverse('video_player', args=[progress.module.id])
        )
    elif progress.is_completed and not _module_completion_ready(progress, progress.module):
        progress.is_completed = False
        progress.completed_at = None
        progress.save(update_fields=['is_completed', 'completed_at', 'updated_at'])


def _check_course_completion(user, course):
    total_modules = Module.objects.filter(course=course).count()
    if total_modules == 0:
        return None

    required_quiz_modules = Module.objects.filter(course=course, type='quiz')
    for quiz_module in required_quiz_modules:
        legacy_passed = StudentProgress.objects.filter(student=user, module=quiz_module, quiz_passed=True).exists()
        if legacy_passed:
            # Retroactive sync for old completions
            mp, _ = ModuleProgress.objects.get_or_create(user=user, module=quiz_module)
            if not mp.is_completed:
                mp.is_completed = True
                mp.video_progress = 100.0
                mp.save(update_fields=['is_completed', 'video_progress', 'updated_at'])
        else:
            return None

    completed_modules = ModuleProgress.objects.filter(
        user=user,
        module__course=course,
        is_completed=True,
    ).count()
    if completed_modules != total_modules:
        return None

    certificate, created = Certificate.objects.get_or_create(
        user=user,
        course=course,
        defaults={
            'certificate_id': Certificate.generate_unique_id(),
            'status': 'pending_teacher',
        },
    )

    if not created and certificate.status in ['rejected']:
        certificate.status = 'pending_teacher'
        certificate.save(update_fields=['status', 'updated_at'])

    return certificate


def _issue_certificate_if_eligible(user, course):
    completion_certificate = _check_course_completion(user, course)
    if completion_certificate is None:
        return None

    # Teacher/Admin workflow in Certificate model
    certificate = completion_certificate
    if certificate.status == 'pending_teacher':
        # already pending 
        return certificate

    if certificate.status in ['pending_admin', 'approved']:
        return certificate

    certificate.status = 'pending_teacher'
    certificate.save(update_fields=['status', 'updated_at'])

    Notification.objects.get_or_create(
        user=user,
        message=f"Certificate request pending teacher approval for {course.title}",
        link=reverse('certificates')
    )

    return certificate

def customize_auth_form(form):
    # We only want to transform the username field to 'Email Address' for the login form (which has no email field).
    # For the signup form, it will naturally have both username and email.
    if 'username' in form.fields and 'email' not in form.fields:
        form.fields['username'].label = 'Email Address'
        form.fields['username'].widget.attrs['placeholder'] = 'Enter your email'
    if 'password' in form.fields:
        form.fields['password'].widget.attrs['placeholder'] = 'Enter your password'

def login_role_selection(request):
    return redirect('student_login')

def signup_role_selection(request):
    return redirect('student_signup')


def home_redirect(request):
    context = _landing_context()
    context['user_role'] = get_user_role(request.user)
    return render(request, 'main/home.html', context)


def landing_courses_view(request):
    courses = Course.objects.annotate(
        module_count=Count('module'),
        learner_count=Count('enrollment', distinct=True),
    ).filter(
        is_active=True,
        module_count__gt=0,
    ).order_by('-learner_count', 'title')
    context = _landing_context()
    context.update({
        'courses': courses,
        'user_role': get_user_role(request.user),
    })
    return render(request, 'main/courses.html', context)


def landing_about_view(request):
    context = _landing_context()
    context['user_role'] = get_user_role(request.user)
    return render(request, 'main/about.html', context)


def landing_contact_view(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')
        
        # Logic to send email to official ID
        subject = f"New Contact Message from {name}"
        full_message = f"You have received a new message from your LMS Contact Form.\n\nName: {name}\nEmail: {email}\n\nMessage:\n{message}"
        recipient_list = ['Vekariyavraj760@gmail.com']
        
        try:
            send_mail(
                subject,
                full_message,
                settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@learntrust.com',
                recipient_list,
                fail_silently=False,
            )
            messages.success(request, "Your message has been sent successfully!")
        except Exception as e:
            messages.error(request, f"Error sending message: {str(e)}")
            
        return redirect('landing_contact')

    context = _landing_context()
    context['user_role'] = get_user_role(request.user)
    context['contact_email'] = 'support@learntrust.com'
    context['contact_phone'] = '+1 (555) 123-4567'
    return render(request, 'main/contact.html', context)

def student_signup_view(request):
    selected_role = 'student'
    if request.method == 'POST':
        selected_role = request.POST.get('role', 'student')
        if selected_role not in {'student', 'teacher'}:
            selected_role = 'student'
        form = CustomUserCreationForm(request.POST)
        customize_auth_form(form)
        if form.is_valid():
            user = form.save()
            approval_status = 'pending' if selected_role == 'teacher' else 'approved'
            StudentProfile.objects.create(user=user, role=selected_role, approval_status=approval_status)
            
            # Sync user to Moodle
            from .moodle_sync import sync_moodle_user
            sync_moodle_user(user, password=form.cleaned_data.get('password'))
            
            if selected_role == 'teacher':
                from django.contrib import messages
                messages.info(request, "Your account is under review. You will be notified once approved.")
                return redirect('login')
            else:
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
        customize_auth_form(form)
    return render(request, 'student/auth_signup.html', {'form': form, 'selected_role': selected_role})

def student_login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        customize_auth_form(form)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # Check approval for teachers
            try:
                profile = user.studentprofile
                if profile.role == 'teacher' and profile.approval_status != 'approved':
                    messages.error(request, "Your account is pending admin approval.")
                    logout(request)
                    return redirect('login')
            except StudentProfile.DoesNotExist:
                pass
            
            # Update/Check Moodle Sync on Login
            from .moodle_sync import sync_moodle_user
            sync_moodle_user(user, password=form.cleaned_data.get('password'))
            
            if user.is_superuser:
                return redirect('adminpanel:home')
            
            try:
                # Redirect teachers to teacher dashboard
                if hasattr(user, 'studentprofile') and user.studentprofile.role == 'teacher':
                    return redirect('teacher:dashboard')
            except StudentProfile.DoesNotExist:
                pass
            
            # Default student redirect
            return redirect('dashboard')

    else:
        form = AuthenticationForm()
        customize_auth_form(form)
    return render(request, 'student/auth_login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

    return response


def verify_certificate(request, token):
    certificate = get_object_or_404(
        Certificate.objects.select_related('course', 'user'),
        verification_token=token,
    )
    return render(request, 'certificates/verify.html', {'certificate': certificate})

@student_required
def profile_view(request):
    user = request.user
    enrollments_count = Enrollment.objects.filter(student=user).count()
    # Debug help
    print(f"DEBUG: {request.user.username} enrolled =>", Enrollment.objects.filter(student=user))

    completed_count = 0
    enrolled_courses = Enrollment.objects.filter(student=user).select_related('course')
    for enrollment in enrolled_courses:
        course = enrollment.course
        total_modules = Module.objects.filter(course=course).count()
        if total_modules == 0:
            continue
        completed_modules = ModuleProgress.objects.filter(
            user=user,
            module__course=course,
            is_completed=True
        ).count()
        if completed_modules >= total_modules:
            completed_count += 1

    certificate_count = Certificate.objects.filter(user=user).count()

    context = {
        'enrollments_count': enrollments_count,
        'completed_count': completed_count,
        'certificate_count': certificate_count,
        'display_name': request.user.get_full_name() or request.user.username,
        'date_joined': request.user.date_joined,
    }
    return render(request, 'student/profile.html', context)

@student_required
def profile_settings(request):
    user = request.user
    profile, _ = StudentProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")

        # Email NOT updated (locked)
        user.first_name = first_name
        user.last_name = last_name

        if request.FILES.get("photo"):
            profile.profile_image = request.FILES.get("photo")

        user.save()
        profile.save()

        messages.success(request, "Profile updated successfully")
        return redirect("settings")

    return render(request, "student/settings.html", {"user": user, "profile": profile})

@student_required
def change_password(request):
    if request.method == "POST":
        old_password = request.POST.get("old_password")
        new_password = request.POST.get("new_password")

        if request.user.check_password(old_password):
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password updated successfully")
        else:
            messages.error(request, "Old password incorrect")

        return redirect("settings")

@student_required
def notifications_view(request):
    # Fetch real notifications from DB
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    # Auto mark as read when viewed
    notifications.update(is_read=True)
    return render(request, 'student/notifications.html', {'notifications': notifications})

@student_required
def dashboard(request):
    from .moodle_api import get_moodle_courses, get_course_modules
    from .moodle_sync import sync_moodle_user, get_course_contents
    
    # Ensure user is synced and we have their Moodle ID
    moodle_user_id = sync_moodle_user(request.user)

    # 0. Sync ALL available courses for discovery/exploration
    from .moodle_service import MoodleService
    ms = MoodleService()
    all_moodle_courses = ms.get_courses()
    if isinstance(all_moodle_courses, list):
        for m_course in all_moodle_courses:
            if m_course['id'] == 1: # Skip Moodle Site Course
                continue
            Course.objects.get_or_create(
                moodle_course_id=m_course['id'],
                defaults={
                    'title': m_course.get('fullname', 'Moodle Course'),
                    'description': m_course.get('summary', ''),
                    'price': 0.00,
                    'is_active': True
                }
            )
    
    if moodle_user_id:
        moodle_courses_data = get_moodle_courses(moodle_user_id)
        
        # --- Force Sync Django -> Moodle ---
        django_enrollments = Enrollment.objects.filter(student=request.user)
        moodle_enrolled_ids = [c['id'] for c in moodle_courses_data] if isinstance(moodle_courses_data, list) else []
        
        from .moodle_sync import enrol_user_in_course
        needs_refetch = False
        for enrollment in django_enrollments:
            m_id = enrollment.course.moodle_course_id
            if m_id and m_id not in moodle_enrolled_ids:
                print(f"DEBUG: Found Django enrollment for Moodle Course {m_id} missing in Moodle. Syncing...")
                if enrol_user_in_course(moodle_user_id, m_id):
                    needs_refetch = True
        
        if moodle_user_id:
            moodle_courses_data = get_moodle_courses(moodle_user_id)
        # -----------------------------------

        if isinstance(moodle_courses_data, list):
            for m_course in moodle_courses_data:
                # Skip Moodle Site Course or the 'Python Programming' course that is not working
                if m_course['id'] == 1 or "Python Programming: Beginner to Intermediate" in m_course.get('fullname', ''):
                    continue
                # 1. Shadow Sync Course to local DB
                course, created = Course.objects.get_or_create(
                    moodle_course_id=m_course['id'],
                    defaults={
                        'title': m_course.get('fullname', 'Moodle Course'),
                        'description': m_course.get('summary', ''),
                        'price': 0.00,
                        'is_active': True
                    }
                )
                
                # 2. Shadow Sync Enrollment
                Enrollment.objects.get_or_create(
                    student=request.user,
                    course=course,
                    defaults={'is_paid': True}
                )

                # 3. Shadow Sync Modules (Contents)
                contents = get_course_contents(m_course['id'])
                for section_idx, section in enumerate(contents):
                    for m_module in section.get('modules', []):
                        if m_module.get('modname') in ['resource', 'video', 'url', 'page']:
                            m_url = ""
                            # Try to extract content URL
                            if m_module.get('contents'):
                                for c in m_module['contents']:
                                    # 1. Prioritize HTML/Page content for 'page' modules
                                    if m_module.get('modname') == 'page' and (c.get('filename') == 'index.html' or c.get('mimetype') == 'text/html'):
                                        m_url = c.get('fileurl', '')
                                        break
                                    # 2. Extract video files
                                    if 'video' in c.get('mimetype', '') or c.get('filename', '').lower().endswith(('.mp4', '.webm', '.ogg')):
                                        m_url = c.get('fileurl', '')
                                        break
                                    # 3. Handle external links for URL modules (e.g. YouTube)
                                    if m_module.get('modname') == 'url' and c.get('fileurl'):
                                        m_url = c.get('fileurl', '')
                                        break
                                
                                if m_url:
                                    m_url = m_url.replace('forcedownload=1', 'forcedownload=0')
                                    # Append token only for local Moodle files
                                    if 'token=' not in m_url and settings.MOODLE_URL.split('/')[2] in m_url:
                                        sep = '&' if '?' in m_url else '?'
                                        m_url += f"{sep}token={settings.MOODLE_TOKEN}"
                            
                            # If no direct file was found (or for URL modules), use the standard module URL
                            if not m_url and m_module.get('url'):
                                m_url = m_module['url']
                            
                            # Map Moodle modname to our type
                            m_type = 'video' if m_module.get('modname') in ['video', 'url'] else 'theory'

                            Module.objects.update_or_create(
                                course=course,
                                title=m_module.get('name', 'Untitled Module'),
                                defaults={
                                    'description': m_module.get('description', ''),
                                    'type': m_type,
                                    'order': section_idx * 100 + m_module.get('id', 0),
                                    'video_url': m_url,
                                    'is_published': True
                                }
                            )
    # Sync finished. Now fetch all courses the user is enrolled in from OUR database.
    user_enrollments = Enrollment.objects.filter(student=request.user).select_related('course')
    
    courses_with_stats = []
    total_completed = 0
    
    for enrollment in user_enrollments:
        course = enrollment.course
        all_modules_count = Module.objects.filter(course=course).count()
        if all_modules_count == 0:
            continue
        completed_count = ModuleProgress.objects.filter(
            user=request.user,
            module__course=course,
            is_completed=True
        ).count()
        
        progress_percent = 0
        if all_modules_count > 0:
            progress_percent = int((completed_count / all_modules_count) * 100)
        
        total_completed += completed_count
        
        courses_with_stats.append({
            'id': course.moodle_course_id or course.id,
            'fullname': course.title,
            'shortname': course.short_name or course.title[:20],
            'progress': progress_percent,
            'completed_modules': completed_count,
            'total_modules': all_modules_count,
            'thumbnail_url': course.thumbnail.url if course.thumbnail else None
        })

    enrolled_course_ids = Enrollment.objects.filter(student=request.user).values_list('course_id', flat=True)
    explore_courses = Course.objects.exclude(id__in=enrolled_course_ids).annotate(
        module_count=Count('module')
    ).filter(module_count__gt=0)[:4]

    context = {
        'enrolled_courses': courses_with_stats,
        'explore_courses': explore_courses,
        'total_completed_modules': total_completed,
        'welcome_msg': f"Welcome back, {request.user.username}!"
    }
    for enrollment in user_enrollments:
        _issue_certificate_if_eligible(request.user, enrollment.course)
    return render(request, 'student/dashboard.html', context)

from django.http import JsonResponse
import json

@student_required
def watch_event_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            module_id = data.get('module_id')
            event_type = data.get('event_type')
            current_time = float(data.get('current_time', 0))
            sequence = int(data.get('sequence', 0))
            metadata = data.get('metadata') or {}
            
            module = get_object_or_404(Module, id=module_id)
            
            # Save watch event
            WatchEvent.objects.create(
                student=request.user,
                module=module,
                event_type=event_type,
                current_time=current_time,
                sequence_number=sequence,
                token_hash=hashlib.sha256(f"{request.user.id}:{module_id}:{sequence}:{settings.SECRET_KEY}".encode()).hexdigest(),
                metadata=metadata,
            )
            
            # Update progress
            progress, created = StudentProgress.objects.get_or_create(
                student=request.user,
                course=module.course,
                module=module
            )
            
            # Calculate watch percentage (simple estimation for now)
            if module.duration_seconds > 0:
                percent = (current_time / module.duration_seconds) * 100
                if percent > progress.watch_percent:
                    progress.watch_percent = min(percent, 100)

            if event_type == 'checkpoint':
                progress.checkpoints_completed = progress.checkpoints_completed + 1
            if event_type in ['complete', 'replay']:
                progress.replay_count = max(progress.replay_count, 1) if event_type == 'complete' else progress.replay_count + 1
            if metadata.get('theory_completed'):
                progress.theory_completed = True

            progress.save()
            _sync_completion_state(progress)

            return JsonResponse({
                'status': 'success',
                'watch_percent': round(progress.watch_percent, 2),
                'is_completed': progress.is_completed,
                'checkpoints_completed': progress.checkpoints_completed,
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'invalid_method'}, status=405)

@student_required
def quiz_submit_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            module_id = data.get('module_id')
            answers = data.get('answers', {})
            theory_completed = data.get('theory_completed', False)
            
            module = get_object_or_404(Module, id=module_id)
            
            progress, _ = StudentProgress.objects.get_or_create(
                student=request.user,
                course=module.course,
                module=module
            )

            progress.theory_completed = progress.theory_completed or bool(theory_completed)

            questions = _module_quiz_questions(module)
            if questions:
                has_submitted_answers = any(
                    _normalize_quiz_answer(value) != ''
                    for value in (answers or {}).values()
                )

                if not has_submitted_answers:
                    progress.save()
                    _sync_completion_state(progress)
                    return JsonResponse({
                        'status': 'pending_quiz',
                        'message': 'Please answer the quiz before completing this module.',
                        'module_completed': progress.is_completed,
                    }, status=400)

                max_attempts = 3  # Default max attempts for new model
                attempts_used = QuizAttempt.objects.filter(student=request.user, module=module).count()
                if attempts_used >= max_attempts:
                    return JsonResponse({
                        'status': 'locked',
                        'message': f'Attempt limit reached ({max_attempts}).'
                    }, status=400)

                score, is_passed = _evaluate_quiz_submission(module, answers)
                QuizAttempt.objects.create(
                    student=request.user,
                    module=module,
                    attempt_number=attempts_used + 1,
                    answers=answers,
                    score=score,
                    passed=is_passed,
                )
                progress.quiz_passed = progress.quiz_passed or is_passed
                progress.save()
            
            elif module.type == 'assignment':
                # Submission alone doesn't complete it, teacher approval does.
                # This API might be called for theory_completed within an assignment module if any.
                pass

            _sync_completion_state(progress)

            if progress.is_completed:
                _issue_certificate_if_eligible(request.user, module.course)

            max_attempts = module.quiz_details.max_attempts if hasattr(module, 'quiz_details') and module.quiz_details else 3
            attempts_remaining = max(
                max_attempts - QuizAttempt.objects.filter(student=request.user, module=module).count(),
                0,
            )
            return JsonResponse({
                'status': 'success' if is_passed or module.type != 'quiz' else 'fail',
                'message': 'Module requirements updated.',
                'score': round(score, 2),
                'passed': bool(is_passed),
                'attempts_remaining': attempts_remaining,
                'module_completed': progress.is_completed,
            })
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'invalid_method'}, status=405)

@student_required
def submit_assignment_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            module_id = data.get('module_id')
            github_link = data.get('github_link')
            google_drive_link = data.get('google_drive_link')
            
            module = get_object_or_404(Module, id=module_id, type='assignment')
            
            submission, created = AssignmentSubmission.objects.update_or_create(
                student=request.user,
                module=module,
                defaults={
                    'github_link': github_link,
                    'google_drive_link': google_drive_link,
                    'status': 'pending', 
                    'submitted_at': timezone.now()
                }
            )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Assignment submitted successfully. Waiting for teacher review.'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'invalid_method'}, status=405)

@student_required
def unlock_next_module_api(request, course_id):
    # This might be used by frontend to check if next module can be played
    course = get_object_or_404(Course, id=course_id)
    # Find next incomplete module
    return JsonResponse({'status': 'success'})

@student_required
def player_course_view(request, course_id):
    """
    Redirects to the first module of a course.
    """
    # Try finding by Moodle ID first, then by local ID
    course = Course.objects.filter(moodle_course_id=course_id).first()
    if not course:
        course = get_object_or_404(Course, id=course_id)
        
    first_module = Module.objects.filter(course=course).order_by('order').first()
    if not first_module:
        messages.warning(request, 'This course has no learning modules yet, so it has been hidden from your learning list.')
        return redirect('my_courses')
        
    return redirect('video_player', module_id=first_module.id)





@student_required
def my_courses(request):
    enrollments = Enrollment.objects.filter(student=request.user, is_paid=True).select_related('course')
    course_cards = []
    for enrollment in enrollments:
        course = enrollment.course
        total_modules = Module.objects.filter(course=course).count()
        if total_modules == 0:
            continue
        completed_modules = ModuleProgress.objects.filter(
            user=request.user,
            module__course=course,
            is_completed=True,
        ).count()
        progress_percent = int((completed_modules / total_modules) * 100) if total_modules else 0
        first_module = Module.objects.filter(course=course).order_by('order').first()
        course_cards.append({
            'enrollment': enrollment,
            'progress_percent': progress_percent,
            'is_completed': total_modules > 0 and completed_modules == total_modules,
            'first_module': first_module,
        })
    return render(request, 'student/my_courses.html', {'course_cards': course_cards})

@student_required
def my_certificate(request, course_id):
    certificate = get_object_or_404(Certificate, user=request.user, course_id=course_id)
    return render(request, 'student/my_certificate.html', {
        'certificate': certificate,
    })

@student_required
def video_player(request, module_id):
    from .moodle_api import get_module_content, get_course_modules
    
    module = get_object_or_404(Module, id=module_id)
    if not Enrollment.objects.filter(student=request.user, course=module.course).exists():
        return redirect('my_courses')

    progress, _ = StudentProgress.objects.get_or_create(
        student=request.user,
        course=module.course,
        module=module,
    )
    
    submission = AssignmentSubmission.objects.filter(student=request.user, module=module).first()
    
    # Fetch module details from Moodle
    print(f"DEBUG: Fetching module content")
    moodle_module = get_module_content(module.order % 100) # Assuming ID mapping
    
    last_event = WatchEvent.objects.filter(student=request.user, module=module).order_by('-sequence_number').first()
    last_sequence_number = last_event.sequence_number if last_event else 0
    
    # ---------------------------------------------------------
    # Module type rendering
    # ---------------------------------------------------------
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
            # Use DASH manifest
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
            
    # Check if module is locked (adaptive progression)
    # Locked if any module with a lower 'order' is not completed
    previous_modules = Module.objects.filter(course=module.course, order__lt=module.order)
    is_locked = False
    lock_reason = ""
    for pm in previous_modules:
        if not ModuleProgress.objects.filter(user=request.user, module=pm, is_completed=True).exists():
            is_locked = True
            lock_reason = "Complete the previous modules first."
            break

    
    # Define missing variables for template
    all_modules = Module.objects.filter(course=module.course).order_by('order')
    course_modules = get_course_modules(module.course.moodle_course_id) if module.course.moodle_course_id else []
    attempts_used = QuizAttempt.objects.filter(student=request.user, module=module).count()
    max_attempts = 3  # Default for new model
    attempts_remaining = max(max_attempts - attempts_used, 0)
    total_modules = all_modules.count()
    completed_modules = ModuleProgress.objects.filter(
        user=request.user,
        module__course=module.course,
        is_completed=True,
    ).count()
    course_progress_percent = int((completed_modules / total_modules) * 100) if total_modules else 0
    module_progress, _ = ModuleProgress.objects.get_or_create(user=request.user, module=module)
    quiz = _ensure_module_quiz(module)
    next_module = Module.objects.filter(course=module.course, order__gt=module.order).order_by('order').first()
             
    return render(request, 'student/video_player.html', {
        'module': module,
        'all_modules': all_modules,
        'last_sequence_number': last_sequence_number,
        'is_youtube': is_youtube,
        'is_hls': is_hls,
        'is_external_page': is_external_page,
        'embed_url': embed_url,
        'moodle_module': moodle_module,
        'course_modules': course_modules,
        'is_locked': is_locked,
        'lock_reason': lock_reason,
        'progress': progress,
        'module_progress': module_progress,
        'module_progress_percent': int(module_progress.video_progress),
        'attempts_remaining': attempts_remaining,
        'course_progress_percent': course_progress_percent,
        'completed_modules_count': completed_modules,
        'total_modules_count': total_modules,
        'quiz_payload': _quiz_payload(quiz),
        'next_module_url': reverse('video_player', kwargs={'module_id': next_module.id}) if next_module else reverse('dashboard'),
        'allow_seek': True,  # Default for new model
        'disable_fast_forward': module.video_details.disable_fast_forward if hasattr(module, 'video_details') and module.video_details else True,
        'enable_checkpoints': module.video_details.enable_checkpoints if hasattr(module, 'video_details') and module.video_details else False,
        'checkpoint_interval': module.video_details.checkpoint_interval if hasattr(module, 'video_details') and module.video_details else 30,
        'checkpoint_interval': module.video_details.checkpoint_interval if hasattr(module, 'video_details') and module.video_details else 30,
        'min_watch_percent': module.video_details.min_watch_percent if hasattr(module, 'video_details') and module.video_details else 80,
        'dash_manifest': dash_manifest,
        'submission': submission,
    })


@login_required
def stream_dash_video(request, module_id, filename):
    module = get_object_or_404(Module, id=module_id)
    if not module.dash_manifest:
        raise Http404("DASH streaming not available for this module")

    # Allow enrolled students OR the course teacher
    is_enrolled = Enrollment.objects.filter(student=request.user, course=module.course).exists()
    is_teacher = module.course.teacher_id == request.user.id
    if not is_enrolled and not is_teacher and not request.user.is_superuser:
        return HttpResponseForbidden("Access denied")

    dash_dir = os.path.join(settings.MEDIA_ROOT, f"videos/dash/module_{module_id}")
    file_path = os.path.join(dash_dir, filename)

    if not os.path.normpath(file_path).startswith(os.path.normpath(dash_dir)):
        raise Http404("Invalid path")

    if not os.path.exists(file_path):
        raise Http404("DASH segment not found")
        
    response = FileResponse(open(file_path, 'rb'))
    response['Access-Control-Allow-Origin'] = '*'
    response['Cache-Control'] = 'no-cache'

    if filename.endswith('.mpd'):
        response['Content-Type'] = 'application/dash+xml'
    elif filename.endswith('.m4s') or filename.endswith('.mp4'):
        response['Content-Type'] = 'video/mp4'

    return response

@student_required
def explore_view(request):
    query = request.GET.get('q')
    enrolled_course_ids = Enrollment.objects.filter(student=request.user).values_list('course_id', flat=True)

    if query:
        courses = Course.objects.filter(
            title__icontains=query
        ) | Course.objects.filter(
            description__icontains=query
        )
    else:
        courses = Course.objects.all()

    courses = courses.exclude(id__in=enrolled_course_ids).annotate(
        module_count=Count('module')
    ).filter(
        module_count__gt=0,
        is_active=True,
    ).distinct()
    
    return render(request, 'student/explore.html', {
        'courses': courses,
        'enrolled_course_ids': enrolled_course_ids,
        'query': query
    })
@student_required
def enroll_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    enrollment, created = Enrollment.objects.get_or_create(
        student=request.user,
        course=course,
        defaults={'is_paid': True}
    )

    if created:
        # Sync to Moodle only on new enrollment
        profile = getattr(request.user, 'studentprofile', None)
        if profile and profile.moodle_user_id and course.moodle_course_id:
            from .moodle_sync import enrol_user_in_course
            enrol_user_in_course(profile.moodle_user_id, course.moodle_course_id)

    return redirect('my_courses')


from django.views.decorators.csrf import csrf_exempt
import json

@login_required
@csrf_exempt
def video_heartbeat(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            percent = float(data.get('percent', 0.0))
            seconds = float(data.get('current_time', 0.0))
            module_id = data.get('module_id')

            module = get_object_or_404(Module, id=module_id, type='video')
            progress, _ = ModuleProgress.objects.get_or_create(
                user=request.user,
                module=module
            )

            # Update progress
            progress.video_progress = max(progress.video_progress, percent)
            progress.save()

            # Sync completion state
            _sync_completion_state(progress)

            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

@login_required
@csrf_exempt
def video_replay(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            module_id = data.get('module_id')

            module = get_object_or_404(Module, id=module_id, type='video')
            progress, _ = ModuleProgress.objects.get_or_create(
                user=request.user,
                module=module
            )

            # For replay tracking, we could add a field to ModuleProgress if needed
            # For now, just acknowledge
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

@student_required
def certificates_view(request):
    """View list of student's certificates and issue eligible ones."""
    enrollments = Enrollment.objects.filter(student=request.user)
    for enrollment in enrollments:
        _issue_certificate_if_eligible(request.user, enrollment.course)

    certificates = Certificate.objects.filter(user=request.user).select_related('course').order_by('-created_at')
    return render(request, 'student/certificates.html', {'certificates': certificates})

def verify_certificate(request, cert_id):
    """Public verification page for certificates."""
    certificate = get_object_or_404(Certificate, certificate_id=cert_id, status='approved')
    return render(request, 'student/verify_certificate.html', {
        'certificate': certificate,
        'issuer_name': "Adaptive Learning LMS",
        'issued_date': certificate.issued_at
    })

@login_required
def download_certificate(request, cert_id):
    """Secure download for students to get their issued certificate PDF."""
    certificate = get_object_or_404(Certificate, certificate_id=cert_id, user=request.user)
    
    if certificate.status != 'approved':
        messages.error(request, "This certificate is not yet approved.")
        return redirect('certificates')

    # On-the-fly generation if file is missing (for legacy or failed generations)
    if not certificate.certificate_file:
        from .certificate_generator import generate_certificate_pdf
        try:
            generate_certificate_pdf(certificate)
        except Exception as e:
            messages.error(request, f"Unable to generate certificate PDF: {str(e)}")
            return redirect('certificates')
        
    return FileResponse(
        certificate.certificate_file.open('rb'),
        content_type='application/pdf',
        as_attachment=True,
        filename=f"Certificate-{certificate.certificate_id}.pdf"
    )

@login_required
@student_required
def notifications_view(request):
    if request.GET.get('action') == 'mark_read':
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return redirect('notifications')

    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Optionally mark all as read automatically on visit
    # Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    return render(request, 'student/notifications.html', {'notifications': notifications})

@login_required
@student_required
def delete_notification(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.delete()
    return redirect('notifications')
