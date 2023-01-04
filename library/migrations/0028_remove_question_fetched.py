from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('library', '0027_add_question_fetch_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='question',
            name='fetched',
        ),
    ]
