import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location("sanitize_roads", Path(__file__).resolve().parents[1]/"tools/sanitize_research_roads.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_quality_export_removes_private_fields_in_both_aliased_occurrences():
    row = {"orders": 21, "max_snap_m": 35.95, "last_accept": "private", "unknown": "private"}
    source = {"attempts": [row], "selected": row, "courier_id": "private"}
    public = module.public_quality_report(source)
    assert public == {"attempts": [{"orders": 21, "max_snap_m": 35.95}], "selected": {"orders": 21, "max_snap_m": 35.95}}
    assert source["selected"]["last_accept"] == "private"


def test_remove_contacts_without_changing_connectivity_or_routing_rules():
    raw = b'<osm><node id="1" lat="29" lon="106" uid="123"><tag k="addr:street" v="private"/><tag k="operator:phone" v="private"/><tag k="barrier" v="gate"/></node><node id="2" lat="29.1" lon="106.1"/><way id="3"><nd ref="1"/><nd ref="2"/><tag k="highway" v="residential"/><tag k="access" v="private"/><tag k="oneway" v="yes"/><tag k="website" v="private"/></way><relation id="4"><member type="way" ref="3" role="from"/><tag k="restriction" v="no_left_turn"/></relation></osm>'
    cleaned, removed = module.sanitize(raw)
    assert removed == 4
    a, b = ET.fromstring(raw), ET.fromstring(cleaned)
    for tree in (a,b):
        assert [(n.get('id'),n.get('lat'),n.get('lon')) for n in tree.findall('node')] == [('1','29','106'),('2','29.1','106.1')]
        assert [n.get('ref') for n in tree.findall('./way/nd')] == ['1','2']
    tags = {t.get('k'):t.get('v') for t in b.findall('.//tag')}
    assert tags == {'barrier':'gate','highway':'residential','access':'private','oneway':'yes','restriction':'no_left_turn'}
    assert 'uid' not in b.find('node').attrib


def test_cleaning_does_not_mutate_input_and_is_idempotent():
    raw = b'<osm><node id="1" lat="29" lon="106"/></osm>'
    first, count = module.sanitize(raw)
    second, count2 = module.sanitize(first)
    assert count == count2 == 0 and first == second
    assert raw == b'<osm><node id="1" lat="29" lon="106"/></osm>'
