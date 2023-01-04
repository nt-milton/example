CREATE OR REPLACE FUNCTION find_questions(questions TEXT[], threshold DECIMAL,
 org_id uuid)
    RETURNS TABLE
            (
                input            TEXT,
                question_id      INTEGER,
                library_entry_id INTEGER,
                question_index   INTEGER
            )
as
$$
DECLARE
    question_id      INTEGER;
    input            TEXT;
    question_index   INTEGER;
    library_entry_id INTEGER;
BEGIN
    question_index := 0;
    FOREACH input IN ARRAY questions
        LOOP
            BEGIN
                question_index := question_index + 1;
                SELECT lq.id, lq.library_entry_id
                INTO STRICT question_id, library_entry_id
                FROM library_question lq INNER JOIN library_libraryentry le
                  ON le.id=lq.library_entry_id
                  AND le.organization_id=org_id
                WHERE to_tsvector('english', lq.text) @@
                      phraseto_tsquery(input)
                ORDER BY similarity(lq.text, input) DESC
                LIMIT 1;
                RETURN QUERY SELECT input,
                                    question_id,
                                    library_entry_id,
                                    question_index;
            EXCEPTION
                WHEN NO_DATA_FOUND THEN
                    SELECT lq.id,
                           lq.library_entry_id
                    INTO question_id, library_entry_id
                    FROM library_question lq INNER JOIN library_libraryentry le
                      ON le.id=lq.library_entry_id
                      AND le.organization_id=org_id
                    WHERE lq.text % input
                      AND similarity(lq.text, input) >= threshold
                    ORDER BY similarity(lq.text, input) DESC;
                    RETURN QUERY SELECT input,
                                        question_id,
                                        library_entry_id,
                                        question_index;
            END;

        END LOOP;
    RETURN;

END;
$$ LANGUAGE plpgsql;
