# Generated by Django 4.2.3 on 2023-08-02 07:53

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("network", "0005_alter_foreigncomment_user"),
    ]

    operations = [
        migrations.CreateModel(
            name="ForeignUserBlocklist",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("blocked_user", models.TextField()),
                (
                    "server",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="network.foreignserver",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
