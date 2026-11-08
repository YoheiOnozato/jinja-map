"""群馬県オープンデータ「遺跡・文化財」の中身を確認する（確認用。結果はログに出すだけ）。"""
import re
import struct
import sys
import urllib.parse
import urllib.request

BASE = "https://toukei.pref.gunma.jp/zu240061/"
UA = {"User-Agent": "jinja-map-probe/0.1 (https://github.com/YoheiOnozato/jinja-map)"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


raw = get(BASE)
links = sorted(set(re.findall(rb'href="([^"]+\.(?:shp|dbf|shx|prj|xlsx|zip|csv))"', raw)))
print("links(raw):", links)


def dec(bs):
    for enc in ("utf-8", "cp932"):
        try:
            return bs.decode(enc)
        except UnicodeDecodeError:
            pass
    return bs.decode("latin-1")


files = {}
for l in links:
    q = urllib.parse.quote(urllib.parse.unquote_to_bytes(l), safe="/:")
    u = urllib.parse.urljoin(BASE, q)
    name = dec(urllib.parse.unquote_to_bytes(l)).rsplit("/", 1)[-1]
    try:
        files[name] = get(u)
        print("got", name, len(files[name]))
    except Exception as e:  # noqa: BLE001
        print("fail", repr(l), u, e)
shp = next((v for k, v in files.items() if k == "遺跡.shp"), None)
dbf = next((v for k, v in files.items() if k == "遺跡.dbf"), None)
if shp:
    st, = struct.unpack("<i", shp[32:36])
    xmin, ymin, xmax, ymax = struct.unpack("<4d", shp[36:68])
    print("shape type", st, "bbox", xmin, ymin, xmax, ymax)
if dbf:
    n, hl, rl = struct.unpack("<IHH", dbf[4:12])
    fields, p = [], 32
    while dbf[p] != 0x0D:
        nm = dbf[p:p + 11].split(b"\0")[0].decode("cp932", "replace")
        ln = dbf[p + 16]
        fields.append((nm, ln))
        p += 32
    print("records", n, "fields", fields)
    recs = []
    for i in range(n):
        raw = dbf[hl + i * rl: hl + (i + 1) * rl]
        o, row = 1, {}
        for nm, ln in fields:
            row[nm] = raw[o:o + ln].decode("cp932", "replace").strip()
            o += ln
        recs.append(row)
    for r in recs[:5]:
        print(r)
    for nm, _ in fields:
        vals = {}
        for r in recs:
            vals[r[nm]] = vals.get(r[nm], 0) + 1
        if len(vals) <= 40:
            print("値の分布", nm, vals)
    kof = [r for r in recs if any("古墳" in v for v in r.values())]
    print("古墳を含む行:", len(kof))
    for r in kof[:8]:
        print(r)
    tm = [r for r in recs if "玉村" in " ".join(r.values())]
    print("玉村町の行:", len(tm))
    for r in [x for x in tm if "古墳" in " ".join(x.values()) or "墳" in " ".join(x.values())][:15]:
        print(r)
