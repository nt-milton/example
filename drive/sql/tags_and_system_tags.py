TAGS_AND_SYSTEM_TAGS = '''
CREATE OR REPLACE VIEW tags_and_system_tags AS
WITH tags_and_system_tags(organization_id, tag_id, tag_name) AS (
SELECT drive.organization_id AS organization_id,
       subtask_tags.id       AS tag_id,
       subtask_tags.name     AS tag_name
FROM drive_driveevidence drive_evidence
         INNER JOIN drive_drive drive
                    ON drive.id = drive_evidence.drive_id
         INNER JOIN evidence_evidence evidence
                    ON evidence.id = drive_evidence.evidence_id
         INNER JOIN evidence_systemtagevidence system_tag_evidence
                   ON evidence.id = system_tag_evidence.evidence_id
         INNER JOIN tag_tag system_tags
                    ON system_tags.id = system_tag_evidence.tag_id
         INNER JOIN program_subtask evidence_subtasks
                   ON evidence_subtasks.id = system_tags."name"::uuid
         INNER JOIN program_subtasktag evidence_subtask_tags
                   ON evidence_subtask_tags.subtask_id = evidence_subtasks.id
         LEFT JOIN tag_tag subtask_tags
                    ON subtask_tags.id = evidence_subtask_tags.tag_id

UNION

SELECT drive.organization_id AS organization_id,
       evidence_tags.id      AS tag_id,
       evidence_tags.name    AS tag_name
FROM drive_driveevidence drive_evidence
         INNER JOIN drive_drive drive
                    ON drive.id = drive_evidence.drive_id
         INNER JOIN evidence_evidence evidence
                    ON evidence.id = drive_evidence.evidence_id
         LEFT JOIN evidence_tagevidence tag_evidence
                   ON tag_evidence.evidence_id = evidence.id
         INNER JOIN tag_tag evidence_tags
                    ON evidence_tags.id = tag_evidence.tag_id
ORDER BY tag_id )
SELECT tags.organization_id,
       tags.tag_id,
       ROW_NUMBER() OVER (ORDER BY tags.tag_id) AS id
FROM tags_and_system_tags tags
ORDER BY tags.tag_name
'''
