# Generated by Django 3.2.13 on 2022-06-23 20:20

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('access_review', '0010_user_access_review_event'),
    ]

    operations = [
        migrations.RunSQL(
            '''
    BEGIN;
    INSERT into
       public.auth_group_permissions (group_id, permission_id) (
       SELECT
            g.id AS group_id, p.id AS permission_id 
       FROM
          public.auth_group g 
          cross join 
             public.auth_permission p 
       WHERE
          (
             g.name ilike 'premium_super' 
             OR g.name ilike 'premium_admin' 
             OR g.name ilike 'premium_member'
          )
          AND p.codename = ANY (array ['add_accessreviewuserevent'])
        )
    ON CONFLICT DO NOTHING;
    COMMIT;
    '''
        )
    ]
