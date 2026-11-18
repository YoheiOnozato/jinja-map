#!/usr/bin/env python3
"""神社ごとの静的ページ（検索エンジン向け）を作る。
使い方: python3 scripts/gen_pages.py <データのフォルダ> <出力先 site> [県名 ...]
  site/jinja/<id>.html（個別）、site/jinja/index.html（一覧）、site/sitemap.xml、site/robots.txt
内容のある神社（由来・祭神・社格などがあるもの）だけを出す。名前と位置だけのページは作らない。"""
import glob, html, json, os, re, sys

BASE = "https://yoheionozato.github.io/jinja-map/"
RANK_NAME = {6: "一宮・二十二社", 5: "名神大社・官幣大社級", 4: "別表神社級", 3: "式内社・県社級", 2: "郷社・村社級／記事あり"}
E = html.escape


def load(data_dir):
    core = json.load(open(os.path.join(data_dir, "core_s.json"), encoding="utf-8"))
    det = {}
    for f in glob.glob(os.path.join(data_dir, "detail_s", "*.json")):
        det.update(json.load(open(f, encoding="utf-8")))
    return core, det


def nbs(v):
    if not v:
        return []
    return [v] if isinstance(v[0], str) else v


def paras(t):
    return "".join("<p>%s</p>" % E(p.strip()) for p in re.split(r"\n\s*\n", t or "") if p.strip())


def main():
    data_dir, site = sys.argv[1], sys.argv[2]
    want = set(sys.argv[3:]) or {"群馬県"}
    core, det = load(data_dir)
    items = []
    for i, name in enumerate(core["n"]):
        pref = core["prefs"][core["p"][i] - 1] if core["p"][i] else ""
        d = det.get(str(i), {})
        if pref not in want or name.startswith("（") or not (d.get("o") or d.get("wd")):
            continue
        if not (core["r"][i] > 1 or any(k in d for k in ("in", "h", "d", "f", "fy", "wp", "rl"))):
            continue
        items.append((i, name, pref, d))
    slug = lambda d: (d.get("o") or d["wd"]).replace("/", "-")
    by_name = {}
    for i, name, pref, d in items:
        by_name.setdefault(name, []).append(slug(d))
    out = os.path.join(site, "jinja")
    os.makedirs(out, exist_ok=True)
    css = ("body{font-family:sans-serif;max-width:720px;margin:0 auto;padding:12px 16px 40px;line-height:1.8;color:#222}"
           "h1{font-size:1.4em;line-height:1.4}table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}"
           "th{width:7em;white-space:nowrap;color:#555;font-weight:600}a{color:#1a5fb4}.btn{display:inline-block;margin:12px 0;padding:10px 16px;background:#1a5fb4;color:#fff;border-radius:6px;text-decoration:none}"
           ".small{font-size:.85em;color:#666}nav{font-size:.9em;margin-bottom:8px}")
    head = lambda title, desc, canon, extra="": (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>%s</title><meta name=\"description\" content=\"%s\"><link rel=\"canonical\" href=\"%s\"><style>%s</style>%s</head><body>"
        % (E(title), E(desc), canon, css, extra))
    for i, name, pref, d in items:
        s = slug(d)
        lat, lon = core["y"][i] / 1e5, core["x"][i] / 1e5
        kind = core["kinds"][core["k"][i]]
        era = core["eras"][core["e"][i] - 1] if core["e"][i] else ""
        addr = d.get("a") or pref
        m = re.search(r"(?:都|道|府|県)(.+?[市区町村郡])", addr)
        place = pref + (m.group(1) if m else "")
        rank = d.get("rl") or RANK_NAME.get(core["r"][i], "")
        rows = [("所在地", addr), ("社格", rank), ("系統", kind if kind != "その他" else ""), ("主祭神", d.get("d")),
                ("創建", d.get("f")), ("創建の時代", (era + ("（%s）" % d["en"] if d.get("en") else "")) if era else "")]
        tbl = "".join("<tr><th>%s</th><td>%s</td></tr>" % (k, E(v)) for k, v in rows if v)
        intro = d.get("in") or ""
        desc = (intro or "%s（%s）の神社。" % (name, place))[:110]
        near = ""
        lis = []
        for n, dist, t in nbs(d.get("nb")):
            lab = "古墳" if t == "k" else "城" if t == "c" else "神社"
            link = ""
            if t == "s" and len(by_name.get(n, [])) == 1:
                link = '<a href="%s.html">%s</a>' % (by_name[n][0], E(n))
            lis.append("<li>%s（%s・約%dm）</li>" % (link or E(n), lab, dist))
        if lis:
            near = "<h2>近くにあるもの</h2><ul>%s</ul>" % "".join(lis)
        ld = json.dumps({"@context": "https://schema.org", "@type": "Place", "name": name, "address": addr,
                         "geo": {"@type": "GeoCoordinates", "latitude": lat, "longitude": lon}}, ensure_ascii=False)
        src = ["位置・名称：<a href=\"https://www.openstreetmap.org/%s\">OpenStreetMap</a> © OpenStreetMap contributors (ODbL)" % d["o"]] if d.get("o") else []
        if d.get("wp"):
            src.append("由来・祭神ほか：<a href=\"https://ja.wikipedia.org/wiki/%s\">Wikipedia「%s」</a>（CC BY-SA）" % (E(d["wp"]), E(d["wp"])))
        body = ('<nav><a href="../">神社マップ</a> › <a href="index.html">%s の神社</a></nav><h1>%s（%s）</h1>%s<table>%s</table>%s%s'
                '<a class="btn" href="../#17/%.5f/%.5f">地図で見る</a>%s<p class="small">%s。社格・系統・時代は文章から機械的に読み取っており、誤りを含むことがあります。</p></body></html>'
                % (E(pref), E(name), E(place), ("<p>%s</p>" % E(intro)) if intro else "", tbl,
                   ("<h2>由来・歴史</h2>%s" % paras(d["h"])) if d.get("h") else "", "", lat, lon, near, "<br>".join(src)))
        page = head("%s（%s）の祭神・由来・アクセス｜関東の神社・古墳・城マップ" % (name, place), desc, BASE + "jinja/%s.html" % s,
                    '<script type="application/ld+json">%s</script>' % ld.replace("</", "<\\/")) + body
        open(os.path.join(out, s + ".html"), "w", encoding="utf-8").write(page)
    # 一覧
    groups = {}
    for i, name, pref, d in items:
        groups.setdefault(core["r"][i], []).append((name, slug(d), d.get("a") or pref))
    h = ""
    for r in sorted(groups, reverse=True):
        h += "<h2>%s</h2><ul>%s</ul>" % (E(RANK_NAME.get(r, "その他")), "".join(
            '<li><a href="%s.html">%s</a> <span class="small">%s</span></li>' % (s, E(n), E(a)) for n, s, a in sorted(groups[r], key=lambda t: t[2])))
    label = "・".join(sorted(want))
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(
        head("%sの神社一覧（社格・由来のある%d社）｜関東の神社・古墳・城マップ" % (label, len(items)), "%sの神社のうち、由来・祭神などの情報がある%d社を社格順に一覧します。" % (label, len(items)), BASE + "jinja/")
        + '<nav><a href="../">神社マップ（地図）</a></nav><h1>%sの神社一覧</h1><p>由来・祭神などの情報がある神社を社格順に並べています。</p>%s</body></html>' % (E(label), h))
    urls = [BASE, BASE + "jinja/"] + [BASE + "jinja/%s.html" % slug(d) for _, _, _, d in items]
    open(os.path.join(site, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>' % "".join("<url><loc>%s</loc></url>" % u for u in urls))
    open(os.path.join(site, "robots.txt"), "w").write("User-agent: *\nAllow: /\nSitemap: %ssitemap.xml\n" % BASE)
    print("神社ページ %d 件（%s）" % (len(items), label))


main()
