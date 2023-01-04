# Generated by Django 3.1.12 on 2021-08-11 21:07
from django.db import migrations


class Migration(migrations.Migration):
    def update_user_preferences(apps, schema_editor):
        user_model = apps.get_model('user', 'User')
        for user in user_model.objects.all():
            try:
                user.user_preferences['tables']['people']['columns'] = []
                user.save()
            except KeyError:
                pass

    dependencies = [
        ('user', '0052_add_security_and_training_fields'),
    ]

    operations = [migrations.RunPython(update_user_preferences)]
