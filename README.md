# 群馬の神社マップ（試作）

群馬県の神社を地図に表示する試作。成功したら全国へ拡大する。

- 位置・祭神・Wikipedia 紐付け：OpenStreetMap（ODbL）
- 地図タイル：国土地理院
- 段階：1) 取得と件数確認 → 2) 社格・系統の付与（Wikidata/Wikipedia） → 3) 由来と人名検索

`scripts/fetch_osm.py` は GitHub Actions で実行され、`site/data/` に GeoJSON と集計を出力する。
