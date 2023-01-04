# Generated by Django 3.1.12 on 2021-12-02 13:47

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('dashboard', '0014_add_action_item_to_view'),
    ]

    operations = [
        migrations.RunSQL(
            '''
                DROP VIEW IF exists dashboard_view;
                CREATE OR REPLACE VIEW dashboard_view AS
                SELECT ROW_NUMBER() OVER() as id, * FROM (
                    SELECT
                       pt.id as model_id,
                       oo.id AS organization_id,
                       cast(ps.id AS text) AS unique_action_item_id,
                       ps.created_at,
                       ps.updated_at,
                       ps.assignee_id,
                       ps.due_date,
                       ps.completed_on,
                       ps.status,
                       'playbook_task' AS TYPE,
                       concat(initcap(ps.group), ' subtask due in ', pt.name)
                       AS description,
                       concat('playbooks/', pp.id, '/', pt.id)
                       AS reference_url,
                       ps.sort_index,
                       ps.group
                    FROM program_subtask ps
                    left join public.program_task pt
                      ON pt.id = ps.task_id
                    left join public.program_program pp
                      ON pp.id = pt.program_id
                    left join public.organization_organization oo
                      ON oo.id = pp.organization_id
                    UNION
                    SELECT
                        du.id as model_id,
                        du.organization_id,
                        '' as unique_action_item_id,
                        du.created_at,
                        du.updated_at,
                        du.assignee_id,
                        du.due_date,
                        du.completed_on,
                        du.status,
                        dt.task_type AS TYPE,
                        du.description,
                        du.reference_url,
                        0 as sort_index,
                        '' as group
                    FROM dashboard_usertask du
                    INNER JOIN dashboard_task dt on du.task_id = dt.id
                    UNION
                    SELECT
                        co.id as model_id,
                        co.organization_id,
                        cast(co.id as text) as unique_action_item_id,
                        NULL as created_at,
                        NULL as updated_at,
                        aia.user_id as assignee_id,
                        ai.due_date as due_date,
                        ai.completion_date as completed_on,
                        ai.status as status,
                        'control' AS TYPE,
                        CONCAT(ai.metadata::json ->>'referenceId', ': ',
                        ai.name)
                        as description,
                        cast(co.id as varchar) as reference_url,
                        0 as sort_index,
                        '' as group
                    FROM action_item_actionitem ai
                    INNER JOIN control_control_action_items ca on
                    ai.id = ca.actionitem_id
                    INNER JOIN control_control co on co.id = ca.control_id
                    INNER JOIN action_item_actionitem_assignees aia
                    on aia.actionitem_id = ai.id
                    ) results;
                CREATE RULE update_dashboard_view AS ON UPDATE TO
                    dashboard_view DO INSTEAD NOTHING;
        ''',
            reverse_sql='',
        )
    ]
