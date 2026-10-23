import copy
import unittest
from datetime import datetime,timedelta
from generate_data import generate_events
from analyze_data import summarize
from model import (read_csv, CONFIG_FILE, CONFIG_COLUMNS, validate_configurations,
                   validate_events, build_rules, shift_bounds)

class IntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configs=validate_configurations(read_csv(CONFIG_FILE,CONFIG_COLUMNS))
        cls.events=generate_events(cls.configs)

    def test_fixture_and_reproducibility(self):
        self.assertEqual(len(self.events),1000)
        self.assertEqual(len({r['configuration_id'] for r in self.events}),5)
        self.assertEqual(self.events,generate_events(self.configs))

    def test_reject_overlapping_intervals(self):
        rows=copy.deepcopy(self.events)
        other=dict(rows[0],event_id='OVERLAP');rows.append(other)
        with self.assertRaisesRegex(ValueError,'Overlapping'):validate_events(rows,self.configs)

    def test_reject_duplicate_id(self):
        rows=copy.deepcopy(self.events);rows.append(rows[0].copy())
        with self.assertRaisesRegex(ValueError,'Duplicate'):validate_events(rows,self.configs)

    def test_reject_rotary_event_without_rotary_box(self):
        row=next(r.copy() for r in self.events if r['configuration_id']=='SIM-CONFIG-05' and r['machine_section']=='cutting_stripping')
        row.update(event_type='setup',cause='rotary_box_calibration')
        with self.assertRaisesRegex(ValueError,'incompatible'):validate_events([row],self.configs)

    def test_reject_wrong_collection_equipment(self):
        row=next(r.copy() for r in self.events if r['configuration_id']=='SIM-CONFIG-02' and r['machine_section']=='collection_machine')
        row.update(event_type='unplanned_stop',cause='door_locking_system_issue')
        with self.assertRaisesRegex(ValueError,'incompatible'):validate_events([row],self.configs)

    def test_reject_fault_labeled_as_setup(self):
        row=next(r.copy() for r in self.events if r['event_type']=='unplanned_stop')
        row['event_type']='setup'
        with self.assertRaisesRegex(ValueError,'incompatible'):validate_events([row],self.configs)

    def test_reject_absent_csu(self):
        row=self.events[0].copy()
        row.update(configuration_id='SIM-CONFIG-02',machine_id='SIM-CUT-02',machine_section='centerstrip_csu')
        with self.assertRaisesRegex(ValueError,'incompatible'):validate_events([row],self.configs)

    def test_reject_cross_shift_event(self):
        row=self.events[0].copy();s=datetime.fromisoformat(row['start_time'])
        boundary=shift_bounds(s)[3];start=boundary-timedelta(minutes=1)
        row.update(start_time=start.isoformat(),end_time=(boundary+timedelta(minutes=1)).isoformat(),duration_minutes='2')
        with self.assertRaisesRegex(ValueError,'shift'):validate_events([row],self.configs)

    def test_reject_inexact_seconds(self):
        row=self.events[0].copy();end=datetime.fromisoformat(row['end_time'])+timedelta(seconds=30)
        row['end_time']=end.isoformat()
        with self.assertRaisesRegex(ValueError,'duration'):validate_events([row],self.configs)

    def test_night_shift_date(self):
        self.assertEqual(str(shift_bounds(datetime(2026,9,2,2))[1]),'2026-09-01')
        row=self.events[0].copy();row['shift_date']='2020-01-01'
        with self.assertRaisesRegex(ValueError,'shift'):validate_events([row],self.configs)

    def test_reject_duplicate_sequence(self):
        rows=copy.deepcopy(self.configs);rows[1]['line_sequence']=rows[0]['line_sequence']
        with self.assertRaisesRegex(ValueError,'Sequence'):validate_configurations(rows)

    def test_display_text_does_not_drive_logic(self):
        rows=copy.deepcopy(self.configs)
        for r in rows:r['equipment_description']='without rotary box, with random words'
        self.assertEqual(build_rules(self.configs),build_rules(rows))

    def test_summaries_reconcile(self):
        stops=[r for r in self.events if r['event_type']=='unplanned_stop']
        for field in ['machine_section','cause','shift','configuration_id','shift_date']:
            summary=summarize(self.events,field)
            self.assertEqual(sum(r['stop_count'] for r in summary),len(stops))
            self.assertEqual(sum(r['downtime_minutes'] for r in summary),sum(int(r['duration_minutes']) for r in stops))
            self.assertEqual(summary[-1]['cumulative_share_percent'],100)

if __name__=='__main__':unittest.main()
