import logging
from datetime import datetime

import django.utils.timezone
from django.conf import settings
from django.db import migrations, models, transaction

from laika.aws.dynamo import dynamo, env
from laika.utils.dates import YYYY_MM_DD, dynamo_timestamp_to_datetime
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.strings import camel_to_snake

logger = logging.getLogger('dataroom_migration')


def get_datarooms_from_dynamo():
    tables_response = dynamo.list_tables()
    table_names = tables_response.get('TableNames')
    name = [t for t in table_names if f'{env}-DataroomTable' in t]
    dataroom_response = dynamo.scan(TableName=name[0])
    datarooms = dataroom_response.get('Items', [])

    while 'LastEvaluatedKey' in dataroom_response:
        dataroom_response = dynamo.scan(
            TableName=name[0], ExclusiveStartKey=dataroom_response['LastEvaluatedKey']
        )
        datarooms.extend(dataroom_response.get('Items', []))

    return datarooms


def map_dynamo_dataroom(dataroom):
    d = {}
    for key in dataroom:
        value = list(dataroom[key].values())[0]
        pgKey = camel_to_snake(key)

        if key == 'createdAt' or key == 'updatedAt':
            date_time = dynamo_timestamp_to_datetime(int(value))
            value = datetime.strftime(date_time, YYYY_MM_DD)

        d[pgKey] = value

    return d


def get_or_create_user(apps, email, organization_id):
    if email == 'Unnasigned':
        return

    User = apps.get_model('user', 'User')
    user, _ = User.objects.get_or_create(
        email=email,
        organization_id=organization_id,
        defaults={
            'role': '',
            'last_name': '',
            'first_name': '',
            'is_active': False,
            'username': '',
        },
    )

    return user


def migrate_dataroom(apps, groups):
    Dataroom = apps.get_model('dataroom', 'Dataroom')
    Organization = apps.get_model('organization', 'Organization')

    datarooms = get_datarooms_from_dynamo()

    for d in datarooms:
        logger.info(f'\n Migrating dataroom: {d}')
        with transaction.atomic():
            dataroom = map_dynamo_dataroom(d)
            organization_id = dataroom.get('organization_id')
            organization = Organization.objects.filter(id=organization_id)
            organization_exists = organization.exists()
            if not organization_exists:
                logger.warning(
                    f'Skipping adding dataroom: {d.get("id")} '
                    f'in organization id: {organization_id}'
                )
            else:
                dataroom['owner'] = get_or_create_user(
                    apps, dataroom.get('owner'), organization_id
                )
                dataroom_data = exclude_dict_keys(
                    dataroom, ['members', 'collection', 'id']
                )
                stored_dataroom, _ = Dataroom.objects.update_or_create(
                    name=dataroom_data.get('name'),
                    organization_id=dataroom_data.get('organization_id'),
                    defaults={**dataroom_data},
                )


class Migration(migrations.Migration):
    dependencies = [
        ('organization', '0006_auto_20200421_1655'),
        ('evidence', '0003_add_additional_evidence_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dataroom', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataroom',
            name='created_at',
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='dataroom',
            name='name',
            field=models.CharField(default='', max_length=512),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='dataroom',
            name='organization',
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='dataroom',
                to='organization.Organization',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='dataroom',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='dataroom_owned',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='dataroom',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.CreateModel(
            name='DataroomEvidence',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'dataroom',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='dataroom_evidence',
                        to='dataroom.Dataroom',
                    ),
                ),
                (
                    'evidence',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='evidence.Evidence',
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name='dataroom',
            name='evidence',
            field=models.ManyToManyField(
                related_name='dataroom',
                through='dataroom.DataroomEvidence',
                to='evidence.Evidence',
            ),
        ),
        # migrations.RunPython(migrate_dataroom)
    ]
