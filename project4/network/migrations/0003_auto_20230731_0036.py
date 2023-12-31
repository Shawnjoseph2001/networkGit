# Generated by Django 4.2.3 on 2023-07-31 00:36

from django.db import migrations


def add_default(apps, schema_editor):
    model = apps.get_model("network", "ForeignServer")
    model.objects.get_or_create(ip="local")


class Migration(migrations.Migration):
    dependencies = (
        ("network", "0002_remove_like_post_remove_like_user_blocklist_server_and_more"),
    )

    operations = (migrations.RunPython(add_default),)
