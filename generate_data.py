"""Reproducible, non-overlapping synthetic events for five cable-processing layouts."""
import argparse
import random
from collections import defaultdict
from datetime import datetime, timedelta
from model import (CONFIG_FILE, CONFIG_COLUMNS, RULE_FILE, RULE_COLUMNS, EVENT_FILE,
                   EVENT_COLUMNS, read_csv, write_csv, validate_configurations,
                   build_rules, validate_events, shift_bounds)

SEED=42
EVENT_COUNT=1000

def generate_events(configs, count=EVENT_COUNT, seed=SEED):
    if not 1<=count<=10000: raise ValueError('Use 1–10,000 events in this fixed one-month fixture')
    rng=random.Random(seed)
    groups=defaultdict(list); options=defaultdict(list); timelines=defaultdict(list)
    for row in configs: groups[(row['configuration_id'],row['machine_id'])].append(row)
    for rule in build_rules(configs):
        options[(rule['configuration_id'],rule['machine_id'],rule['machine_section'],rule['event_type'])].append(rule)
    events=[]
    for _ in range(count):
        cid,mid=rng.choice(list(groups));section=rng.choice(groups[(cid,mid)])['machine_section']
        kind=rng.choices(['unplanned_stop','setup','quality_check'],[62,23,15])[0]
        choices=options[(cid,mid,section,kind)]
        rule=rng.choices(choices,[int(r['sampling_weight']) for r in choices])[0]
        duration=rng.randint(3,42) if kind=='unplanned_stop' else rng.randint(5,35)
        for attempt in range(20000):
            shift_start=datetime(2026,9,1,6)+timedelta(hours=12*rng.randrange(60))
            start=shift_start+timedelta(minutes=rng.randrange(721-duration))
            end=start+timedelta(minutes=duration)
            if all(end<=s or start>=e for s,e in timelines[mid]): break
        else: raise ValueError('Cannot fit requested events into the sampling window')
        timelines[mid].append((start,end));shift,day,_,_=shift_bounds(start)
        events.append(dict(zip(EVENT_COLUMNS,['pending',mid,cid,section,shift,str(day),kind,
            rule['cause'],start.isoformat(timespec='minutes'),end.isoformat(timespec='minutes'),
            str(duration),rule['action_taken']])))
    events.sort(key=lambda r:(r['start_time'],r['machine_id']))
    for i,row in enumerate(events,1):row['event_id']=f'EVT-{i:05d}'
    return validate_events(events,configs)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=EVENT_COUNT)
    parser.add_argument('--seed',type=int,default=SEED)
    args=parser.parse_args()
    configs=validate_configurations(read_csv(CONFIG_FILE,CONFIG_COLUMNS))
    events=generate_events(configs,args.count,args.seed)
    write_csv(RULE_FILE,RULE_COLUMNS,build_rules(configs))
    write_csv(EVENT_FILE,EVENT_COLUMNS,events)
    print(f'Created and validated {len(events)} events; seed={args.seed}')

if __name__=='__main__':main()
