DASHBOARD_VIEW = """
    DROP VIEW IF exists dashboard_view;
    CREATE OR REPLACE VIEW dashboard_view AS
    SELECT ROW_NUMBER() OVER() as id, * FROM (
        SELECT
            pt.id as model_id,
            oo.id AS organization_id,
            '' as reference_id,
            '' as reference_name,
            false as is_recurrent,
            false as is_required,
            cast(ps.id AS text) AS unique_action_item_id,
            ps.created_at,
            ps.updated_at,
            ps.assignee_id,
            null::timestamp as start_date,
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
            '' as reference_id,
            '' as reference_name,
            false as is_recurrent,
            false as is_required,
            '' as unique_action_item_id,
            du.created_at,
            du.updated_at,
            du.assignee_id,
            null::timestamp as start_date,
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
            uu.organization_id as model_id,
            uu.organization_id,
            '' as reference_id,
            '' as reference_name,
            false as is_recurrent,
            false as is_required,
            cast(aia.id as text) as unique_action_item_id,
            NULL as created_at,
            NULL as updated_at,
            aiaa.user_id as assignee_id,
            aia.start_date as start_date,
            aia.due_date,
            aia.completion_date as completed_on,
            aia.status,
            aia.metadata->>'type' as type,
            aia.description,
            aia.metadata->>'type' as reference_url,
            0 as sort_index,
            '' as group
        from action_item_actionitem aia
        INNER JOIN action_item_actionitem_assignees as aiaa
        ON aia.id = aiaa.actionitem_id
        INNER JOIN user_user uu ON uu.id = aiaa.user_id
        WHERE aia.metadata @> '{"type": "quick_start"}'
        OR aia.metadata @> '{"type": "access_review"}'
        OR aia.metadata @> '{"type": "policy"}'
        ) results;
    CREATE RULE update_dashboard_view AS ON UPDATE TO
    dashboard_view DO INSTEAD NOTHING;
    CREATE RULE delete_dashboard_view AS ON DELETE TO
    dashboard_view DO INSTEAD NOTHING;
"""


MY_COMPLIANCE_VIEW = """
    DROP VIEW IF exists my_compliance_view;
    CREATE OR REPLACE VIEW my_compliance_view AS
    SELECT ROW_NUMBER() OVER() as id, * FROM (
        SELECT
            du.id as model_id,
            du.organization_id,
            '' as reference_id,
            '' as reference_name,
            false as is_recurrent,
            false as is_required,
            '' as unique_action_item_id,
            du.created_at,
            du.updated_at,
            du.assignee_id,
            null::timestamp as start_date,
            du.due_date,
            du.completed_on,
            du.status,
            dt.task_type AS TYPE,
            du.description,
            du.reference_url,
            0 as sort_index,
            'group' as group
        FROM dashboard_usertask du
        INNER JOIN dashboard_task dt on du.task_id = dt.id
        UNION
        SELECT
            uu.organization_id as model_id,
            uu.organization_id,
            '' as reference_id,
            '' as reference_name,
            false as is_recurrent,
            false as is_required,
            cast(aia.id as text) as unique_action_item_id,
            NULL as created_at,
            NULL as updated_at,
            aiaa.user_id as assignee_id,
            aia.start_date as start_date,
            aia.due_date,
            aia.completion_date as completed_on,
            aia.status,
            aia.metadata->>'type' as type,
            aia.description,
            aia.metadata->>'type' as reference_url,
            0 as sort_index,
            'group' as group
        from action_item_actionitem aia
        INNER JOIN action_item_actionitem_assignees as aiaa
        ON aia.id = aiaa.actionitem_id
        INNER JOIN user_user uu ON uu.id = aiaa.user_id
        WHERE aia.metadata @> '{"type": "quick_start"}'
        OR aia.metadata @> '{"type": "access_review"}'
        OR aia.metadata @> '{"type": "policy"}'
        UNION
        SELECT
            co.id as model_id,
            co.organization_id,
            /* reference_id & reference_name columns added to display
            control reference_id and control name for control action items*/
            co.reference_id,
            co.name as reference_name,
            /* is_required & is_recurrent columns added to by able to filter
            by required or recurrent action items */
            ai.is_recurrent as is_recurrent,
            ai.is_required as is_required,
            cast(ai.id as text) as unique_action_item_id,
            NULL as created_at,
            NULL as updated_at,
            aia.user_id as assignee_id,
            ai.start_date as start_date,
            ai.due_date as due_date,
            ai.completion_date as completed_on,
            ai.status as status,
            'control' AS TYPE,
            CONCAT(ai.metadata::json ->>'referenceId', ': ',
            ai.name)
            as description,
            cast(co.id as varchar) as reference_url,
            0 as sort_index,
            'group' as group
        FROM action_item_actionitem ai
        INNER JOIN control_control_action_items ca on
        ai.id = ca.actionitem_id
        INNER JOIN control_control co on co.id = ca.control_id
        INNER JOIN action_item_actionitem_assignees aia
        on aia.actionitem_id = ai.id
        ) results;
    CREATE RULE update_my_compliance_view AS ON UPDATE TO
    my_compliance_view DO INSTEAD NOTHING;
    CREATE RULE delete_my_compliance_view AS ON DELETE TO
    my_compliance_view DO INSTEAD NOTHING;
"""
