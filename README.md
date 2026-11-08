# 関東の神社マップ（試作）

関東1都6県の神社（丸）と古墳（四角）を地図に表示するサイト。成功したら全国へ拡大する。
公開ページ: https://yoheionozato.github.io/jinja-map/

## データの出どころ

| 項目 | 出どころ |
| --- | --- |
| 名称・位置（神社・古墳） | OpenStreetMap（ODbL） |
| 神社の社格・祭神・創建・由来 | Wikipedia 日本語版の各神社の記事（CC BY-SA） |
| 古墳の指定・築造時期・規模・被葬者・説明 | Wikipedia 日本語版の各古墳の記事（CC BY-SA） |
| 系統（八幡・稲荷など）・墳形・創建の時代・地図上の大きさ | 上記の名称・文章から**機械的に推定**したもの |
| 地図タイル | 国土地理院 |

- 神社の情報の大半は自動で集めたもので、**誤りや抜けを含みます**。
- 画面の「自動推定」「要確認」の表示は、機械的な判定であることを示します。「確認済み」は運営が確認した項目です。
- Wikipedia に記事がない神社は、名称と位置だけの表示です。

## データの誤り報告方法

間違いを見つけたら、次のどちらかで知らせてください。

1. **地図から**: 神社の点をタップし、ポップアップ下の「情報の誤りを報告」を押します。GitHub の入力画面が開き、神社名と ID が自動で入ります（GitHub アカウントが必要です）。
2. **直接**: [Issues](https://github.com/YoheiOnozato/jinja-map/issues/new?template=data-error.yml) から「データの誤りを報告」を選び、間違っている項目・正しい内容・根拠（公式サイトの URL など）を書いてください。

報告は運営が根拠を確認したうえで、`data/overrides.json` に書き足して反映します。反映した項目は「確認済み」と表示され、毎週の自動更新でも消えません。

## 仕組み（開発者向け）

データ作り（遅い）と公開（速い）を分けています。

- `.github/workflows/data.yml`（build-data）… 毎週・手動・`scripts/` や `data/overrides.json` の変更時に動く。データを作って **`data` ブランチ**に保存する。
  - `scripts/fetch_osm.py` … OpenStreetMap から神社・古墳を都県ごとに取得
  - `scripts/fetch_wiki.py` … Wikipedia のカテゴリから神社・古墳の記事を取得
  - `scripts/build_site_data.py` … 統合し、社格・系統・墳形・時代の推定、`data/overrides.json` の適用、近くの神社⇔古墳の紐付けをして書き出す
- `.github/workflows/pages.yml`（build-and-deploy）… `site/` の変更時と、build-data の完了時に動く。`data` ブランチのデータを取り込んで GitHub Pages に公開する。画面だけの修正は数分で反映される。
- データ形式を変えたときは、`scripts/build_site_data.py` の `DATA_VERSION` と `site/index.html` の `const DATA_VERSION` を同時に上げる（合わないと公開を見送り、build-data 完了後に自動で公開される）。

### 地図用データの形

全国でも動くよう、起動時に読むものは小さく、詳しい内容はタップした時に読みます。

- `core_s.json`（神社）・`core_k.json`（古墳）… 名前・位置・社格・系統・時代・都県を**列ごとの配列**にしたもの。古墳は「古墳」のチェックを入れた時に初めて読み込む。
- `detail_s/` `detail_k/` … 緯度経度 0.25° ごとの詳細（OSM の番号・祭神・由来・出典など）。ポップアップを開いた時に該当の区画だけ読む。
- 画面は、見えている範囲だけを supercluster でまとめて描く。

- `data/overrides.json` … 確認済みの修正（キーは神社・古墳の ID）。書き方はファイル内の説明を参照
