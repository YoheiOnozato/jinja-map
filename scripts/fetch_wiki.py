"""Wikipedia（日本語版）の関東各都県の神社カテゴリから神社の記事を集める。

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
UA = "jinja-map/0.2 (https://github.com/YoheiOnozato/jinja-map)"
PREF_NAMES = ["茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県"]
ROOTS = [("Category:%sの神社" % n, n) for n in PREF_NAMES] + [("Category:群馬県の神道", "群馬県")] + [
    ("Category:%s" % c, "") for c in (
        "常陸国の式内社 下野国の式内社 上野国の式内社 武蔵国の式内社 相模国の式内社 上総国の式内社 下総国の式内社 安房国の式内社 "
        "常陸国一宮 下野国一宮 上野国一宮 武蔵国一宮 相模国一宮 上総国一宮 下総国一宮 安房国一宮").split()]
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
    seen_cats, titles = set(), {}
    queue = [(r, 0, pf) for r, pf in ROOTS]
    while queue:
        cat, depth, pf = queue.pop(0)
        if cat in seen_cats:
            continue
        seen_cats.add(cat)
        cont = {}
        while True:
            data = call(dict(action="query", list="categorymembers", cmtitle=cat,
                             cmlimit="500", cmtype="page|subcat", **cont))
            for m in data["query"]["categorymembers"]:
                if m["ns"] == 0:
                    if not titles.get(m["title"]):
                        titles[m["title"]] = pf
                elif m["ns"] == 14 and depth < MAX_DEPTH:
                    queue.append((m["title"], depth + 1, pf))
            if "continue" in data:
                cont = data["continue"]
            else:
                break
        time.sleep(0.2)
    return titles, sorted(seen_cats)


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


PERSON_CAT = __import__("re").compile(r"^Category:(紀元前)?\d+年(生|没)$|生年不明|没年不明|生年不詳|没年不詳|日本の天皇|日本の皇族")


def resolve_people(all_links):
    """記事名の一覧から「人物」の記事だけを選び、{リンク名: 正式な記事名} を返す。"""
    titles = sorted(all_links)
    canon, is_person = {}, {}
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        cont = {}
        while True:
            data = call(dict(action="query", prop="categories", titles="|".join(batch), redirects="1",
                             cllimit="max", **cont))
            q = data.get("query", {})
            for r in q.get("redirects", []):
                canon[r["from"]] = r["to"]
            for p in q.get("pages", []):
                if p.get("missing"):
                    continue
                for c in p.get("categories", []):
                    if PERSON_CAT.search(c["title"]):
                        is_person[p["title"]] = True
            if "continue" in data:
                cont = data["continue"]
            else:
                break
        time.sleep(0.25)
    out = {}
    for t in titles:
        c = canon.get(t, t)
        if is_person.get(c):
            out[t] = c
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
    tpref, cats = category_pages()
    titles = sorted(tpref)
    print(f"カテゴリ {len(cats)} 件 / 記事 {len(titles)} 件")
    arts = fetch_articles(titles)
    items = [dict(digest(t, a), pref=tpref.get(t, "")) for t, a in arts.items()]
    all_links = {l for x in items for l in x["links"]}
    print(f"リンク先の記事 {len(all_links)} 件から人物を判定します")
    people_map = resolve_people(all_links)
    for x in items:
        x["people"] = sorted({people_map[l] for l in x["links"] if l in people_map})
    print("人物の例:", sorted(set(people_map.values()))[:30])
    with_coord = sum(1 for x in items if x["lat"] is not None)
    with_deity = sum(1 for x in items if x["deity"])
    with_rank = sum(1 for x in items if x["rank"])
    with_history = sum(1 for x in items if x["history"])
    tpl_count = {}
    for x in items:
        tpl_count[x["template"]] = tpl_count.get(x["template"], 0) + 1
    debug = {
        "categories": len(cats), "articles": len(items), "with_coord": with_coord,
        "with_deity": with_deity, "with_rank": with_rank, "with_history": with_history, "with_people": sum(1 for x in items if x.get("people")),
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
