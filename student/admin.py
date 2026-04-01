from django.contrib import admin
from .models import (
    Course,
    Certificate,
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
    StudentProfile,
    StudentProgress,
    WatchEvent,
)

admin.site.register(StudentProfile)
admin.site.register(Notification)
admin.site.register(Course)
admin.site.register(Certificate)
admin.site.register(Enrollment)
admin.site.register(Module)
admin.site.register(ModuleProgress)
admin.site.register(Quiz)
admin.site.register(Question)
admin.site.register(Option)
admin.site.register(StudentProgress)
admin.site.register(WatchEvent)
admin.site.register(QuizAttempt)
admin.site.register(CourseCertificateTemplate)
admin.site.register(IssuedCertificate)
admin.site.register(PlatformSetting)
