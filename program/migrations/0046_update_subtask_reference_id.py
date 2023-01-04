import csv
import os

from django.db import migrations

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


def update_subtask_reference_id(apps, schema_editor):
    SubTask = apps.get_model('program', 'SubTask')
    for row in get_valid_rows():
        SubTask.objects.filter(text=row['Name'], reference_id__isnull=True).update(
            reference_id=row['subtask_reference_id']
        )


def get_valid_rows():
    with open(
        os.path.join(__location__, 'resources/subtask_mapping.csv'), mode='r'
    ) as csv_file:
        csv_reader = csv.DictReader(csv_file)
        valid_rows = []
        for row in csv_reader:
            if row['subtask_reference_id']:
                valid_rows.append(row)
        return valid_rows


class Migration(migrations.Migration):
    dependencies = [
        ('program', '0045_subtask_reference_id'),
    ]

    operations = [
        migrations.RunPython(update_subtask_reference_id),
    ]
