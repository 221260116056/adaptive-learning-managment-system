from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import hashlib
import uuid

# ---------------------------------
# 🔔 Notification
# ---------------------------------
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    link = models.URLField(max_length=500, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}"

# ---------------------------------
# 1️⃣ Student Profile
# ---------------------------------
class StudentProfile(models.Model):
    APPROVAL_STATUS_CHOICES = [
        ('approved', 'Approved'),
        ('pending', 'Pending'),
        ('rejected', 'Rejected'),
    ]

    ROLE_CHOICES = [
        ('student', 'Student'),
        ('teacher', 'Teacher'),
        ('admin', 'Admin'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_image = models.ImageField(upload_to='profiles/', null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='approved')
    moodle_user_id = models.IntegerField(null=True, blank=True, help_text="Moodle user ID for API integration")
    expertise = models.CharField(max_length=255, null=True, blank=True)
    auto_sync_enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_or_update_student_profile(sender, instance, created, **kwargs):
    if created:
        StudentProfile.objects.create(user=instance)
    else:
        StudentProfile.objects.get_or_create(user=instance)

# ---------------------------------
# 2️⃣ Course
# ---------------------------------
class Course(models.Model):
    MOODLE_SYNC_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('synced', 'Synced'),
        ('failed', 'Failed'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='courses_taught')
    moodle_course_id = models.IntegerField(null=True, blank=True, help_text="Moodle course ID for API integration")
    short_name = models.CharField(max_length=100, blank=True)
    category_id = models.IntegerField(default=1, help_text="Moodle Category ID")
    visibility = models.BooleanField(default=True)
    start_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    certificate_auto_issue = models.BooleanField(default=True)
    moodle_sync_status = models.CharField(max_length=20, choices=MOODLE_SYNC_STATUS_CHOICES, default='pending')
    moodle_last_error = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to='course_thumbnails/', blank=True, null=True)
    is_published = models.BooleanField(default=True)
    teacher_signature = models.ImageField(upload_to='signatures/teacher/', blank=True, null=True)

    def __str__(self):
        return self.title

# ---------------------------------
# 3️⃣ Enrollment
# ---------------------------------
class Enrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    is_paid = models.BooleanField(default=False)
    razorpay_order_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student.username} -> {self.course.title}"

# ---------------------------------
# 4️⃣ Course Module
# ---------------------------------
class Module(models.Model):
    MODULE_TYPES = (
        ("video", "Video"),
        ("theory", "Theory"),
        ("quiz", "Quiz"),
        ("assignment", "Assignment"),
    )

    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=20, choices=MODULE_TYPES)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)

    # Video fields
    video_file = models.FileField(upload_to="videos/raw/", null=True, blank=True)
    video_url = models.URLField(max_length=500, blank=True, null=True, help_text="[DEPRECATED] Use local video_file instead.")
    dash_manifest = models.CharField(max_length=255, blank=True)

    # Theory fields
    content = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to="theory/", null=True, blank=True)

    # Quiz fields (Legacy - now handled by Question model)
    # Fields removed: question, option_a, option_b, option_c, option_d, correct_answer


    # Assignment fields
    assignment_task_file = models.FileField(upload_to="assignments/tasks/", null=True, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.order:
            max_order = self.__class__.objects.filter(course=self.course).aggregate(models.Max('order'))['order__max']
            self.order = (max_order or 0) + 1
        super().save(*args, **kwargs)


# ---------------------------------
# 5️⃣ Student Progress
# ---------------------------------

class StudentProgress(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    watch_percent = models.FloatField(default=0)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    theory_completed = models.BooleanField(default=False)
    quiz_passed = models.BooleanField(default=False)
    replay_count = models.PositiveIntegerField(default=0)
    checkpoints_completed = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('student', 'module')

    def mark_completed(self):
        self.is_completed = True
        self.completed_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.student.username} - {self.module.title} ({self.watch_percent}%)"


class ModuleProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)
    video_progress = models.FloatField(default=0)
    last_watched_time = models.FloatField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'module')

    def __str__(self):
        return f"{self.user.username} - {self.module.title} ({self.video_progress}%)"


class Quiz(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='quizzes')

    def __str__(self):
        return f"Quiz for {self.module.title}"


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    option_a = models.CharField(max_length=500, default="")
    option_b = models.CharField(max_length=500, default="")
    option_c = models.CharField(max_length=500, default="")
    option_d = models.CharField(max_length=500, default="")
    correct_answer = models.CharField(max_length=1, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')], default="A")

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.quiz.module.title} - Q{self.order + 1}"


# Legacy - no longer used if flattening into Question
class Option(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options_legacy')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text


# ---------------------------------
# 5️⃣ Quiz Progress (Adaptive)
# ---------------------------------
class QuestionAttempt(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='question_attempts')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='user_attempts')
    attempts_count = models.PositiveIntegerField(default=0)
    is_correct = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    last_attempt_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'question')

    def __str__(self):
        return f"{self.student.username} - {self.question.text[:30]} - {self.attempts_count} attempts"


# ---------------------------------
# 6️⃣ Watch Events (append-only)
# ---------------------------------

class WatchEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ('play', 'Play'),
        ('pause', 'Pause'),
        ('heartbeat', 'Heartbeat'),
        ('checkpoint', 'Checkpoint'),
        ('webcam_snapshot', 'Webcam Snapshot'),
    ]
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    sequence_number = models.IntegerField()
    token_hash = models.CharField(max_length=64)
    current_time = models.FloatField(default=0.0)
    snapshot_image = models.ImageField(upload_to='snapshots/', null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']
        unique_together = [('student', 'module', 'sequence_number')]
        indexes = [
            models.Index(fields=['student', 'module', 'created_at']),
        ]

    def __str__(self):
        return f"{self.student.username} - {self.event_type} - {self.sequence_number}"


class QuizAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, null=True, blank=True, related_name='attempts')
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    attempt_number = models.PositiveIntegerField()
    answers = models.JSONField(default=dict, blank=True)
    score = models.FloatField(default=0)
    passed = models.BooleanField(default=False)
    is_passed = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        unique_together = ('student', 'module', 'attempt_number')

    def __str__(self):
        return f"{self.student.username} - {self.module.title} - Attempt {self.attempt_number}"


class CourseCertificateTemplate(models.Model):
    course = models.OneToOneField(Course, on_delete=models.CASCADE)
    template_name = models.CharField(max_length=120, default='Default Certificate')
    signer_name = models.CharField(max_length=120, blank=True)
    signer_title = models.CharField(max_length=120, blank=True)
    qr_verify_base_url = models.URLField(blank=True)
    auto_issue = models.BooleanField(default=True)

    def __str__(self):
        return f"Certificate Template - {self.course.title}"


class IssuedCertificate(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    certificate_number = models.CharField(max_length=64, unique=True)
    verification_hash = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_certificates',
    )
    revoke_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-issued_at']
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.certificate_number} - {self.student.username}"

    def revoke(self, revoked_by=None, reason=''):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.revoked_by = revoked_by
        self.revoke_reason = reason
        self.save(update_fields=['is_active', 'revoked_at', 'revoked_by', 'revoke_reason'])

    @staticmethod
    def build_verification_hash(student_id, course_id, certificate_number):
        raw = f"{student_id}:{course_id}:{certificate_number}"
        return hashlib.sha256(raw.encode()).hexdigest()


class Certificate(models.Model):
    STATUS_CHOICES = [
        ('pending_teacher', 'Pending Teacher Approval'),
        ('pending_admin', 'Pending Admin Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    certificate_id = models.CharField(max_length=50, unique=True)
    verification_token = models.UUIDField(default=uuid.uuid4, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_teacher')
    issued_at = models.DateTimeField(null=True, blank=True)
    certificate_file = models.FileField(upload_to='certificates/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'course')
        ordering = ['-created_at']

    def __str__(self):
        return self.certificate_id

    def mark_pending_admin(self):
        self.status = 'pending_admin'
        self.save(update_fields=['status', 'updated_at'])

    def approve(self):
        self.status = 'approved'
        self.issued_at = timezone.now()
        self.save(update_fields=['status', 'issued_at', 'updated_at'])

    def reject(self):
        self.status = 'rejected'
        self.save(update_fields=['status', 'updated_at'])

    @staticmethod
    def generate_unique_id():
        import random
        import string
        year = timezone.now().year
        # Generate 4 random uppercase chars/digits
        rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        cert_id = f"ALMS-{year}-{rand}"
        # Ensure uniqueness
        while Certificate.objects.filter(certificate_id=cert_id).exists():
            rand = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            cert_id = f"ALMS-{year}-{rand}"
        return cert_id


class PlatformSetting(models.Model):
    platform_name = models.CharField(max_length=255, default='Adaptive Learning LMS')
    maintenance_mode = models.BooleanField(default=False)
    video_host = models.CharField(max_length=255, blank=True)
    signed_url_secret = models.CharField(max_length=255, blank=True)
    admin_signature = models.ImageField(upload_to='signatures/admin/', blank=True, null=True)
    token_ttl_seconds = models.PositiveIntegerField(default=300)
    attention_monitoring_enabled = models.BooleanField(default=False)
    siem_endpoint = models.URLField(blank=True)
    blockchain_anchor_enabled = models.BooleanField(default=False)
    email_from_address = models.EmailField(blank=True)
    smtp_host = models.CharField(max_length=255, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Platform Settings"


# ---------------------------------
# 🛡️ Legacy/Orphaned Audit Models (For DB Integrity)
# ---------------------------------
class VideoEventLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=50)
    timestamp = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.event_type} @ {self.timestamp}"


class VideoProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    watched_seconds = models.FloatField(default=0)
    watch_percent = models.FloatField(default=0)
    replay_count = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.module.title} ({self.watch_percent}%)"


class AssignmentSubmission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assignment_submissions')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='submissions')
    github_link = models.URLField(max_length=500, blank=True, null=True)
    google_drive_link = models.URLField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    feedback = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'module')

    def __str__(self):
        return f"{self.student.username} - {self.module.title} ({self.status})"
