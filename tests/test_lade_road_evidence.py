import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]/"data/lade-study/road-snapshots"


def test_redistributed_road_bytes_match_declared_hashes_and_have_no_contacts():
    for i in range(1,5):
        path = ROOT/f"area{i}.osm"
        metadata = json.loads(path.with_suffix('.meta.json').read_text())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == metadata['redistribution']['sanitized_sha256']
        tree = ET.parse(path)
        assert tree.getroot().tag == 'osm'
        assert tree.findall('way')
        for element in tree.iter():
            assert not set(element.attrib) & {'uid','user','changeset'}
        for tag in tree.findall('.//tag'):
            assert not set(tag.get('k','').split(':')) & {'addr','contact','phone','email','fax','mobile','website'}


def test_quality_evidence_keeps_failed_batches_and_does_not_publish_individual_times():
    reports=[json.loads((ROOT/f"area{i}-quality.json").read_text()) for i in range(1,5)]
    assert [len(r['attempts']) for r in reports] == [35,13,8,4]
    assert all('selected' not in r for r in reports[:3])
    assert reports[3]['selected']['max_snap_m'] <= 50
    for report in reports:
        for attempt in report['attempts']:
            assert not set(attempt) & {'ds','last_accept','first_delivery','courier_id','order_id','lat','lng'}
        if 'selected' in report:
            assert not set(report['selected']) & {'ds','last_accept','first_delivery'}
    verification=json.loads((ROOT/'verification.json').read_text())
    assert verification['source_costs_unchanged'] is True
    assert verification['solver_not_rerun'] is True
    assert all(v['quality_identical'] for v in verification['areas'])
