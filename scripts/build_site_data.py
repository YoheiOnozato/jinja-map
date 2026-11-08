"""OSM と Wikipedia のデータを統合して、地図ページ用の shrines.geojson を作る。

入力: build/osm.geojson, build/wiki.json
出力: site/data/core_s.json (神社), core_k.json (古墳), detail_s/ detail_k/ (詳細), summary.json
"""
import datetime
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from era import ERA_NAMES, era_of_year, estimate  # noqa: E402

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


DATA_VERSION = 2
PREFS = ["茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県"]
CELL = 0.25  # 詳細ファイルの区画（度）

# 古墳の墳形
KOFUN_SHAPES = [
    ("前方後方墳", ["前方後方"]),
    ("前方後円墳", ["前方後円", "keyhole"]),
    ("帆立貝形古墳", ["帆立貝"]),
    ("上円下方墳", ["上円下方"]),
    ("八角墳", ["八角"]),
    ("円墳", ["円墳", "round", "circular"]),
    ("方墳", ["方墳", "square"]),
    ("横穴墓", ["横穴墓", "横穴群"]),
    ("古墳群", ["古墳群", "塚群"]),
]
KOFUN_RANKS = [
    (5, "国指定史跡", ["特別史跡", "国の史跡", "国指定史跡", "国史跡"]),
    (4, "県指定史跡", ["県指定", "県史跡", "県の史跡"]),
    (3, "市町村指定史跡", ["市指定", "町指定", "村指定", "市史跡", "町史跡", "村史跡", "市の史跡", "町の史跡", "村の史跡"]),
]


def kofun_shape(text):
    for label, kws in KOFUN_SHAPES:
        if any(k in text for k in kws):
            return label
    return "形不明"


def kofun_period(text):
    """築造時期の記述を拾う（見つからなければ空）。"""
    m = re.search(r"(\d{1,2})世紀(初頭|前半|中頃|中葉|後半|末)?", text)
    if m:
        return m.group(1) + "世紀" + (m.group(2) or "")
    m = re.search(r"(古墳時代)?(前期|中期|後期|終末期)", text)
    if m:
        return "古墳時代" + m.group(2)
    return ""


def kofun_size(text):
    m = re.search(r"(墳丘長|全長|直径|一辺)\s*(約)?\s*(\d+(?:\.\d+)?)\s*(メートル|ｍ|m)", text)
    return "%s約%sm" % (m.group(1), m.group(3)) if m else ""


def build_kofun(osm_k, wiki_k):
    by_title = {w["title"]: w for w in wiki_k}
    for w in wiki_k:
        w["_n"] = norm_name(w["name"])
        w["_t"] = norm_name(w["title"])
    used = set()
    out = []

    def make(name, lon, lat, w, op):
        w = w or {}
        op = op or {}
        intro, history = w.get("intro", ""), w.get("history", "")
        text = " ".join([name, w.get("shape", ""), intro, op.get("tumulus", ""), history[:300]])
        shape = kofun_shape(w.get("shape", "") + " " + name + " " + op.get("tumulus", ""))
        if shape == "形不明":
            shape = kofun_shape(text)
        # 指定: 情報欄の「指定」欄 → Wikipedia 本文 → OSM の heritage タグの順
        des_text = (w.get("designation", "") or "") + " " + intro + " " + op.get("heritage", "")
        score, label = 1, ""
        for sc, lb, kws in KOFUN_RANKS:
            if any(k in des_text for k in kws):
                score, label = sc, lb
                break
        if score == 1 and w:
            score = 2
        rank_src = "wikipedia" if (w.get("designation") and label) else ("auto" if label else "")
        built = w.get("built", "") or kofun_period(intro + " " + history)
        size = w.get("size", "") or kofun_size(intro + " " + history)
        persons = persons_in(" ".join([name, w.get("buried", ""), intro]))
        return {
            "geometry": {"coordinates": [lon, lat]},
            "properties": {
                "name": name, "deity": w.get("buried", ""), "rank": score, "rank_label": label, "rank_src": rank_src,
                "osm_id": op.get("id", ""), "pref": op.get("pref", "") or w.get("pref", ""),
                "kind": shape, "founded": built, "founded_year": None, "era": "古墳",
                "era_note": "" if w.get("built") else "推定",
                "address": w.get("address", ""), "website": op.get("website", ""),
                "intro": intro[:300], "history": history[:900], "size": size,
                "persons": persons, "people": [], "wikipedia": w.get("title", ""),
                "wikidata": w.get("wikidata", "") or op.get("wikidata", ""),
            },
        }

    for f in osm_k:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        w = None
        wp = p.get("wikipedia", "")
        if wp.startswith("ja:") and wp[3:] in by_title:
            w = by_title[wp[3:]]
        if w is None and p.get("name"):
            pn = norm_name(p["name"])
            for cand in wiki_k:
                if cand["title"] in used or cand["lat"] is None:
                    continue
                if (cand["_n"] == pn or cand["_t"] == pn) and haversine(lat, lon, cand["lat"], cand["lon"]) < 800:
                    w = cand
                    break
        if w:
            used.add(w["title"])
        out.append(make(p.get("name") or (w or {}).get("name", "（名称不明の古墳）"), lon, lat, w, p))
    added = 0
    for w in wiki_k:
        if w["title"] in used or w["lat"] is None or w["lon"] is None:
            continue
        out.append(make(w["name"], w["lon"], w["lat"], w, None))
        added += 1
    # 都県が空のものは最寄りの点から補う
    pts = [(f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0], f["properties"]["pref"]) for f in out if f["properties"]["pref"]]
    for f in out:
        pr = f["properties"]
        if pr["pref"]:
            continue
        for n_ in PREFS:
            if n_ in (pr.get("address") or ""):
                pr["pref"] = n_
                break
        if not pr["pref"] and pts:
            lo, la = f["geometry"]["coordinates"]
            pr["pref"] = min(pts, key=lambda t: (t[0] - la) ** 2 + (t[1] - lo) ** 2)[2]
    stat = {"total": len(out), "osm": len(osm_k), "wiki_articles": len(wiki_k), "wiki_added": added,
            "kind_dist": {}, "rank_dist": {}}
    for f in out:
        k = f["properties"]["kind"]
        stat["kind_dist"][k] = stat["kind_dist"].get(k, 0) + 1
        r = str(f["properties"]["rank"])
        stat["rank_dist"][r] = stat["rank_dist"].get(r, 0) + 1
    return out, stat


# ---- 城 ----
# 現存12天守（日本全国）。関東には現存天守はない。
GENZON_TENSHU = {"弘前城", "松本城", "丸岡城", "犬山城", "彦根城", "姫路城", "松江城", "備中松山城", "丸亀城", "松山城 (伊予国)", "宇和島城", "高知城"}
CASTLE_KINDS = ["現存天守", "復元・再建天守", "城跡（櫓・門などが残る）", "城跡（石垣・土塁・堀など）", "区分不明"]
CASTLE_RANKS = [
    (5, "国指定史跡", ["特別史跡", "国の史跡", "国指定史跡", "国史跡", "国宝", "重要文化財"]),
    (5, "日本100名城", ["日本100名城", "続日本100名城", "日本の100名城", "続100名城", "日本百名城"]),
    (4, "県指定史跡", ["県指定", "県史跡", "県の史跡", "都指定", "都史跡"]),
    (3, "市町村指定史跡", ["市指定", "町指定", "村指定", "市史跡", "町史跡", "村史跡", "市の史跡", "町の史跡", "村の史跡"]),
]
RE_KEEP_REBUILT = re.compile(r"(天守|天守閣|大天守)[^。]{0,25}(復元|復興|再建|模擬|再現)|(復元|復興|再建|模擬|再現)[^。]{0,12}(天守|天守閣)")
RE_KEEP_NONE = re.compile(r"天守[^。]{0,12}(なかった|存在しな|築かれ|造られ|上げられ)")
RE_BUILDINGS = re.compile(r"(櫓|門|御殿|書院|多門)[^。]{0,20}(現存|復元|再建|復興)|(現存|復元|再建|復興)[^。]{0,12}(櫓|門|御殿)|重要文化財")
RE_RUINS_NAME = re.compile(r"城跡|城址|城趾|館跡|陣屋跡|砦跡|館址")


def castle_kind(name, w, op):
    title = w.get("title", "")
    ten = w.get("tenshu", "")
    body = " ".join([ten, w.get("remains", ""), w.get("intro", ""), w.get("history", "")[:700]])
    if title in GENZON_TENSHU or re.search(r"現存", ten):
        return "現存天守"
    if re.search(r"復元|復興|再建|模擬|再現", ten) or (RE_KEEP_REBUILT.search(body) and not RE_KEEP_NONE.search(body)):
        return "復元・再建天守"
    if w and RE_BUILDINGS.search(body):
        return "城跡（櫓・門などが残る）"
    if w or op.get("ruins") == "castle" or op.get("historic") == "ruins" or RE_RUINS_NAME.search(name):
        return "城跡（石垣・土塁・堀など）"
    return "区分不明"


def build_castle(osm_c, wiki_c):
    by_title = {w["title"]: w for w in wiki_c}
    for w in wiki_c:
        w["_n"] = norm_name(w["name"])
        w["_t"] = norm_name(w["title"])
    used, out, seen_pts = set(), [], []

    def make(name, lon, lat, w, op):
        w = w or {}
        op = op or {}
        intro, history = w.get("intro", ""), w.get("history", "")
        kind = castle_kind(name, w, op)
        des_text = " ".join([w.get("designation", ""), intro, op.get("heritage", "")])
        score, label = 1, ""
        for sc, lb, kws in CASTLE_RANKS:
            if any(k in des_text for k in kws):
                score, label = sc, lb
                break
        if kind == "現存天守" and score < 5:
            score, label = 5, "現存天守"
        if score == 1 and w:
            score = 2
        rank_src = "wikipedia" if (w.get("designation") and label) else ("auto" if label else "")
        built = w.get("built", "")
        if built and w.get("abolished"):
            built += "（廃城：" + w["abolished"] + "）"
        elif w.get("abolished"):
            built = "廃城：" + w["abolished"]
        year, era = None, ""
        m = re.search(r"(?<![0-9])(\d{3,4})年", w.get("built", "") or op.get("start_date", ""))
        if m and 600 <= int(m.group(1)) <= 1900:
            year = int(m.group(1))
            era = era_of_year(year)
        persons = persons_in(" ".join([name, w.get("lord", ""), intro]))
        return {
            "geometry": {"coordinates": [lon, lat]},
            "properties": {
                "name": name, "deity": w.get("lord", ""), "rank": score, "rank_label": label, "rank_src": rank_src,
                "osm_id": op.get("id", ""), "pref": op.get("pref", "") or w.get("pref", ""),
                "kind": kind, "founded": built, "founded_year": year, "era": era,
                "era_note": "" if w.get("built") else "推定",
                "address": w.get("address", ""), "website": op.get("website", ""),
                "intro": intro[:300], "history": history[:900], "size": w.get("remains", ""),
                "persons": persons, "people": [], "wikipedia": w.get("title", ""),
                "wikidata": w.get("wikidata", "") or op.get("wikidata", ""),
            },
        }

    for f in osm_c:
        p = f["properties"]
        lon, lat = f["geometry"]["coordinates"]
        name = p.get("name", "")
        w = None
        wp = p.get("wikipedia", "")
        if wp.startswith("ja:") and wp[3:] in by_title:
            w = by_title[wp[3:]]
        if w is None and name:
            pn = norm_name(name)
            for cand in wiki_c:
                if cand["lat"] is None:
                    continue
                if (cand["_n"] == pn or cand["_t"] == pn) and haversine(lat, lon, cand["lat"], cand["lon"]) < 2000:
                    w = cand
                    break
        if w:
            if w["title"] in used:
                continue  # 同じ城の別の点（本丸・二の丸など）は1つにまとめる
            used.add(w["title"])
        elif name and any(n == name and haversine(lat, lon, la, lo) < 1000 for n, la, lo in seen_pts):
            continue
        seen_pts.append((name, lat, lon))
        out.append(make(name or (w or {}).get("name", "（名称不明の城）"), lon, lat, w, p))
    added = 0
    for w in wiki_c:
        if w["title"] in used or w["lat"] is None or w["lon"] is None:
            continue
        out.append(make(w["name"], w["lon"], w["lat"], w, None))
        added += 1
    pts = [(f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0], f["properties"]["pref"]) for f in out if f["properties"]["pref"]]
    for f in out:
        pr = f["properties"]
        if pr["pref"]:
            continue
        for n_ in PREFS:
            if n_ in (pr.get("address") or ""):
                pr["pref"] = n_
                break
        if not pr["pref"] and pts:
            lo, la = f["geometry"]["coordinates"]
            pr["pref"] = min(pts, key=lambda t: (t[0] - la) ** 2 + (t[1] - lo) ** 2)[2]
    stat = {"total": len(out), "osm": len(osm_c), "wiki_articles": len(wiki_c), "wiki_added": added,
            "kind_dist": {}, "rank_dist": {}}
    for f in out:
        k = f["properties"]["kind"]
        stat["kind_dist"][k] = stat["kind_dist"].get(k, 0) + 1
        r = str(f["properties"]["rank"])
        stat["rank_dist"][r] = stat["rank_dist"].get(r, 0) + 1
    return out, stat


def link_nearby(shrines, kofun, castles=()):
    """神社・古墳・城のうち近いもの（古墳は150m、城は300m 以内）を props["nearby"] = [名前, 距離m, 種類] に記録する。
    種類は 's'=神社 'k'=古墳 'c'=城。神社は古墳を優先し、なければ城を記録する。"""

    def mkgrid(feats):
        g = {}
        for f in feats:
            lo, la = f["geometry"]["coordinates"]
            g.setdefault((int(la / 0.003), int(lo / 0.003)), []).append(f)
        return g

    def nearest(lo, la, grid, limit):
        best = None
        gy, gx = int(la / 0.003), int(lo / 0.003)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for g in grid.get((gy + dy, gx + dx), ()):
                    glo, gla = g["geometry"]["coordinates"]
                    d = haversine(la, lo, gla, glo)
                    if d <= limit and (best is None or d < best[0]):
                        best = (d, g)
        return best

    kgrid, cgrid, sgrid = mkgrid(kofun), mkgrid(castles), mkgrid(shrines)
    for f in shrines:
        lo, la = f["geometry"]["coordinates"]
        b = nearest(lo, la, kgrid, 150)
        t = "k"
        if not b:
            b, t = nearest(lo, la, cgrid, 300), "c"
        if b:
            f["properties"]["nearby"] = [b[1]["properties"]["name"], int(b[0]), t]
    for feats in (kofun, castles):
        for f in feats:
            lo, la = f["geometry"]["coordinates"]
            b = nearest(lo, la, sgrid, 300 if f in castles else 150)
            if b:
                f["properties"]["nearby"] = [b[1]["properties"]["name"], int(b[0]), "s"]


# 詳細ファイルの短い項目名
DETAIL_KEYS = [
    ("osm_id", "o"), ("rank_label", "rl"), ("rank_src", "rs"), ("deity", "d"), ("founded", "f"), ("founded_year", "fy"),
    ("era_note", "en"), ("address", "a"), ("website", "w"), ("intro", "in"), ("history", "h"),
    ("wikipedia", "wp"), ("wikidata", "wd"), ("verified", "vf"), ("size", "sz"), ("nearby", "nb"),
]


def write_layer(core_name, detail_sub, feats):
    """列ごとの配列にした軽い本体(core)と、0.25° 区画ごとの詳細ファイルを書く。戻り値は詳細ファイル数。"""
    kinds = [k for k, _ in sorted(((k, sum(1 for f in feats if f["properties"]["kind"] == k)) for k in {f["properties"]["kind"] for f in feats}), key=lambda t: -t[1])]
    kidx = {k: i for i, k in enumerate(kinds)}
    eidx = {e: i + 1 for i, e in enumerate(ERA_NAMES)}
    pidx = {p: i + 1 for i, p in enumerate(PREFS)}
    core = {"v": DATA_VERSION, "kinds": kinds, "eras": ERA_NAMES, "prefs": PREFS, "cell": CELL,
            "n": [], "x": [], "y": [], "r": [], "k": [], "e": [], "p": [], "pp": {}}
    cells = {}
    for i, f in enumerate(feats):
        pr = f["properties"]
        lo, la = f["geometry"]["coordinates"]
        xi, yi = int(round(lo * 1e5)), int(round(la * 1e5))
        core["n"].append(pr["name"])
        core["x"].append(xi)
        core["y"].append(yi)
        core["r"].append(pr["rank"])
        core["k"].append(kidx[pr["kind"]])
        core["e"].append(eidx.get(pr.get("era") or "", 0))
        core["p"].append(pidx.get(pr.get("pref") or "", 0))
        if pr.get("persons") or pr.get("people"):
            core["pp"][str(i)] = [pr.get("persons") or [], pr.get("people") or []]
        rec = {}
        for long_k, short_k in DETAIL_KEYS:
            v = pr.get(long_k)
            if v not in (None, "", [], 0):
                rec[short_k] = v
        # 画面側と同じ計算（丸めた座標から区画を決める）
        cell = "%d_%d" % (math.floor(yi / 1e5 / CELL), math.floor(xi / 1e5 / CELL))
        if rec:
            cells.setdefault(cell, {})[str(i)] = rec
    with open(os.path.join(OUT_DIR, core_name), "w", encoding="utf-8") as fh:
        json.dump(core, fh, ensure_ascii=False, separators=(",", ":"))
    dd = os.path.join(OUT_DIR, detail_sub)
    os.makedirs(dd, exist_ok=True)
    for cell, d in cells.items():
        with open(os.path.join(dd, cell + ".json"), "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, separators=(",", ":"))
    return len(cells)


def main():
    with open(os.path.join(BASE, "build", "osm.geojson"), encoding="utf-8") as fh:
        osm = json.load(fh)["features"]
    with open(os.path.join(BASE, "build", "wiki.json"), encoding="utf-8") as fh:
        wiki = json.load(fh)

    def load_opt(name, key=None):
        path = os.path.join(BASE, "build", name)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d[key] if key else d
    osm_k = load_opt("osm_kofun.geojson", "features")
    osm_c = load_opt("osm_castle.geojson", "features")
    wiki_c = load_opt("wiki_castle.json")
    wiki_k = load_opt("wiki_kofun.json")

    by_title = {w["title"]: w for w in wiki}
    for w_ in wiki:
        w_["_n"] = norm_name(w_["name"])
        w_["_t"] = norm_name(w_["title"])
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
        e_year, e_era, e_note = estimate((w or {}).get("founded", ""), intro, history) if w else (None, "", "")
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            "properties": {
                "name": name,
                "deity": deity,
                "rank": score,
                "rank_label": ((w or {}).get("rank", "") or rank_label)[:80],
                "rank_src": "wikipedia" if (w or {}).get("rank") else ("auto" if rank_label else ""),
                "osm_id": (osm_props or {}).get("id", ""),
                "pref": (osm_props or {}).get("pref", "") or (w or {}).get("pref", ""),
                "kind": kind,
                "founded": (w or {}).get("founded", ""),
                "founded_year": e_year,
                "era": e_era,
                "era_note": e_note,
                "address": (w or {}).get("address", ""),
                "website": (w or {}).get("website", "") or (osm_props or {}).get("website", ""),
                "intro": intro[:300],
                "history": history[:900],
                "persons": persons_in(text_for_person),
                "links": ((w or {}).get("links") or [])[:200],
                "people": (w or {}).get("people", []),
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
            pn = norm_name(p["name"])
            for cand in wiki:
                if cand["title"] in used or cand["lat"] is None:
                    continue
                if cand["_n"] == pn or cand["_t"].startswith(pn):
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

    # 都県が分からない記事（式内社カテゴリ由来など）は、所在地の文字→最寄りの OSM 点の順で補う
    pts = [(f["geometry"]["coordinates"][1], f["geometry"]["coordinates"][0], f["properties"]["pref"]) for f in features if f["properties"]["pref"]]
    for f in features:
        pr = f["properties"]
        if pr["pref"]:
            continue
        for n_ in ("茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県"):
            if n_ in (pr.get("address") or ""):
                pr["pref"] = n_
                break
        if not pr["pref"] and pts:
            lo, la = f["geometry"]["coordinates"]
            pr["pref"] = min(pts, key=lambda t: (t[0] - la) ** 2 + (t[1] - lo) ** 2)[2]

    # 確認済みの修正（data/overrides.json）を重ねる。毎週の自動生成でも消えない。
    ov_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "overrides.json")
    overrides = {}
    if os.path.exists(ov_path):
        with open(ov_path, encoding="utf-8") as fh:
            overrides = {k: v for k, v in json.load(fh).items() if not k.startswith("_")}
    OV_FIELDS = ("name", "kind", "rank_label", "founded", "era", "deity", "address")
    ov_applied = 0
    for f in features:
        pr = f["properties"]
        key = pr.get("osm_id") or ("wikipedia:" + pr.get("wikipedia", ""))
        ov = overrides.get(key) or (overrides.get("wikipedia:" + pr["wikipedia"]) if pr.get("wikipedia") else None)
        if not ov:
            continue
        done = [k for k in OV_FIELDS if ov.get(k)]
        for k in done:
            pr[k] = ov[k]
        if "rank_label" in done:
            pr["rank_src"] = "verified"
        if "era" in done:
            pr["era_note"] = ""
        pr["verified"] = done
        ov_applied += 1
    print("overrides applied:", ov_applied, "/", len(overrides))

    summary = {
        "total": len(features),
        "osm_points": len(osm),
        "wiki_articles": len(wiki),
        "wiki_matched_to_osm": len(used),
        "wiki_added": added,
        "wiki_skipped_no_coord": skipped_no_coord,
        "with_deity": sum(1 for f in features if f["properties"]["deity"]),
        "with_era": sum(1 for f in features if f["properties"]["era"]),
        "era_dist": {e: sum(1 for f in features if f["properties"]["era"] == e) for e in ERA_NAMES},
        "with_history": sum(1 for f in features if f["properties"]["history"]),
        "generated": datetime.date.today().isoformat(),
        "overrides_applied": ov_applied,
        "pref_dist": {n_: sum(1 for f in features if f["properties"]["pref"] == n_) for n_ in ("茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県")},
        "with_links": sum(1 for f in features if f["properties"]["links"]),
        "with_people": sum(1 for f in features if f["properties"]["people"]),
        "with_persons": sum(1 for f in features if f["properties"]["persons"]),
        "rank_ge3": sum(1 for f in features if f["properties"]["rank"] >= 3),
        "rank_dist": {},
    }
    for f in features:
        k = str(f["properties"]["rank"])
        summary["rank_dist"][k] = summary["rank_dist"].get(k, 0) + 1
    # ---- 古墳 ----
    kofun_features, kstat = build_kofun(osm_k, wiki_k)
    summary["kofun"] = kstat

    # ---- 近くの神社・古墳（150m 以内で最も近いもの）をお互いに記録 ----
    castle_features, cstat = build_castle(osm_c, wiki_c)
    summary["castle"] = cstat
    link_nearby(features, kofun_features, castle_features)

    # ---- 書き出し：地図用の軽いデータ(列ごとの配列)と、タップ時に読む詳細ファイル ----
    os.makedirs(OUT_DIR, exist_ok=True)
    for sub in ("detail_s", "detail_k", "detail_c"):
        d = os.path.join(OUT_DIR, sub)
        if os.path.isdir(d):
            for fn in os.listdir(d):
                os.remove(os.path.join(d, fn))
    n_s = write_layer("core_s.json", "detail_s", features)
    n_k = write_layer("core_k.json", "detail_k", kofun_features)
    n_c = write_layer("core_c.json", "detail_c", castle_features)
    summary["detail_files"] = n_s + n_k + n_c
    with open(os.path.join(OUT_DIR, "version.txt"), "w") as fh:
        fh.write(str(DATA_VERSION))
    for fn in ("core_s.json", "core_k.json", "core_c.json"):
        print(fn, "bytes:", os.path.getsize(os.path.join(OUT_DIR, fn)))
    with open(os.path.join(OUT_DIR, "persons.json"), "w", encoding="utf-8") as fh:
        json.dump(PERSONS, fh, ensure_ascii=False)
    with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
