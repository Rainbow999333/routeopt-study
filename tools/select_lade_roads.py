"""Private pre-optimization quality selection; preserve all source-group orders."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request



def main():
    p = argparse.ArgumentParser()
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--road-metadata', type=Path, required=True)
    p.add_argument('--osrm-url', required=True)
    p.add_argument('--label', choices=['area1','area2','area3','area4'], required=True)
    args = p.parse_args()
    import pandas as pd
    import pyarrow.parquet as pq
    from run_lade_case import loopback_base
    root = args.directory
    base_url = loopback_base(args.osrm_url)
    area_bbox = json.loads(args.road_metadata.read_text())['bbox_south_west_north_east']
    args.area = args.label
    target = root / ('road-selected-'+args.area+'-private.json')
    if (root/'delivery_cq.parquet').stat().st_size != 61844340:
        raise ValueError('unexpected pinned source size')
    if hashlib.sha256((root/'delivery_cq.parquet').read_bytes()).hexdigest() != 'ea503be5d475aa9a3ceb27f09ce6f910f48a02e78122428fbb4f9c724820323b':
        raise ValueError('pinned source hash mismatch')
    if target.exists() or (root/('road-selection-'+args.area+'.json')).exists():
        raise ValueError('selection already recorded')
    cols = ['order_id','region_id','city','courier_id','lng','lat','accept_time','delivery_time','ds']
    df = pq.read_table(root/'delivery_cq.parquet',columns=cols).to_pandas()
    keys=['ds','region_id','courier_id']; source_counts=df.groupby(keys).size()
    for c in ['accept_time','delivery_time']:
        df[c+'_parsed']=pd.to_datetime(df[c],format='%m-%d %H:%M:%S',errors='coerce')
    df=df[df.lng.between(105,111)&df.lat.between(28,33)&df.accept_time_parsed.notna()&df.delivery_time_parsed.notna()&(df.accept_time_parsed<=df.delivery_time_parsed)].copy()
    df['point']=list(zip(df.lng,df.lat))
    g=df.groupby(keys,sort=True).agg(n=('order_id','size'),unique=('order_id','nunique'),stops=('point','nunique'),last_accept=('accept_time_parsed','max'),first_delivery=('delivery_time_parsed','min'),s=('lat','min'),n_lat=('lat','max'),w=('lng','min'),e=('lng','max'))
    eligible=g[(g.n==source_counts.reindex(g.index))&(g.n==g.unique)&g.stops.between(20,30)&(g.last_accept<=g.first_delivery)&(g.n_lat-g.s<=.04)&(g.e-g.w<=.04)]
    (root/'candidate-batches-private.json').write_text(eligible.reset_index().to_json(orient='records',date_format='iso'))
    # Keep >=0.01 degree road buffer on all sides of the existing bounded extract.
    local=eligible[(eligible.s>=area_bbox[0]+.01)&(eligible.n_lat<=area_bbox[2]-.01)&(eligible.w>=area_bbox[1]+.01)&(eligible.e<=area_bbox[3]-.01)]
    report={'all_complete_eligible':len(eligible),'within_buffered_extract':len(local),'selection':'first lexicographic eligible complete group in fixed extract with all <=50m snaps and all-pairs reachable; no optimization inspected','attempts':[],'coordinate_datum':'unconfirmed; road snapping tests only the released-coordinates-as-WGS84 hypothesis'}
    for key,row in local.head(100).iterrows():
        part=df[(df.ds==key[0])&(df.region_id==key[1])&(df.courier_id==key[2])].sort_values(['delivery_time_parsed','order_id'])
        records=part[cols].to_dict(orient='records'); raw=json.dumps(records,ensure_ascii=False,indent=2).encode(); digest=hashlib.sha256(raw).hexdigest()
        points=list(dict.fromkeys(zip(part.lng,part.lat)))
        coords=';'.join(f'{x},{y}' for x,y in points)
        with urllib.request.urlopen(base_url+'/table/v1/driving/'+coords+'?annotations=distance,duration',timeout=20) as r:
            b=r.read(1024*1024+1)
        assert len(b)<=1024*1024
        data=json.loads(b); assert data['code']=='Ok'
        snaps=[max(a['distance'],b['distance']) for a,b in zip(data['sources'],data['destinations'])]
        unreachable=sum(v is None for row in data['distances'] for v in row)
        report['attempts'].append({'source_group_sha256':digest,'ds':int(key[0]),'orders':len(part),'stops':len(points),'max_snap_m':max(snaps),'over_50m':sum(s>50 for s in snaps),'unreachable_cells':unreachable})
        if max(snaps)<=50 and unreachable==0:
            target.write_bytes(raw)
            (root/('road-selected-'+args.area+'-osrm-private.json')).write_bytes(b)
            report['selected']=report['attempts'][-1]
            report['selected']['last_accept']=part.accept_time.max()
            report['selected']['first_delivery']=part.delivery_time.min()
            break
    (root/('road-selection-'+args.area+'.json')).write_text(json.dumps(report,indent=2))
    print(json.dumps({'eligible':len(eligible),'attempted':len(report['attempts']),'selected':report.get('selected')}))


if __name__ == '__main__':
    main()
