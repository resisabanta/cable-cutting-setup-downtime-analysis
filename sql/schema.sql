-- Version 2: run in a NEW database. This is not an automatic v1 migration.
\set ON_ERROR_STOP on
BEGIN;
CREATE TABLE machine_configurations (
    configuration_id TEXT NOT NULL CHECK (btrim(configuration_id) <> ''),
    machine_id TEXT NOT NULL CHECK (btrim(machine_id) <> ''),
    line_sequence SMALLINT NOT NULL CHECK (line_sequence > 0),
    machine_section TEXT NOT NULL,
    equipment_description TEXT NOT NULL CHECK (btrim(equipment_description) <> ''),
    provenance TEXT NOT NULL CHECK (provenance IN ('user_example','synthetic_variant')),
    rotary_box TEXT NOT NULL CHECK (rotary_box IN ('present','absent','unknown')),
    equipment_code TEXT NOT NULL,
    PRIMARY KEY (configuration_id,machine_id,machine_section),
    UNIQUE (configuration_id,machine_id,line_sequence),
    CHECK ((equipment_code='powerstrip_9500_rotary' AND rotary_box='present') OR
           (equipment_code='powerstrip_9500_nonrotary' AND rotary_box='absent') OR
           (equipment_code NOT IN ('powerstrip_9500_rotary','powerstrip_9500_nonrotary') AND rotary_box='unknown'))
);
CREATE TABLE event_rules (
    configuration_id TEXT NOT NULL,
    machine_id TEXT NOT NULL,
    machine_section TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('unplanned_stop','setup','quality_check')),
    cause TEXT NOT NULL CHECK (btrim(cause) <> ''),
    action_taken TEXT NOT NULL CHECK (btrim(action_taken) <> ''),
    sampling_weight INTEGER NOT NULL CHECK (sampling_weight > 0),
    PRIMARY KEY (configuration_id,machine_id,machine_section,event_type,cause),
    FOREIGN KEY (configuration_id,machine_id,machine_section)
        REFERENCES machine_configurations(configuration_id,machine_id,machine_section)
);
CREATE TABLE synthetic_machine_events (
    event_id TEXT PRIMARY KEY CHECK (btrim(event_id) <> ''),
    machine_id TEXT NOT NULL,
    configuration_id TEXT NOT NULL,
    machine_section TEXT NOT NULL,
    shift TEXT NOT NULL CHECK (shift IN ('morning','night')),
    shift_date DATE NOT NULL,
    event_type TEXT NOT NULL,
    cause TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    action_taken TEXT NOT NULL CHECK (btrim(action_taken) <> ''),
    CHECK (end_time > start_time),
    CHECK (EXTRACT(EPOCH FROM (end_time-start_time)) = duration_minutes*60),
    CHECK (start_time >= shift_date + CASE WHEN shift='morning' THEN TIME '06:00' ELSE TIME '18:00' END),
    CHECK (end_time <= shift_date + CASE WHEN shift='morning' THEN TIME '06:00' ELSE TIME '18:00' END + INTERVAL '12 hours'),
    FOREIGN KEY (configuration_id,machine_id,machine_section,event_type,cause)
        REFERENCES event_rules(configuration_id,machine_id,machine_section,event_type,cause)
);
CREATE INDEX idx_events_machine_time ON synthetic_machine_events(machine_id,start_time);
CREATE INDEX idx_events_configuration ON synthetic_machine_events(configuration_id,event_type);
COMMIT;
