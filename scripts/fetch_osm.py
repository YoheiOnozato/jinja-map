"""群馬県の神社を OpenStreetMap (Overpass API) から取得し、GeoJSON と集計を出力する。

標準ライブラリのみ。GitHub Actions 上で実行する想定。
出力:
  site/data/shrines.geojson  地図ページが読むデータ
  site/data/summary.json     件数・情報の充実度の集計
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
# ISO3166-2 JP-10 = 群馬県
QUERY = """
[out:json][timeout:180];
area["ISO3166-2"="JP-10"]->.a;
nwr["amenity"="place_of_worship"]["religion"="shinto"](area.a);
out center tags;
"""
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "site", "data")


def fetch():
    body = urllib.parse.urlencode({"data": QUERY}).encode()
    last = None
    for url in ENDPOINTS:
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    url, data=body, headers={"User-Agent": "jinja-map-gunma/0.1"}
                )
                with urllib.request.urlopen(req, timeout=240) as r:
                    return json.load(r)
            except Exception as e:  # noqa: BLE001
                last = e
                print(f"retry {url} ({attempt + 1}): {e}", file=sys.stderr)
                time.sleep(10 * (attempt + 1))
    raise SystemExit(f"Overpass 取得失敗: {last}")


def to_feature(el):
    tags = el.get("tags", {})
    if el["type"] == "node":
        lat, lon = el["lat"], el["lon"]
    else:
        c = el.get("center")
        if not c:
            return None
        lat, lon = c["lat"], c["lon"]
    enshrine = tags.get("enshrine") or tags.get("subject:wikidata") or ""
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
        "properties": {
            "id": f'{el["type"]}/{el["id"]}',
            "name": tags.get("name", ""),
            "name_en": tags.get("name:en", ""),
            "enshrine": enshrine,
            "wikipedia": tags.get("wikipedia", ""),
            "wikidata": tags.get("wikidata", ""),
            "website": tags.get("website", "") or tags.get("contact:website", ""),
        },
    }


def main():
    data = fetch()
    features = [f for f in (to_feature(e) for e in data.get("elements", [])) if f]
    total = len(features)
    named = sum(1 for f in features if f["properties"]["name"])
    summary = {
        "total": total,
        "with_name": named,
        "with_enshrine": sum(1 for f in features if f["properties"]["enshrine"]),
        "with_wikipedia": sum(1 for f in features if f["properties"]["wikipedia"]),
        "with_wikidata": sum(1 for f in features if f["properties"]["wikidata"]),
        "osm_timestamp": data.get("osm3s", {}).get("timestamp_osm_base", ""),
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "shrines.geojson"), "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh, ensure_ascii=False)
    with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
