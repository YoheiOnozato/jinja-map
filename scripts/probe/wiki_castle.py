"""城の記事の天守関連の項目の値を確認する（確認用）。"""
import json
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, "scripts")
from wikitext import find_infobox, clean  # noqa: E402

for title in ("水戸城", "宇都宮城", "逆井城", "忍城", "亥鼻城", "小田原城", "関宿城", "久留里城", "館林城"):
    url = "https://ja.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "format": "json", "titles": title, "formatversion": 2})
    req = urllib.request.Request(url, headers={"User-Agent": "jinja-map-probe/0.1 (https://github.com/YoheiOnozato/jinja-map)"})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    wt = d["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
    tpl, info = find_infobox(wt)
    print("==", title)
    for k in ("tower_struct", "rebuilding things", "remains", "struct"):
        print("  ", k, "=", repr(clean(info.get(k, ""))[:150]))
