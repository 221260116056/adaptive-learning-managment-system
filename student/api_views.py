import hashlib
from django.conf import settings
from django.db.models import Max
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import (
    Certificate,
    Enrollment,
    Module,
    ModuleProgress,
    Question,
    QuestionAttempt,
    Quiz,
    QuizAttempt,
    StudentProgress,
    WatchEvent,
)
from .views import _ensure_module_quiz, _issue_certificate_if_eligible
from django.shortcuts import get_object_or_404
from management.utils import _write_audit_log

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def watch_event_api(request):
    """
    Secure watch event logging with sequence, timestamp, and snapshot handling.
    """
    import time
    
    # Handle both JSON and Multipart
    data = request.data
    print(f"DEBUG: Watch Event Data Received: {data}")
    module_id = data.get("module_id")
    event_type = data.get("event_type")
    sequence_number = data.get("sequence_number")
    event_timestamp = data.get("timestamp")
    current_time = data.get("current_time", 0.0)
    snapshot_file = request.FILES.get("snapshot")

    if not all([module_id, event_type, sequence_number]):
        print(f"DEBUG: Missing fields! module_id={module_id}, event_type={event_type}, seq={sequence_number}")
        return Response({"status": "error", "message": "Missing required fields"}, status=400)


    try:
        module = Module.objects.get(id=module_id)
    except Module.DoesNotExist:
        return Response({"status": "error", "message": "Module not found"}, status=404)

    # 1. Sequence Validation
    last_event = WatchEvent.objects.filter(
        student=request.user, 
        module=module
    ).order_by('-sequence_number').first()
    
    if last_event and int(sequence_number) <= last_event.sequence_number:
        # If it's the same sequence, it might be a retry, but usually we want unique
        return Response({
            "status": "error", 
            "message": f"Sequence number must be greater than {last_event.sequence_number}"
        }, status=400)

    # 2. Timestamp Validation (Anti-Replay)
    if event_timestamp:
        server_time = time.time()
        if abs(server_time - float(event_timestamp)) > 60:
            return Response({"status": "error", "message": "Event timestamp out of sync"}, status=400)

    # 3. Cryptographic Token Binding
    hash_input = f"{request.user.id}{module_id}{sequence_number}{settings.SECRET_KEY}"
    token_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    # 4. Save Event
    event = WatchEvent.objects.create(
        student=request.user,
        module=module,
        event_type=event_type,
        sequence_number=sequence_number,
        token_hash=token_hash,
        current_time=float(current_time),
        snapshot_image=snapshot_file
    )

    # 5. Update Progress (Real percentage calculation)
    progress, created = StudentProgress.objects.get_or_create(
        student=request.user, 
        course=module.course, 
        module=module
    )
    

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def watch_event_api(request):
    """
    Secure watch event logging with sequence, timestamp, and snapshot handling.
    """
    import time
    
    # Handle both JSON and Multipart
    data = request.data
    print(f"DEBUG: Watch Event Data Received: {data}")
    module_id = data.get("module_id")
    event_type = data.get("event_type")
    sequence_number = data.get("sequence_number")
    event_timestamp = data.get("timestamp")
    current_time = data.get("current_time", 0.0)
    snapshot_file = request.FILES.get("snapshot")

    if not all([module_id, event_type, sequence_number]):
        print(f"DEBUG: Missing fields! module_id={module_id}, event_type={event_type}, seq={sequence_number}")
        return Response({"status": "error", "message": "Missing required fields"}, status=400)


    try:
        module = Module.objects.get(id=module_id)
    except Module.DoesNotExist:
        return Response({"status": "error", "message": "Module not found"}, status=404)

    # 1. Sequence Validation
    last_event = WatchEvent.objects.filter(
        student=request.user, 
        module=module
    ).order_by('-sequence_number').first()
    
    if last_event and int(sequence_number) <= last_event.sequence_number:
        # If it's the same sequence, it might be a retry, but usually we want unique
        return Response({
            "status": "error", 
            "message": f"Sequence number must be greater than {last_event.sequence_number}"
        }, status=400)

    # 2. Timestamp Validation (Anti-Replay)
    if event_timestamp:
        server_time = time.time()
        if abs(server_time - float(event_timestamp)) > 60:
            return Response({"status": "error", "message": "Event timestamp out of sync"}, status=400)

    # 3. Cryptographic Token Binding
    hash_input = f"{request.user.id}{module_id}{sequence_number}{settings.SECRET_KEY}"
    token_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    # 4. Save Event
    event = WatchEvent.objects.create(
        student=request.user,
        module=module,
        event_type=event_type,
        sequence_number=sequence_number,
        token_hash=token_hash,
        current_time=float(current_time),
        snapshot_image=snapshot_file
    )

    # 5. Update Progress (Real percentage calculation)
    progress, created = StudentProgress.objects.get_or_create(
        student=request.user, 
        course=module.course, 
        module=module
    )
    
    if module.duration_seconds > 0:
        current_percent = (float(current_time) / module.duration_seconds) * 100
        # Only update if new progress is further than before
        if current_percent > progress.watch_percent:
            progress.watch_percent = min(round(current_percent, 2), 100.0)
            
            # Auto-complete logic
            min_watch = module.video_details.min_watch_percent if hasattr(module, 'video_details') and module.video_details else 80
            if progress.watch_percent >= min_watch and not progress.is_completed:
                # Basic completion: 80% or threshold met
                progress.mark_completed()
            progress.save()

    return Response({"status": "success", "token": token_hash, "event_id": event.id})


def _get_enrolled_module(request_user, module_id):
    module = get_object_or_404(Module, id=module_id)
    is_enrolled = Enrollment.objects.filter(student=request_user, course=module.course).exists()
    if not is_enrolled:
        return None
    return module


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_progress_api(request):
    module_id = request.data.get("module_id")
    current_time = float(request.data.get("current_time", 0) or 0)
    duration = float(request.data.get("duration", 0) or 0)

    module = _get_enrolled_module(request.user, module_id)
    if module is None:
        return Response({"status": "error", "message": "Enrollment required"}, status=403)

    percent = 0
    if duration > 0:
        percent = min(round((current_time / duration) * 100, 2), 100.0)

    progress, _ = ModuleProgress.objects.get_or_create(user=request.user, module=module)
    if percent > progress.video_progress:
        progress.video_progress = percent
    progress.last_watched_time = max(progress.last_watched_time, current_time)
    progress.save(update_fields=["video_progress", "last_watched_time", "updated_at"])

    legacy_progress, _ = StudentProgress.objects.get_or_create(
        student=request.user,
        course=module.course,
        module=module,
    )
    if percent > legacy_progress.watch_percent:
        legacy_progress.watch_percent = percent
        legacy_progress.save(update_fields=["watch_percent", "updated_at"])

    return Response({
        "status": "success",
        "video_progress": progress.video_progress,
        "last_watched_time": progress.last_watched_time,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_complete_api(request, module_id):
    module = _get_enrolled_module(request.user, module_id)
    if module is None:
        return Response({"status": "error", "message": "Enrollment required"}, status=403)

    progress, _ = ModuleProgress.objects.get_or_create(user=request.user, module=module)
    
    if module.type == 'video':
        min_watch = module.video_details.min_watch_percent if hasattr(module, 'video_details') and module.video_details else 80
        if progress.video_progress < min_watch:
            return Response({"status": "error", "message": f"Must watch at least {min_watch}% before marking complete."}, status=400)
            
    progress.is_completed = True
    progress.video_progress = max(progress.video_progress, 100.0)
    progress.save(update_fields=["is_completed", "video_progress", "updated_at"])

    legacy_progress, _ = StudentProgress.objects.get_or_create(
        student=request.user,
        course=module.course,
        module=module,
    )
    legacy_progress.watch_percent = max(legacy_progress.watch_percent, 100.0)
    legacy_progress.theory_completed = True
    if module.type != 'quiz':
        legacy_progress.quiz_passed = True
    legacy_progress.is_completed = True
    legacy_progress.completed_at = legacy_progress.completed_at or timezone.now()
    legacy_progress.save(
        update_fields=[
            "watch_percent",
            "theory_completed",
            "quiz_passed",
            "is_completed",
            "completed_at",
            "updated_at",
        ]
    )

    _issue_certificate_if_eligible(request.user, module.course)

    total_modules = Module.objects.filter(course=module.course).count()
    completed_modules = ModuleProgress.objects.filter(
        user=request.user,
        module__course=module.course,
        is_completed=True,
    ).count()
    course_progress_percent = int((completed_modules / total_modules) * 100) if total_modules else 0

    return Response({
        "status": "completed",
        "module_progress": progress.video_progress,
        "course_progress_percent": course_progress_percent,
        "completed_modules": completed_modules,
        "total_modules": total_modules,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_quiz_api(request):
    quiz_id = request.data.get("quiz_id")
    answers = request.data.get("answers", {}) or {}

    quiz = get_object_or_404(Quiz, id=quiz_id)
    module = _get_enrolled_module(request.user, quiz.module_id)
    if module is None:
        return Response({"status": "error", "message": "Enrollment required"}, status=403)

    quiz = _ensure_module_quiz(module)
    if quiz is None:
        return Response({"status": "error", "message": "Quiz is not configured for this module."}, status=400)

    max_attempts = module.quiz_details.max_attempts if hasattr(module, 'quiz_details') and module.quiz_details else 3
    module_attempts = QuizAttempt.objects.filter(student=request.user, module=module)
    attempts_used = module_attempts.count()
    if attempts_used >= max_attempts:
        return Response({
            "status": "error",
            "message": f"Attempt limit reached ({max_attempts}).",
        }, status=400)

    questions = list(quiz.questions.all().order_by("order"))
    total_questions = len(questions)
    if total_questions == 0:
        return Response({"status": "error", "message": "Quiz has no questions."}, status=400)

    normalized_answers = {}
    correct_count = 0

    for question in questions:
        submitted_answer = answers.get(str(question.id)) or answers.get(question.id)
        if not submitted_answer:
            continue

        # Save for record
        normalized_answers[str(question.id)] = str(submitted_answer)

        # Case-insensitive comparison (A, B, C, or D)
        if str(submitted_answer).upper() == str(question.correct_answer).upper():
            correct_count += 1


    score = int(round((correct_count / total_questions) * 100))
    passing_score = module.quiz_details.passing_score if hasattr(module, 'quiz_details') and module.quiz_details else 70
    is_passed = score >= passing_score

    next_attempt_number = (module_attempts.aggregate(max_attempt=Max("attempt_number")).get("max_attempt") or 0) + 1

    attempt = QuizAttempt.objects.create(
        user=request.user,
        quiz=quiz,
        student=request.user,
        module=module,
        attempt_number=next_attempt_number,
        answers=normalized_answers,
        score=score,
        passed=is_passed,
        is_passed=is_passed,
    )

    legacy_progress, _ = StudentProgress.objects.get_or_create(
        student=request.user,
        course=module.course,
        module=module,
    )
    legacy_progress.quiz_passed = legacy_progress.quiz_passed or is_passed
    legacy_progress.theory_completed = True
    legacy_progress.save(update_fields=["quiz_passed", "theory_completed", "updated_at"])

    if is_passed:
        modern_progress, _ = ModuleProgress.objects.get_or_create(user=request.user, module=module)
        modern_progress.is_completed = True
        modern_progress.video_progress = max(modern_progress.video_progress, 100.0)
        modern_progress.save(update_fields=["is_completed", "video_progress", "updated_at"])

        _issue_certificate_if_eligible(request.user, module.course)

    _write_audit_log(request.user, 'Quiz Submission', f"Submitted quiz for '{module.title}' with score {score}%")

    return Response({
        "status": "success",
        "score": score,
        "passed": is_passed,
        "attempt_id": attempt.id,
        "attempts_used": attempts_used + 1,
        "attempts_remaining": max(max_attempts - (attempts_used + 1), 0),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def certificate_api(request, course_id):
    certificate = get_object_or_404(Certificate, user=request.user, course_id=course_id)
    return Response({
        "certificate_id": certificate.certificate_id,
        "course_id": certificate.course_id,
        "issued_at": certificate.issued_at,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_quiz_question_api(request):
    """
    Validates a single question answer in an adaptive quiz.
    Supports attempt limits (3) and sequential unlocking.
    """
    question_id = request.data.get("question_id")
    answer = request.data.get("answer")

    if not question_id or not answer:
        return Response({"status": "error", "message": "Missing question_id or answer."}, status=400)

    question = get_object_or_404(Question, id=question_id)
    quiz = question.quiz
    module = quiz.module
    
    # Check if the user is enrolled
    if not Enrollment.objects.filter(student=request.user, course=module.course).exists():
        return Response({"status": "error", "message": "Access denied."}, status=403)

    # Sequential Check: Ensure all lower-order questions in this quiz are completed
    previous_incomplete = Question.objects.filter(
        quiz=quiz,
        order__lt=question.order
    ).exclude(
        user_attempts__student=request.user,
        user_attempts__is_completed=True
    ).exists()

    if previous_incomplete:
        return Response({
            "status": "error", 
            "message": "Please complete previous questions first."
        }, status=400)

    # Get or create attempt record
    attempt, created = QuestionAttempt.objects.get_or_create(
        student=request.user,
        question=question
    )

    if attempt.is_completed:
        return Response({
            "status": "success",
            "message": "Question already completed.",
            "is_correct": attempt.is_correct,
            "attempts_count": attempt.attempts_count,
            "is_completed": True
        })

    if attempt.attempts_count >= 3:
        return Response({
            "status": "error",
            "message": "Maximum attempts reached.",
            "correct_answer": question.correct_answer,
            "attempts_count": attempt.attempts_count,
            "is_completed": True
        })

    # Validate Answer
    attempt.attempts_count += 1
    is_correct = str(answer).strip().upper() == str(question.correct_answer).strip().upper()
    
    if is_correct:
        attempt.is_correct = True
        attempt.is_completed = True
    elif attempt.attempts_count >= 3:
        # After 3rd failure, mark as completed but not correct
        attempt.is_completed = True
    
    attempt.save()

    response_data = {
        "status": "success",
        "is_correct": is_correct,
        "attempts_count": attempt.attempts_count,
        "is_completed": attempt.is_completed,
    }

    # Check for whole quiz completion after this attempt
    all_questions_count = quiz.questions.count()
    completed_questions_count = Question.objects.filter(
        quiz=quiz,
        user_attempts__student=request.user,
        user_attempts__is_completed=True
    ).count()

    if completed_questions_count >= all_questions_count:
        # Mark module as completed in the new system
        from .models import ModuleProgress, StudentProgress
        mp, _ = ModuleProgress.objects.get_or_create(user=request.user, module=module)
        if not mp.is_completed:
            mp.is_completed = True
            mp.save()
            
            # Retroactively sync with legacy system for certificate logic
            student_progress, _ = StudentProgress.objects.get_or_create(
                student=request.user,
                course=module.course,
                module=module
            )
            student_progress.quiz_passed = True
            student_progress.save()

            # Trigger potential certificate request
            from .views import _issue_certificate_if_eligible
            _issue_certificate_if_eligible(request.user, module.course)

    return Response(response_data)



