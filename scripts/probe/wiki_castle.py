"""Wikipedia の城の記事の情報欄（テンプレート名・項目名）を確認する（確認用）。"""
import json
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, "scripts")
from wikitext import find_infobox  # noqa: E402

for title in ("小田原城", "水戸城", "忍城", "江戸城", "館林城", "亥鼻城"):
    url = "https://ja.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "format": "json", "titles": title, "formatversion": 2})
    req = urllib.request.Request(url, headers={"User-Agent": "jinja-map-probe/0.1 (https://github.com/YoheiOnozato/jinja-map)"})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    wt = d["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
    names = re.findall(r"\{\{\s*([^|{}\n]{1,40})", wt[:6000])
    print("==", title, "先頭のテンプレート名:", names[:8])
    tpl, info = find_infobox(wt)
    print("find_infobox:", tpl, list(info.keys())[:30])
    for k in info:
        if "天守" in k or "遺構" in k:
            print("  ", k, "=", info[k][:120])
