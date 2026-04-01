from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('student', '0009_certificate_verification_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformsetting',
            name='email_from_address',
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name='platformsetting',
            name='maintenance_mode',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='platformsetting',
            name='platform_name',
            field=models.CharField(default='Adaptive Learning LMS', max_length=255),
        ),
        migrations.AddField(
            model_name='platformsetting',
            name='smtp_host',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='platformsetting',
            name='smtp_port',
            field=models.PositiveIntegerField(default=587),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='approval_status',
            field=models.CharField(choices=[('approved', 'Approved'), ('pending', 'Pending'), ('rejected', 'Rejected')], default='approved', max_length=20),
        ),
    ]
