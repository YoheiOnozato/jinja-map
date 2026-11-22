# 神社マップ MCP サーバー

AI アプリ（Claude など）から「この近くの神社は？」「貫前神社の由来は？」「徳川家康ゆかりの神社は？」と聞けるようにする、読み取り専用のサーバーです。
地図サイトが公開しているデータ（JSON）を読むだけで、データの書き込みや秘密情報はありません。

## ツール
- `search_shrines` 名前で探す（都県で絞り込み可。上位は祭神・由来・行事つき）
- `nearby_shrines` 緯度・経度の近くを近い順に
- `shrines_by_person` 祭神・ゆかりの人物から探す

## 公開手順（Cloudflare Workers・無料枠）
1. Cloudflare のアカウントを作る（無料）
2. このフォルダで `npx wrangler login` → `npx wrangler deploy`
3. 表示された URL（`https://jinja-map-mcp.<アカウント>.workers.dev`）を、AI アプリの「カスタムコネクタ（MCP）」に登録する

## 動作確認
`curl -X POST <URL> -H 'content-type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'`

## 注意
- 回答には出典（OpenStreetMap ODbL・Wikipedia CC BY-SA）を添える（結果の「出典」欄に入っています）。
- データは地図サイトの更新（毎週）に合わせて自動で新しくなります（1時間キャッシュ）。
