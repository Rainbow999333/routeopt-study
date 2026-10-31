"""Download one bounded OSM road extract; never used by the public website."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

MAX_BYTES = 16 * 1024 * 1024
ENDPOINT = "https://overpass-api.de/api/interpreter"


def build_query(bbox):
    south, west, north, east = bbox
    if not (-90 <= south < north <= 90 and -180 <= west < east <= 180):
        raise ValueError("invalid bounding box")
    if north - south > 0.15 or east - west > 0.15:
        raise ValueError("extract limited to 0.15 degrees per dimension")
    box = ",".join(str(float(v)) for v in bbox)
    return ('[out:xml][timeout:60][maxsize:67108864];'
            f'way["highway"]["highway"!~"^(footway|path|steps|cycleway|pedestrian|bridleway|'
            f'construction|proposed|abandoned|platform)$"]({box})->.roads;'
            '(.roads;rel(bw.roads)["type"="restriction"];);(._;>;);out body;')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bbox", nargs=4, type=float, default=[29.49, 106.535, 29.56, 106.625])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError("refusing to overwrite a saved extract; choose a new snapshot name")
    query = build_query(args.bbox)
    request = urllib.request.Request(ENDPOINT,
        data=urllib.parse.urlencode({"data": query}).encode(),
        headers={"User-Agent": "routeopt-study/0.1 (student offline routing experiment)",
                 "Accept": "application/xml"})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("extract exceeds 16 MiB; choose a smaller area")
    root = ET.fromstring(data)
    if root.tag != "osm" or root.find("remark") is not None:
        raise ValueError("Overpass did not return a complete OSM extract")
    for element in root.iter():
        for field in ("uid", "user", "changeset"):
            element.attrib.pop(field, None)
    sanitized = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(sanitized)
    metadata = {"source": ENDPOINT, "query": query, "bbox_south_west_north_east": args.bbox,
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
                "osm_base": root.find("meta").get("osm_base") if root.find("meta") is not None else None,
                "original_response_sha256": hashlib.sha256(data).hexdigest(),
                "saved_extract_sha256": hashlib.sha256(sanitized).hexdigest(),
                "saved_bytes": len(sanitized), "nodes": len(root.findall("node")),
                "ways": len(root.findall("way")), "relations": len(root.findall("relation")),
                "license": "ODbL-1.0", "attribution": "© OpenStreetMap contributors",
                "license_url": "https://www.openstreetmap.org/copyright",
                "privacy": "OSM contributor usernames, user IDs and changeset IDs removed"}
    args.out.with_suffix(".meta.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2),
                                                  encoding="utf-8")
    # Keep terminal output safe even on a legacy Windows GBK console.
    print(json.dumps(metadata, ensure_ascii=True))


if __name__ == "__main__":
    main()
