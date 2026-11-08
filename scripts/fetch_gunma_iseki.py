"""群馬県オープンデータ「遺跡・文化財」（周知の埋蔵文化財包蔵地）から古墳を取り出す。

出典：遺跡・文化財、群馬県、クリエイティブ・コモンズ・ライセンス 表示 4.0
      https://toukei.pref.gunma.jp/zu240061/ （範囲の中心点を取り、緯度経度に変換して利用）
包蔵地の範囲は目安であり、最新でない場合があるため、画面では「位置は目安」と表示する。

出力: build/gunma_kofun.json  [{"name","kana","lat","lon","id"}]
"""
import json
import os
import re
import struct
import sys
import urllib.parse
import urllib.request

BASE = "https://toukei.pref.gunma.jp/zu240061/"
UA = {"User-Agent": "jinja-map/0.3 (https://github.com/YoheiOnozato/jinja-map)"}
OUT = os.path.join(os.path.dirname(__file__), "..", "build", "gunma_kofun.json")
CRS = "EPSG:6677"  # 平面直角座標系 第IX系（群馬県）
KOFUN_RE = re.compile(r"墳")


def get(path):
    q = urllib.parse.quote(path.encode("utf-8"), safe="/:")
    last = None
    for _ in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(urllib.parse.urljoin(BASE, q), headers=UA), timeout=180) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
    raise SystemExit(f"取得失敗 {path}: {last}")


def read_dbf(b):
    n, hl, rl = struct.unpack("<IHH", b[4:12])
    fields, p = [], 32
    while b[p] != 0x0D:
        fields.append((b[p:p + 11].split(b"\0")[0].decode("cp932", "replace"), b[p + 16]))
        p += 32
    rows = []
    for i in range(n):
        raw, o, row = b[hl + i * rl: hl + (i + 1) * rl], 1, {}
        for nm, ln in fields:
            row[nm] = raw[o:o + ln].decode("cp932", "replace").strip()
            o += ln
        rows.append(row)
    return rows


def centroids(b):
    """シェープファイル（ポリゴン）を順に読み、各レコードの代表点（面積重心。取れなければ外接矩形の中心）を返す。"""
    out, p, n = [], 100, len(b)
    while p + 8 <= n:
        ln = struct.unpack(">i", b[p + 4:p + 8])[0] * 2
        c = b[p + 8:p + 8 + ln]
        p += 8 + ln
        st = struct.unpack("<i", c[:4])[0] if len(c) >= 4 else 0
        if st == 0 or len(c) < 44:
            out.append(None)
            continue
        xmin, ymin, xmax, ymax = struct.unpack("<4d", c[4:36])
        np_, npt = struct.unpack("<2i", c[36:44])
        parts = list(struct.unpack("<%di" % np_, c[44:44 + 4 * np_])) + [npt]
        pts = struct.unpack("<%dd" % (2 * npt), c[44 + 4 * np_:44 + 4 * np_ + 16 * npt])
        A = cx = cy = 0.0
        for k in range(np_):
            ring = [(pts[2 * i], pts[2 * i + 1]) for i in range(parts[k], parts[k + 1])]
            for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
                cr = x0 * y1 - x1 * y0
                A += cr
                cx += (x0 + x1) * cr
                cy += (y0 + y1) * cr
        if abs(A) > 1e-6:
            out.append((cx / (3 * A), cy / (3 * A)))
        else:
            out.append(((xmin + xmax) / 2, (ymin + ymax) / 2))
    return out


def main():
    from pyproj import Transformer  # pip install pyproj
    tr = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
    rows = read_dbf(get("data/遺跡.dbf"))
    cents = centroids(get("data/遺跡.shp"))
    print("遺跡の件数:", len(rows), "形の件数:", len(cents))
    items = []
    for r, c in zip(rows, cents):
        name = r.get("遺跡名", "")
        if not c or not name or not KOFUN_RE.search(name):
            continue
        lon, lat = tr.transform(c[0], c[1])
        if not (35.9 < lat < 37.1 and 138.3 < lon < 139.8):
            continue
        items.append({"id": r.get("遺跡ID", ""), "name": name, "kana": r.get("よみがな", ""),
                      "lat": round(lat, 6), "lon": round(lon, 6)})
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False)
    print("古墳の件数:", len(items))
    if "--check" in sys.argv:  # 位置の確認用: 既知の古墳（OpenStreetMap の位置）との差
        known = {"軍配山古墳": (139.12691, 36.29359), "梨ノ木山古墳": (139.13204, 36.28876), "綿貫観音山古墳": (139.07721, 36.30749),
                 "不動山古墳": (139.07864, 36.30379)}
        for it in items:
            for k, (lo, la) in known.items():
                if it["name"] == k:
                    d = (((it["lon"] - lo) * 91000) ** 2 + ((it["lat"] - la) * 111000) ** 2) ** 0.5
                    print("位置の確認", k, it["lon"], it["lat"], "差(m)", round(d))
        tm = [it["name"] for it in items if 139.08 < it["lon"] < 139.17 and 36.27 < it["lat"] < 36.33]
        print("玉村町付近の古墳:", len(tm), tm[:40])


if __name__ == "__main__":
    main()
