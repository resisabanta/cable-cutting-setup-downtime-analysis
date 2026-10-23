"""Validate all data and export downtime summaries for Power BI or spreadsheet use."""
from collections import defaultdict
from model import ROOT, load_and_validate, write_csv

def summarize(rows, field):
    groups=defaultdict(lambda:[0,0])
    for row in rows:
        if row['event_type']=='unplanned_stop':
            groups[row[field]][0]+=1;groups[row[field]][1]+=int(row['duration_minutes'])
    total=sum(v[1] for v in groups.values())
    cumulative=0; result=[]
    for key,(count,minutes) in sorted(groups.items(),key=lambda kv:(-kv[1][1],kv[0])):
        cumulative+=minutes
        result.append({field:key,'stop_count':count,'downtime_minutes':minutes,
            'mean_stop_minutes':round(minutes/count,2),
            'downtime_share_percent':round(100*minutes/total,2),
            'cumulative_share_percent':round(100*cumulative/total,2)})
    return result

def main():
    rows=load_and_validate(); stops=[r for r in rows if r['event_type']=='unplanned_stop']
    print(f'Validated {len(rows)} events: {len(stops)} unplanned stops, '
          f'{sum(int(r["duration_minutes"]) for r in stops)} minutes')
    for field in ['machine_section','cause','shift','configuration_id','shift_date']:
        summary=summarize(rows,field)
        columns=[field,'stop_count','downtime_minutes','mean_stop_minutes',
                 'downtime_share_percent','cumulative_share_percent']
        write_csv(ROOT/'reports'/f'downtime_by_{field}.csv',columns,summary)
    print('Wrote five reconciled summaries in reports/. Raw totals are not reliability rankings.')

if __name__=='__main__':main()
