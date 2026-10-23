"""Shared event rules and validation; equipment descriptions are display text only."""
import csv
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / 'data/machine_configurations.csv'
EVENT_FILE = ROOT / 'data/synthetic_machine_events.csv'
RULE_FILE = ROOT / 'data/event_rules.csv'
CONFIG_COLUMNS = ['configuration_id', 'machine_id', 'line_sequence', 'machine_section',
                  'equipment_description', 'provenance', 'rotary_box', 'equipment_code']
EVENT_COLUMNS = ['event_id', 'machine_id', 'configuration_id', 'machine_section', 'shift',
                 'shift_date', 'event_type', 'cause', 'start_time', 'end_time',
                 'duration_minutes', 'action_taken']
RULE_COLUMNS = ['configuration_id', 'machine_id', 'machine_section', 'event_type',
                'cause', 'action_taken', 'sampling_weight']
SECTIONS = ['cable_feeder', 'v_loop', 'letter_marking', 'centerstrip_csu',
            'teza_transfer_ribbon_marking', 'cutting_stripping', 'collection_machine']
FAULTS = {
    'cable_feeder': ['feed_interruption', 'cable_path_issue'],
    'v_loop': ['loop_tension_variation', 'buffer_signal_issue'],
    'letter_marking': ['mark_position_issue', 'mark_legibility_issue'],
    'centerstrip_csu': ['center_strip_defect', 'csu_cycle_fault'],
    'teza_transfer_ribbon_marking': ['incomplete_ribbon_transfer', 'ribbon_feed_fault'],
    'powerstrip_9500': ['cut_length_deviation', 'incomplete_cut', 'strip_quality_defect'],
    'powerstrip_9500_rotary': ['cut_length_deviation', 'incomplete_cut', 'rotary_cut_fault'],
    'powerstrip_9500_nonrotary': ['cut_length_deviation', 'incomplete_cut', 'strip_quality_defect'],
    'integrated_kuka_cell': ['door_locking_system_issue', 'paper_taping_issue'],
    'cablecoiler_1300': ['cablecoiler_feed_or_coiling_issue'],
    'wirestacker_1000': ['wirestacker_stacking_issue'],
    'active_offloader': ['active_offloader_issue'],
    'passive_offloader': ['passive_offloader_issue'],
}
EQUIPMENT_SECTION = {k: k for k in SECTIONS[:-2]}
EQUIPMENT_SECTION.update({k:'cutting_stripping' for k in
                          ['powerstrip_9500','powerstrip_9500_rotary','powerstrip_9500_nonrotary']})
EQUIPMENT_SECTION.update({k:'collection_machine' for k in
                          ['integrated_kuka_cell','cablecoiler_1300','wirestacker_1000',
                           'active_offloader','passive_offloader']})

def read_csv(path, columns):
    with Path(path).open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f'{path}: missing or duplicate headers')
        if set(reader.fieldnames) != set(columns):
            raise ValueError(f'{path}: expected columns {columns}')
        rows = list(reader)
    if not rows:
        raise ValueError(f'{path}: empty dataset')
    for i, row in enumerate(rows, 2):
        if None in row or any(v is None or not v.strip() for v in row.values()):
            raise ValueError(f'{path}:{i}: missing value or malformed row')
    return rows

def write_csv(path, columns, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)

def config_key(row):
    return row['configuration_id'], row['machine_id'], row['machine_section']

def rule_key(row):
    return (*config_key(row), row['event_type'], row['cause'])

def validate_configurations(rows):
    seen=set(); groups=defaultdict(list); machine_configs=defaultdict(set)
    for row in rows:
        key=config_key(row)
        if key in seen: raise ValueError('Duplicate configuration section')
        seen.add(key)
        if EQUIPMENT_SECTION.get(row['equipment_code']) != row['machine_section']:
            raise ValueError('Equipment does not belong to section')
        expected={'powerstrip_9500_rotary':'present', 'powerstrip_9500_nonrotary':'absent'}.get(row['equipment_code'],'unknown')
        if row['rotary_box'] != expected: raise ValueError('Invalid rotary-box capability')
        if row['provenance'] not in {'user_example','synthetic_variant'}: raise ValueError('Invalid provenance')
        groups[key[:2]].append(row);machine_configs[row['machine_id']].add(row['configuration_id'])
    if any(len(v)!=1 for v in machine_configs.values()):
        raise ValueError('This version supports one fixed configuration per machine')
    for group in groups.values():
        ordered=sorted(group,key=lambda r:int(r['line_sequence']))
        if [int(r['line_sequence']) for r in ordered] != list(range(1,len(ordered)+1)):
            raise ValueError('Sequence must be unique and contiguous')
        sections=[r['machine_section'] for r in ordered]
        if sections != [s for s in SECTIONS if s in sections]: raise ValueError('Invalid process order')
        if not {'cable_feeder','cutting_stripping','collection_machine'} <= set(sections):
            raise ValueError('Missing essential section')
        if len({r['provenance'] for r in group}) != 1: raise ValueError('Mixed provenance')
    return rows

def build_rules(configurations):
    rules=[]
    for row in configurations:
        for kind, causes in [('unplanned_stop',FAULTS[row['equipment_code']]),
                             ('setup',['planned_changeover']),
                             ('quality_check',['scheduled_sample_inspection'])]:
            if kind=='setup' and row['rotary_box']=='present':
                causes=causes+['rotary_box_calibration']
            for cause in causes:
                rules.append(dict(zip(RULE_COLUMNS,[*config_key(row),kind,cause,
                    {'unplanned_stop':'Investigate recorded symptom; log simulated corrective action',
                     'setup':'Complete simulated setup and verify sample',
                     'quality_check':'Record simulated sample inspection result'}[kind],
                    '5' if cause=='door_locking_system_issue' else '1'])))
    return rules

def shift_bounds(start):
    if 6 <= start.hour < 18:
        return 'morning', start.date(), start.replace(hour=6,minute=0,second=0,microsecond=0), start.replace(hour=18,minute=0,second=0,microsecond=0)
    shift_start=start.replace(hour=18,minute=0,second=0,microsecond=0)
    if start.hour<6: shift_start-=timedelta(days=1)
    return 'night',shift_start.date(),shift_start,shift_start+timedelta(hours=12)

def validate_events(rows, configurations):
    allowed={rule_key(r) for r in build_rules(configurations)}
    seen=set(); timelines=defaultdict(list)
    for row in rows:
        if not all(isinstance(row.get(k),str) and row[k].strip() for k in EVENT_COLUMNS):
            raise ValueError('Missing event value')
        if row['event_id'] in seen: raise ValueError('Duplicate event ID')
        seen.add(row['event_id'])
        if rule_key(row) not in allowed: raise ValueError('Event rule incompatible with installed equipment or event type')
        start=datetime.fromisoformat(row['start_time']);end=datetime.fromisoformat(row['end_time'])
        if start.tzinfo or end.tzinfo: raise ValueError('Use local naive timestamps for this September fixture')
        if (end-start).total_seconds() != int(row['duration_minutes'])*60 or end<=start:
            raise ValueError('Invalid exact duration')
        shift,day,_,boundary=shift_bounds(start)
        if row['shift'] != shift or row['shift_date'] != str(day) or end>boundary:
            raise ValueError('Incorrect shift/date or event crosses shift boundary')
        timelines[row['machine_id']].append((start,end))
    for intervals in timelines.values():
        previous_end=None
        for start,end in sorted(intervals):
            if previous_end is not None and start<previous_end: raise ValueError('Overlapping machine events')
            previous_end=end
    return rows

def load_and_validate():
    configs=validate_configurations(read_csv(CONFIG_FILE,CONFIG_COLUMNS))
    rules=read_csv(RULE_FILE,RULE_COLUMNS)
    expected={tuple(r[k] for k in RULE_COLUMNS) for r in build_rules(configs)}
    if len(rules)!=len(expected) or {tuple(r[k] for k in RULE_COLUMNS) for r in rules} != expected:
        raise ValueError('event_rules.csv differs from configuration rules; regenerate data')
    return validate_events(read_csv(EVENT_FILE,EVENT_COLUMNS),configs)
