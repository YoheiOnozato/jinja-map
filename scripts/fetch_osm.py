"""関東1都6県の神社を OpenStreetMap (Overpass API) から取得し、GeoJSON と集計を出力する。

標準ライブラリのみ。GitHub Actions 上で実行する想定。
出力:
  build/osm.geojson        OSM の神社（中間データ）
  build/osm_summary.json   件数の集計
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
# 関東1都6県（ISO3166-2）
PREFS = [("JP-08", "茨城県"), ("JP-09", "栃木県"), ("JP-10", "群馬県"), ("JP-11", "埼玉県"),
         ("JP-12", "千葉県"), ("JP-13", "東京都"), ("JP-14", "神奈川県")]
QUERY = """
[out:json][timeout:300];
area["ISO3166-2"="%s"]->.a;
(
  nwr["religion"="shinto"](area.a);
  nwr["amenity"="place_of_worship"]["name"~"神社|神宮|八幡宮|稲荷|天満宮|大社|宮$"](area.a);
  nwr["building"="shrine"](area.a);
);
out center tags;
"""
KOFUN_QUERY = """
[out:json][timeout:300];
area["ISO3166-2"="%s"]->.a;
(
  nwr["historic"="archaeological_site"]["archaeological_site"="tumulus"](area.a);
  nwr["historic"="tomb"]["tomb"="tumulus"](area.a);
  nwr["historic"]["name"~"古墳|古墳群|塚古墳"](area.a);
  nwr["name"~"古墳$|古墳群$"]["amenity"!="place_of_worship"]["religion"!="shinto"]["highway"!~"."]["railway"!~"."](area.a);
);
out center tags;
"""
CASTLE_QUERY = """
[out:json][timeout:300];
area["ISO3166-2"="%s"]->.a;
(
  nwr["historic"="castle"](area.a);
  nwr["castle_type"](area.a);
  nwr["historic"="ruins"]["ruins"="castle"](area.a);
  nwr["historic"]["name"~"城跡|城址|城趾|陣屋|館跡|砦跡|[^神社]城$"](area.a);
);
out center tags;
"""
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "build")


def fetch(iso, query=None):
    body = urllib.parse.urlencode({"data": (query or QUERY) % iso}).encode()
    last = None
    for url in ENDPOINTS:
        for attempt in range(4):
            try:
                req = urllib.request.Request(
                    url, data=body, headers={"User-Agent": "jinja-map/0.2"}
                )
                with urllib.request.urlopen(req, timeout=330) as r:
                    return json.load(r)
            except Exception as e:  # noqa: BLE001
                last = e
                print(f"retry {url} ({attempt + 1}): {e}", file=sys.stderr)
                time.sleep(10 * (attempt + 1))
    raise SystemExit(f"Overpass 取得失敗: {last}")


def to_feature(el, pref=""):
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
            "pref": pref,
            "name": tags.get("name", ""),
            "name_en": tags.get("name:en", ""),
            "enshrine": enshrine,
            "wikipedia": tags.get("wikipedia", ""),
            "wikidata": tags.get("wikidata", ""),
            "website": tags.get("website", "") or tags.get("contact:website", ""),
            "tumulus": tags.get("tumulus", ""),
            "heritage": tags.get("heritage", "") or tags.get("designation", ""),
            "start_date": tags.get("start_date", ""),
            "historic": tags.get("historic", ""),
            "castle_type": tags.get("castle_type", ""),
            "ruins": tags.get("ruins", ""),
        },
    }


def main():
    features, seen, stamp, per_pref = [], set(), "", {}
    kofun, kseen, per_pref_kofun = [], set(), {}
    castle, cseen, per_pref_castle = [], set(), {}
    for iso, pname in PREFS:
        data = fetch(iso)
        stamp = data.get("osm3s", {}).get("timestamp_osm_base", "") or stamp
        n = 0
        for e in data.get("elements", []):
            f = to_feature(e, pname)
            if f and f["properties"]["id"] not in seen:
                seen.add(f["properties"]["id"])
                features.append(f)
                n += 1
        per_pref[pname] = n
        print(pname, n, flush=True)
        time.sleep(8)
        kd = fetch(iso, KOFUN_QUERY)
        kn = 0
        for e in kd.get("elements", []):
            f = to_feature(e, pname)
            if f and f["properties"]["id"] not in kseen:
                kseen.add(f["properties"]["id"])
                kofun.append(f)
                kn += 1
        per_pref_kofun[pname] = kn
        print(pname, "古墳", kn, flush=True)
        time.sleep(8)
        cd = fetch(iso, CASTLE_QUERY)
        cn = 0
        for e in cd.get("elements", []):
            f = to_feature(e, pname)
            if f and f["properties"]["id"] not in cseen:
                cseen.add(f["properties"]["id"])
                castle.append(f)
                cn += 1
        per_pref_castle[pname] = cn
        print(pname, "城", cn, flush=True)
        time.sleep(8)
    total = len(features)
    named = sum(1 for f in features if f["properties"]["name"])
    summary = {
        "total": total,
        "with_name": named,
        "with_enshrine": sum(1 for f in features if f["properties"]["enshrine"]),
        "with_wikipedia": sum(1 for f in features if f["properties"]["wikipedia"]),
        "with_wikidata": sum(1 for f in features if f["properties"]["wikidata"]),
        "osm_timestamp": stamp,
        "per_pref": per_pref,
        "kofun_total": len(kofun),
        "per_pref_kofun": per_pref_kofun,
        "castle_total": len(castle),
        "per_pref_castle": per_pref_castle,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "osm.geojson"), "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh, ensure_ascii=False)
    with open(os.path.join(OUT_DIR, "osm_kofun.geojson"), "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": kofun}, fh, ensure_ascii=False)
    with open(os.path.join(OUT_DIR, "osm_castle.geojson"), "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": castle}, fh, ensure_ascii=False)
    with open(os.path.join(OUT_DIR, "osm_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
