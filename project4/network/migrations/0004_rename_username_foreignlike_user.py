# Generated by Django 4.2.3 on 2023-07-31 05:26

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("network", "0003_auto_20230731_0036"),
    ]

    operations = [
        migrations.RenameField(
            model_name="foreignlike",
            old_name="username",
            new_name="user",
        ),
    ]
