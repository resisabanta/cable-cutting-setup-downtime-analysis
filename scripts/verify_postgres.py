"""Check an already-loaded, disposable PostgreSQL practice database.

Uses psql and standard PG* environment variables. Invalid insert probes run in
transactions that always roll back. No credentials are stored in this script.
"""
import csv
import io
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import load_and_validate
from analyze_data import summarize


def psql(sql):
    return subprocess.run(['psql', '-X', '-v', 'ON_ERROR_STOP=1', '-q', '-c', sql],
                          capture_output=True, text=True, check=False)


def query(sql):
    result = psql(f'COPY ({sql}) TO STDOUT WITH CSV HEADER')
    if result.returncode:
        raise RuntimeError(result.stderr)
    return list(csv.DictReader(io.StringIO(result.stdout)))


def main():
    rows = load_and_validate()
    counts = query('SELECT COUNT(*) AS count FROM synthetic_machine_events')
    if int(counts[0]['count']) != len(rows):
        raise AssertionError('PostgreSQL and CSV event counts differ')
    for field in ['machine_section', 'cause', 'shift', 'configuration_id', 'shift_date']:
        actual = query(f"SELECT {field}, COUNT(*) AS stop_count, SUM(duration_minutes) AS downtime_minutes "
                       f"FROM synthetic_machine_events WHERE event_type='unplanned_stop' GROUP BY {field}")
        expected = summarize(rows, field)
        normalized = lambda values: {r[field]: (int(r['stop_count']), int(r['downtime_minutes'])) for r in values}
        if normalized(actual) != normalized(expected):
            raise AssertionError(f'SQL/Python mismatch: {field}')
    # A new event ID avoids accidental duplicate-key failures masking the intended constraint.
    source = "FROM synthetic_machine_events WHERE event_type='unplanned_stop' ORDER BY event_id LIMIT 1"
    probes = {
        'duration': ("duration_minutes+1", 'shift', 'event_type', 'cause', '23514'),
        'shift': ('duration_minutes', "CASE WHEN shift='morning' THEN 'night' ELSE 'morning' END", 'event_type', 'cause', '23514'),
        'reason/type': ('duration_minutes', 'shift', "'setup'", 'cause', '23503'),
        'unknown cause': ('duration_minutes', 'shift', 'event_type', "'not_a_permitted_reason'", '23503'),
    }
    for name, (duration, shift, kind, cause, expected_state) in probes.items():
        sql = ("BEGIN; INSERT INTO synthetic_machine_events "
               "(event_id,machine_id,configuration_id,machine_section,shift,shift_date,event_type,cause,"
               "start_time,end_time,duration_minutes,action_taken) SELECT '__invalid_probe__',machine_id,"
               f"configuration_id,machine_section,{shift},shift_date,{kind},{cause},start_time,end_time,"
               f"{duration},action_taken {source}; ROLLBACK;")
        result = subprocess.run(['psql', '-X', '-v', 'ON_ERROR_STOP=1', '-v', 'VERBOSITY=verbose', '-q', '-c', sql],
                                capture_output=True, text=True, check=False)
        if not result.returncode or expected_state not in result.stderr:
            raise AssertionError(f'{name}: expected SQLSTATE {expected_state}; got {result.stderr}')
    if int(query('SELECT COUNT(*) AS count FROM synthetic_machine_events')[0]['count']) != len(rows):
        raise AssertionError('Probe changed dataset')
    print('PASS: SQL/Python counts and five aggregates match; four invalid inserts rejected and rolled back.')


if __name__ == '__main__':
    main()
