-- Run from project root against empty v2 tables. Errors roll back the entire batch.
\set ON_ERROR_STOP on
BEGIN;
\copy machine_configurations (configuration_id,machine_id,line_sequence,machine_section,equipment_description,provenance,rotary_box,equipment_code) FROM 'data/machine_configurations.csv' WITH (FORMAT csv, HEADER true)
\copy event_rules (configuration_id,machine_id,machine_section,event_type,cause,action_taken,sampling_weight) FROM 'data/event_rules.csv' WITH (FORMAT csv, HEADER true)
\copy synthetic_machine_events (event_id,machine_id,configuration_id,machine_section,shift,shift_date,event_type,cause,start_time,end_time,duration_minutes,action_taken) FROM 'data/synthetic_machine_events.csv' WITH (FORMAT csv, HEADER true)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM (
            SELECT start_time, MAX(end_time) OVER (
                PARTITION BY machine_id ORDER BY start_time,event_id
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
            ) AS previous_end
            FROM synthetic_machine_events
        ) t WHERE start_time < previous_end
    ) THEN RAISE EXCEPTION 'Overlapping machine events; import rolled back'; END IF;
END $$;
COMMIT;
