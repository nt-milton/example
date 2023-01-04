# Generated by Django 3.2.13 on 2022-05-10 05:40

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('fieldwork', '0052_attachment_has_been_submitted'),
    ]

    operations = [
        migrations.RunSQL(
            '''
            BEGIN;
            UPDATE
                fieldwork_attachment fa
            SET
                has_been_submitted = true
            WHERE
                EXISTS (
                SELECT
                    id
                FROM
                    fieldwork_evidence fe
                WHERE
                    fa.evidence_id = fe.id
                    AND (fe.status = 'submitted'
                        OR fe.status = 'auditor_accepted'));
            COMMIT;
        '''
        )
    ]
