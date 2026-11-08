"""Wikipedia（日本語版）のカテゴリ「群馬県の神社」から神社の記事を集める。

出力: build/wiki.json （記事ごとの座標・情報欄・由緒の抜粋）
GitHub Actions 上で実行する想定。標準ライブラリのみ。
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from wikitext import clean, find_infobox, link_targets, split_sections  # noqa: E402

API = "https://ja.wikipedia.org/w/api.php"
UA = "jinja-map-gunma/0.1 (https://github.com/YoheiOnozato/jinja-map)"
ROOTS = ["Category:群馬県の神社", "Category:上野国の式内社", "Category:上野国一宮", "Category:群馬県の神道"]
MAX_DEPTH = 3
OUT = os.path.join(os.path.dirname(__file__), "..", "build", "wiki.json")
HISTORY_HEADS = ("歴史", "由緒", "由来", "沿革", "歴史・由緒", "歴史と由緒", "縁起", "概要")


def call(params):
    params = dict(params, format="json", formatversion="2")
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            print(f"retry ({attempt + 1}): {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise SystemExit("Wikipedia API 失敗")


def category_pages():
    """カテゴリを再帰的にたどり、記事（標準名前空間）のタイトル集合を返す。"""
    seen_cats, titles = set(), set()
    queue = [(r, 0) for r in ROOTS]
    while queue:
        cat, depth = queue.pop(0)
        if cat in seen_cats:
            continue
        seen_cats.add(cat)
        cont = {}
        while True:
            data = call(dict(action="query", list="categorymembers", cmtitle=cat,
                             cmlimit="500", cmtype="page|subcat", **cont))
            for m in data["query"]["categorymembers"]:
                if m["ns"] == 0:
                    titles.add(m["title"])
                elif m["ns"] == 14 and depth < MAX_DEPTH:
                    queue.append((m["title"], depth + 1))
            if "continue" in data:
                cont = data["continue"]
            else:
                break
        time.sleep(0.2)
    return sorted(titles), sorted(seen_cats)


def fetch_articles(titles):
    out = {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        data = call(dict(action="query", prop="revisions|coordinates|pageprops", titles="|".join(batch),
                         rvprop="content", rvslots="main", colimit="max", ppprop="wikibase_item",
                         redirects="1"))
        for p in data["query"]["pages"]:
            if p.get("missing") or "revisions" not in p:
                continue
            wt = p["revisions"][0]["slots"]["main"]["content"]
            coord = p.get("coordinates", [{}])[0] if p.get("coordinates") else {}
            out[p["title"]] = {
                "wikitext": wt,
                "lat": coord.get("lat"),
                "lon": coord.get("lon"),
                "wikidata": p.get("pageprops", {}).get("wikibase_item", ""),
            }
        time.sleep(0.3)
    return out


def digest(title, a):
    tpl, info = find_infobox(a["wikitext"])
    sections = split_sections(a["wikitext"])
    intro = clean(sections[0][1])
    history = ""
    for head, body in sections[1:]:
        if any(head == h or head.startswith(h) for h in HISTORY_HEADS):
            history += clean(body) + "\n"
            if len(history) > 1500:
                break

    def pick(*keys):
        for k in keys:
            if k in info and clean(info[k]):
                return clean(info[k])
        return ""

    return {
        "title": title,
        "lat": a["lat"], "lon": a["lon"], "wikidata": a["wikidata"],
        "template": tpl,
        "info_keys": sorted(info.keys()),
        "name": pick("社名", "名称", "名前") or title,
        "deity": pick("主祭神", "祭神"),
        "rank": pick("社格", "格式"),
        "founded": pick("創建", "創祀", "創建年", "創建時期"),
        "address": pick("所在地", "住所"),
        "website": pick("公式サイト", "ウェブサイト", "HP", "URL"),
        "intro": intro[:400],
        "history": history.strip()[:1500],
        "links": link_targets(a["wikitext"]),
    }


def main():
    titles, cats = category_pages()
    print(f"カテゴリ {len(cats)} 件 / 記事 {len(titles)} 件")
    print("カテゴリ一覧:", " / ".join(cats))
    arts = fetch_articles(titles)
    items = [digest(t, a) for t, a in arts.items()]
    with_coord = sum(1 for x in items if x["lat"] is not None)
    with_deity = sum(1 for x in items if x["deity"])
    with_rank = sum(1 for x in items if x["rank"])
    with_history = sum(1 for x in items if x["history"])
    tpl_count = {}
    for x in items:
        tpl_count[x["template"]] = tpl_count.get(x["template"], 0) + 1
    debug = {
        "categories": len(cats), "articles": len(items), "with_coord": with_coord,
        "with_deity": with_deity, "with_rank": with_rank, "with_history": with_history,
        "templates": tpl_count,
        "sample_info_keys": next((x["info_keys"] for x in items if x["info_keys"]), []),
        "sample_titles": [x["title"] for x in items[:8]],
    }
    print(json.dumps(debug, ensure_ascii=False, indent=2))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False)


if __name__ == "__main__":
    main()
