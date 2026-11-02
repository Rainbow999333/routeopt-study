"""Remove non-routing contact/address metadata from a redistributable OSM copy."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def public_quality_report(report):
    """Whitelist each occurrence: selected may alias an attempts entry upstream."""
    fields = {"source_group_sha256", "orders", "stops", "max_snap_m", "over_50m", "unreachable_cells"}
    output = {key: report[key] for key in (
        "all_complete_eligible", "within_buffered_extract", "selection", "coordinate_datum") if key in report}
    output["attempts"] = [{k: v for k, v in row.items() if k in fields} for row in report["attempts"]]
    if "selected" in report:
        output["selected"] = {k: v for k, v in report["selected"].items() if k in fields}
    return output


def sanitize(raw):
    root = ET.fromstring(raw)
    if root.tag != "osm":
        raise ValueError("expected OSM XML")
    removed = 0
    for element in root.iter():
        for field in ("uid", "user", "changeset"):
            if field in element.attrib:
                del element.attrib[field]; removed += 1
        for tag in list(element.findall("tag")):
            parts = set(tag.get("k", "").split(":"))
            if parts & {"addr", "contact", "phone", "email", "fax", "mobile", "website"}:
                element.remove(tag); removed += 1
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), removed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.out.exists() or args.out.resolve() == args.input.resolve():
        raise ValueError("refusing to overwrite unique source or existing output")
    if args.input.stat().st_size > 16*1024*1024:
        raise ValueError("OSM input exceeds 16MiB")
    raw = args.input.read_bytes()
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    digest = hashlib.sha256(raw).hexdigest()
    if digest != metadata["saved_extract_sha256"]:
        raise ValueError("OSM input differs from acquisition metadata")
    output, removed = sanitize(raw)
    metadata["redistribution"] = {
        "original_saved_extract_sha256": digest, "removed_non_routing_fields": removed,
        "sanitized_sha256": hashlib.sha256(output).hexdigest(),
        "note": "Only contributor identity and contact/address tags removed; preserve original private input; route-cost equivalence checked separately",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(output)
    args.out.with_suffix(".meta.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    print(json.dumps(metadata["redistribution"]))


if __name__ == "__main__":
    main()
