# Database schema — v2

```mermaid
erDiagram
    machine_configurations ||--|{ event_rules : permits
    event_rules ||--o{ synthetic_machine_events : validates
    machine_configurations {
        TEXT configuration_id PK
        TEXT machine_id PK
        TEXT machine_section PK
        SMALLINT line_sequence
        TEXT equipment_description
        TEXT equipment_code
        TEXT rotary_box
        TEXT provenance
    }
    event_rules {
        TEXT configuration_id PK,FK
        TEXT machine_id PK,FK
        TEXT machine_section PK,FK
        TEXT event_type PK
        TEXT cause PK
        TEXT action_taken
        INTEGER sampling_weight
    }
    synthetic_machine_events {
        TEXT event_id PK
        TEXT configuration_id FK
        TEXT machine_id FK
        TEXT machine_section FK
        TEXT event_type FK
        TEXT cause FK
        TEXT shift
        DATE shift_date
        TIMESTAMP start_time
        TIMESTAMP end_time
        INTEGER duration_minutes
        TEXT action_taken
    }
```

- Configuration key: `(configuration_id, machine_id, machine_section)`; sequence also unique within machine/configuration.
- Rule key: `(configuration_id, machine_id, machine_section, event_type, cause)`.
- Each event references **one composite rule key**. The five FK labels do not mean five independent relationships.
- Rule `action_taken` is the generator's default; event `action_taken` is the illustrative recorded action.
- Explicit capabilities and equipment codes replace substring matching of descriptions.
- SQL checks enforce positive exact durations, shift boundaries, and basic capability consistency. Python validates configuration order and the permitted rule catalog.
- The loader checks overlaps once per imported batch; the schema alone does not prohibit future concurrent overlapping inserts.
- No configuration history, production exposure, or production/quality quantities are modeled.

Executable definition: [schema.sql](schema.sql). CSV import: [load_data.sql](load_data.sql).
