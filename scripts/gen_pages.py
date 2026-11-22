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
        if not (core["r"][i] > 1 or any(k in d for k in ("in", "h", "d", "f", "fy", "wp", "rl", "ev"))):
            continue
        items.append((i, name, pref, d))
    slug = lambda d: (d.get("o") or d["wd"]).replace("/", "-")
    by_name = {}
    for i, name, pref, d in items:
        by_name.setdefault(name, []).append(slug(d))
    out = os.path.join(site, "jinja")
    os.makedirs(out, exist_ok=True)
    css = ("*{box-sizing:border-box}body{margin:0;background:#f7f2e8;color:#1f2a44;font-family:'Noto Sans JP',-apple-system,'Hiragino Sans',sans-serif;line-height:1.9}"
           "a{color:inherit}.bar{background:#1f2a44;color:#f7f2e8;padding:14px 24px;display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between}"
           ".bar a{text-decoration:none}.bar .logo{font-family:'Noto Serif JP',serif;font-weight:700;letter-spacing:.08em}.bar .go{font-size:14px;padding:8px 18px;border:1px solid #f7f2e8;border-radius:999px}"
           ".wrap{max-width:1120px;margin:0 auto;padding:40px 24px 72px}.narrow{max-width:760px}"
           ".eyebrow{font-size:13px;letter-spacing:.3em;color:#a9301f;font-weight:700}"
           "h1{font-family:'Noto Serif JP',serif;font-weight:700;font-size:clamp(30px,6vw,52px);line-height:1.3;letter-spacing:.04em;margin:10px 0 16px}"
           "h2{font-family:'Noto Serif JP',serif;font-weight:700;font-size:22px;letter-spacing:.04em;margin:40px 0 12px;padding-bottom:8px;border-bottom:2px solid #a9301f}"
           ".lead{max-width:640px;color:#3b4560;margin:0}.chips{display:flex;flex-wrap:wrap;gap:10px;margin:28px 0 8px}"
           ".chip{padding:8px 16px;border-radius:999px;background:#fff;border:1px solid #d9cfba;font-size:14px;text-decoration:none}.chip b{margin-left:8px;color:#a9301f}"
           ".grp{margin-top:44px}.grp h2{display:flex;align-items:baseline;gap:14px;margin-top:0}.grp h2 span{font-family:'Noto Sans JP',sans-serif;font-size:14px;font-weight:400;color:#5b647b}"
           ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}"
           ".card{display:flex;flex-direction:column;gap:6px;background:#fff;border:1px solid #e4dac4;border-top:4px solid var(--c);border-radius:10px;padding:16px 18px;text-decoration:none;transition:transform .15s,box-shadow .15s}"
           ".card:hover{transform:translateY(-2px);box-shadow:0 8px 20px rgba(31,42,68,.12)}.card b{font-family:'Noto Serif JP',serif;font-size:18px;line-height:1.4}"
           ".card span{font-size:13px;color:#5b647b;line-height:1.6}.card i{font-style:normal;font-size:12px;font-weight:700;color:var(--c);margin-top:4px}"
           "table{border-collapse:collapse;width:100%;background:#fff;border:1px solid #e4dac4;border-radius:10px;overflow:hidden;margin:20px 0}"
           "th,td{border-bottom:1px solid #eee5d2;padding:10px 14px;text-align:left;vertical-align:top}th{width:7.5em;white-space:nowrap;color:#7a5a2a;background:#fbf7ee;font-weight:500}tr:last-child th,tr:last-child td{border-bottom:0}"
           ".btn{display:inline-block;margin:20px 0;padding:12px 24px;background:#a9301f;color:#fff;border-radius:999px;text-decoration:none;font-weight:700}"
           "ul{padding-left:1.3em}nav{font-size:14px;color:#5b647b;margin-bottom:12px}nav a{text-decoration:none;color:#a9301f}"
           ".small{font-size:13px;color:#5b647b}.foot{background:#1f2a44;color:#c9cfdf;padding:28px 24px;font-size:12px;line-height:1.9;text-align:center}.foot a{color:#e8d9a8}")
    fonts = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700'
             '&family=Noto+Serif+JP:wght@700&display=swap" rel="stylesheet">')
    bar = '<div class="bar"><a class="logo" href="../">関東の神社・古墳・城マップ</a><a class="go" href="../">地図で見る</a></div>'
    foot = '<div class="foot">位置・名称：OpenStreetMap © OpenStreetMap contributors（ODbL）／由来・祭神ほか：Wikipedia（CC BY-SA）<br>社格・系統・時代は文章から機械的に読み取っており、誤りを含むことがあります。</div>'
    RCOL = {6: "#a9301f", 5: "#b0701c", 4: "#2f6b5a", 3: "#3a5a9a"}
    head = lambda title, desc, canon, extra="": (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>%s</title><meta name=\"description\" content=\"%s\"><link rel=\"canonical\" href=\"%s\">%s<style>%s</style>%s</head><body>%s"
        % (E(title), E(desc), canon, fonts, css, extra, bar))
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
        evh = ""
        if d.get("ev"):
            evh = "<h2>行事・イベント</h2><ul>%s</ul>" % "".join("<li>%s%s%s</li>" % (E(e["n"]), "：" + E(e["d"]) if e.get("d") else "", ' <a href="%s">出典</a>' % E(e["u"]) if e.get("u") else "") for e in d["ev"])
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
        body = ('<main class="wrap narrow"><nav><a href="../">神社マップ</a> › <a href="index.html">%s の神社</a></nav><div class="eyebrow">SHRINE</div><h1>%s（%s）</h1>%s<table>%s</table>%s%s'
                '<a class="btn" href="../#17/%.5f/%.5f">地図で見る</a>%s<p class="small">%s</p></main>'
                % (E(pref), E(name), E(place), ("<p>%s</p>" % E(intro)) if intro else "", tbl,
                   ("<h2>由来・歴史</h2>%s" % paras(d["h"])) if d.get("h") else "", evh, lat, lon, near, "<br>".join(src))) + foot + "</body></html>"
        page = head("%s（%s）の祭神・由来・アクセス｜関東の神社・古墳・城マップ" % (name, place), desc, BASE + "jinja/%s.html" % s,
                    '<script type="application/ld+json">%s</script>' % ld.replace("</", "<\\/")) + body
        open(os.path.join(out, s + ".html"), "w", encoding="utf-8").write(page)
    # 一覧
    groups = {}
    for i, name, pref, d in items:
        groups.setdefault(core["r"][i], []).append((name, slug(d), d.get("a") or pref))
    chips = "".join('<a class="chip" href="#g%d">%s<b>%d</b></a>' % (r, E(RANK_NAME.get(r, "その他")), len(groups[r])) for r in sorted(groups, reverse=True))
    h = ""
    for r in sorted(groups, reverse=True):
        cards = "".join('<a class="card" style="--c:%s" href="%s.html"><b>%s</b><span>%s</span><i>詳しく見る →</i></a>' % (RCOL.get(r, "#6b6f7e"), s, E(n), E(a))
                        for n, s, a in sorted(groups[r], key=lambda t: t[2]))
        h += '<section class="grp" id="g%d"><h2>%s<span>%d社</span></h2><div class="grid">%s</div></section>' % (r, E(RANK_NAME.get(r, "その他")), len(groups[r]), cards)
    label = "・".join(sorted(want))
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(
        head("%sの神社一覧（社格・由来のある%d社）｜関東の神社・古墳・城マップ" % (label, len(items)), "%sの神社のうち、由来・祭神などの情報がある%d社を社格順に一覧します。" % (label, len(items)), BASE + "jinja/")
        + '<main class="wrap"><div class="eyebrow">SHRINES</div><h1>%sの神社一覧</h1><p class="lead">由来や祭神などの情報がある%d社を、社格の高い順に並べました。気になる神社を選ぶと、由緒・祭神・近くの古墳や城を見られます。</p><div class="chips">%s</div>%s</main>' % (E(label), len(items), chips, h)
        + foot + "</body></html>")
    urls = [BASE, BASE + "jinja/"] + [BASE + "jinja/%s.html" % slug(d) for _, _, _, d in items]
    open(os.path.join(site, "sitemap.xml"), "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>' % "".join("<url><loc>%s</loc></url>" % u for u in urls))
    open(os.path.join(site, "robots.txt"), "w").write("User-agent: *\nAllow: /\nSitemap: %ssitemap.xml\n" % BASE)
    print("神社ページ %d 件（%s）" % (len(items), label))


main()
