# 関東の神社マップ（試作）

関東1都6県の神社を地図に表示するサイト。成功したら全国へ拡大する。
公開ページ: https://yoheionozato.github.io/jinja-map/

## データの出どころ

| 項目 | 出どころ |
| --- | --- |
| 名称・位置 | OpenStreetMap（ODbL） |
| 社格・祭神・創建・由来 | Wikipedia 日本語版の各神社の記事（CC BY-SA） |
| 系統（八幡・稲荷など）・創建の時代・地図上の大きさ | 上記の文章から**機械的に推定**したもの |
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

- `scripts/fetch_osm.py` … OpenStreetMap から神社を取得（都県ごと）
- `scripts/fetch_wiki.py` … Wikipedia のカテゴリから記事を取得
- `scripts/build_site_data.py` … 統合・社格/系統/時代の推定・`data/overrides.json` の適用 → `site/data/`
- `.github/workflows/pages.yml` … 上記を実行して GitHub Pages に公開（push 時と毎週）
- `data/overrides.json` … 確認済みの修正（キーは神社 ID）。書き方はファイル内の説明を参照
