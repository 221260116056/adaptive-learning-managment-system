import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("student", "0008_quiz_and_certificate_pipeline"),
    ]

    operations = [
        migrations.AddField(
            model_name="certificate",
            name="verification_token",
            field=models.UUIDField(default=uuid.uuid4, unique=True),
        ),
    ]
