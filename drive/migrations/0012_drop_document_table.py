# Generated by Django 3.1.2 on 2021-05-31 20:47

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('drive', '0011_delete_tagsandsystemtags'),
    ]

    operations = [
        migrations.RunSQL(
            '''
            DROP TABLE IF EXISTS document_document
        '''
        ),
    ]
