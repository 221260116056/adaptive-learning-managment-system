from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("student", "0006_course_moodle_sync_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ModuleProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_completed", models.BooleanField(default=False)),
                ("video_progress", models.FloatField(default=0)),
                ("last_watched_time", models.FloatField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("module", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="student.module")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "unique_together": {("user", "module")},
            },
        ),
    ]
