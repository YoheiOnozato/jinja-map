"""OSM と Wikipedia のデータを統合して、地図ページ用の shrines.geojson を作る。

入力: build/osm.geojson, build/wiki.json
出力: site/data/shrines.geojson, site/data/summary.json
"""
import json
import math
import os
import re

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT_DIR = os.path.join(BASE, "site", "data")

# 社格の強さ（地図上の大きさ）。上から順に判定して最初に当たったものを採用。
RANKS = [
    (6, "一宮・二十二社", ["二十二社", "一宮", "一ノ宮", "一の宮"]),
    (5, "名神大社・官幣大社・国幣大社", ["名神大社", "名神大", "官幣大社", "国幣大社", "勅祭社", "神宮"]),
    (4, "別表神社・官国幣中社", ["別表神社", "官幣中社", "国幣中社", "式内大社", "大社"]),
    (3, "式内社・二宮〜総社・県社", ["式内", "二宮", "三宮", "総社", "県社", "府社", "官幣小社", "国幣小社", "延喜式"]),
    (2, "郷社・村社・その他社格", ["郷社", "村社", "諸社", "無格社", "旧社格"]),
]

# 系統（祭神や社名のキーワード）。上から順に判定。
KINDS = [
    ("八幡", ["八幡", "応神天皇", "誉田", "ホンダワケ"]),
    ("稲荷", ["稲荷", "倉稲魂", "宇迦之御魂", "ウカノミタマ"]),
    ("天神", ["天満宮", "天神", "菅原道真"]),
    ("神明（伊勢）", ["神明", "天照大", "伊勢神宮", "皇大神宮"]),
    ("諏訪", ["諏訪", "建御名方"]),
    ("浅間", ["浅間", "木花咲耶", "コノハナサクヤ"]),
    ("熊野", ["熊野"]),
    ("氷川", ["氷川"]),
    ("白山", ["白山", "菊理媛"]),
    ("赤城・榛名・上州の山岳", ["赤城", "榛名", "妙義", "武尊", "男体", "二荒"]),
    ("八坂・須賀（天王）", ["八坂", "須賀", "祇園", "天王", "素戔嗚", "須佐之男", "スサノオ"]),
    ("日吉・山王", ["日吉", "山王", "日枝"]),
    ("春日", ["春日"]),
    ("住吉", ["住吉"]),
    ("香取・鹿島", ["香取", "鹿島", "経津主", "武甕槌"]),
    ("雷電", ["雷電", "雷神"]),
    ("愛宕", ["愛宕"]),
    ("出雲系（大国主）", ["出雲", "大国主", "大己貴", "大黒"]),
    ("琴平・金毘羅", ["琴平", "金刀比羅", "金毘羅"]),
    ("諏訪・その他", []),
]

# 人物タグ：正式名 -> 検索に使う別名
PERSONS = {
    "徳川家康": ["徳川家康", "家康", "東照宮"],
    "新田義貞": ["新田義貞"],
    "新田義重": ["新田義重"],
    "源頼朝": ["源頼朝", "頼朝"],
    "源義家": ["源義家", "八幡太郎"],
    "源義経": ["源義経", "義経"],
    "源頼義": ["源頼義"],
    "足利尊氏": ["足利尊氏", "尊氏"],
    "足利義兼": ["足利義兼"],
    "上杉謙信": ["上杉謙信", "長尾景虎", "謙信"],
    "武田信玄": ["武田信玄", "信玄"],
    "織田信長": ["織田信長", "信長"],
    "豊臣秀吉": ["豊臣秀吉", "秀吉"],
    "北条氏康": ["北条氏康"],
    "北条氏政": ["北条氏政"],
    "真田昌幸": ["真田昌幸"],
    "真田信之": ["真田信之"],
    "真田幸村": ["真田信繁", "真田幸村"],
    "由良成繁": ["由良成繁"],
    "長野業政": ["長野業政"],
    "小栗上野介": ["小栗忠順", "小栗上野介", "小栗又一"],
    "井伊直政": ["井伊直政"],
    "榊原康政": ["榊原康政"],
    "本多忠勝": ["本多忠勝"],
    "日本武尊": ["日本武尊", "ヤマトタケル"],
    "菅原道真": ["菅原道真"],
    "坂上田村麻呂": ["坂上田村麻呂"],
    "聖徳太子": ["聖徳太子"],
    "弘法大師（空海）": ["空海", "弘法大師"],
    "平将門": ["平将門"],
    "藤原秀郷": ["藤原秀郷", "俵藤太"],
    "大国主命": ["大国主"],
    "天照大神": ["天照大神", "天照大御神"],
    "素戔嗚尊": ["素戔嗚", "須佐之男"],
    "応神天皇": ["応神天皇"],
    "豊城入彦命": ["豊城入彦"],
    "忠治（国定忠治）": ["国定忠治"],
}


def haversine(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def rank_of(text):
    for score, label, kws in RANKS:
        if any(k in text for k in kws):
            return score, label
    return 1, ""


def kind_of(text):
    for label, kws in KINDS:
        if kws and any(k in text for k in kws):
            return label
    return "その他"


def persons_in(text):
    return [name for name, aliases in PERSONS.items() if any(a in text for a in aliases)]


def norm_name(s):
    return re.sub(r"[\s（）()　]", "", s or "")


def main():
    with open(os.path.join(BASE, "build", "osm.geojson"), encoding="utf-8") as fh:
        osm = json.load(fh)["features"]
    with open(os.path.join(BASE, "build", "wiki.json"), encoding="utf-8") as fh:
        wiki = json.load(fh)

    by_title = {w["title"]: w for w in wiki}
    used = set()
    features = []

    def make(name, lon, lat, w, osm_props):
        deity = (w or {}).get("deity", "")
        rank_text = (w or {}).get("rank", "")
        history = (w or {}).get("history", "")
        intro = (w or {}).get("intro", "")
        score, rank_label = rank_of(rank_text + " " + name + " " + intro[:200]) if w else (1, "")
        if w and score == 1 and w.get("rank"):
            score, rank_label = 2, w["rank"][:20]
        if w and score < 3:
            score = max(score, 2)  # Wikipedia に記事があるだけで一段上げる
        kind = kind_of(name + " " + deity)
        text_for_person = " ".join([name, deity, intro, history])
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            "properties": {
                "name": name,
                "deity": deity,
                "rank": score,
                "rank_label": ((w or {}).get("rank", "") or rank_label)[:80],
                "kind": kind,
                "founded": (w or {}).get("founded", ""),
                "address": (w or {}).get("address", ""),
                "website": (w or {}).get("website", "") or (osm_props or {}).get("website", ""),
                "intro": intro[:300],
                "history": history[:900],
                "persons": persons_in(text_for_person),
                "wikipedia": (w or {}).get("title", ""),
                "wikidata": (w or {}).get("wikidata", "") or (osm_props or {}).get("wikidata", ""),
            },
        }

    # OSM を軸に、Wikipedia 記事と結びつける
    for f in osm:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        w = None
        wp = p.get("wikipedia", "")
        if wp.startswith("ja:") and wp[3:] in by_title:
            w = by_title[wp[3:]]
        if w is None and p.get("name"):
            for cand in wiki:
                if cand["title"] in used or cand["lat"] is None:
                    continue
                if norm_name(cand["name"]) == norm_name(p["name"]) or norm_name(cand["title"]).startswith(norm_name(p["name"])):
                    if haversine(lat, lon, cand["lat"], cand["lon"]) < 600:
                        w = cand
                        break
        if w:
            used.add(w["title"])
        features.append(make(p.get("name") or (w or {}).get("name", "（名称不明）"), lon, lat, w, p))

    # OSM に無かった Wikipedia 記事を追加
    added = 0
    skipped_no_coord = 0
    for w in wiki:
        if w["title"] in used:
            continue
        if w["lat"] is None or w["lon"] is None:
            skipped_no_coord += 1
            continue
        features.append(make(w["name"], w["lon"], w["lat"], w, None))
        added += 1

    summary = {
        "total": len(features),
        "osm_points": len(osm),
        "wiki_articles": len(wiki),
        "wiki_matched_to_osm": len(used),
        "wiki_added": added,
        "wiki_skipped_no_coord": skipped_no_coord,
        "with_deity": sum(1 for f in features if f["properties"]["deity"]),
        "with_history": sum(1 for f in features if f["properties"]["history"]),
        "with_persons": sum(1 for f in features if f["properties"]["persons"]),
        "rank_ge3": sum(1 for f in features if f["properties"]["rank"] >= 3),
        "rank_dist": {},
    }
    for f in features:
        k = str(f["properties"]["rank"])
        summary["rank_dist"][k] = summary["rank_dist"].get(k, 0) + 1
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "shrines.geojson"), "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh, ensure_ascii=False)
    with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
