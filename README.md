# agent-sample

LangGraph + FastAPI + React (TypeScript) + Ollama (gemma4) による
**仮想ECサイトAIエージェント** の最小構成サンプル。

商品検索 → 詳細確認 → カート追加 → 決済 → 注文確認 までを、複数ノード
LangGraph + ツール呼び出しで実現する。

## 構成

```
frontend (React + Vite)  ──/api──▶  backend (FastAPI + LangGraph)  ──HTTP──▶  Host Ollama (gemma4)
        :5173                              :8000                                   :11434
```

### LangGraph (3 ノード構成)

```
START → agent ──tool_calls? yes──► tools ──► agent
              └── no ──► final_responder ──► END
```

- `agent` … LLM がユーザー要求を解釈してツール呼び出しを判断
- `tools` … `ToolNode` が 7 ツールを実行し `Command(update=...)` で状態更新
- `final_responder` … 直前のツール結果を踏まえた最終応答を生成

### State (LangGraph)

`messages` / `cart` / `orders` / `last_search` / `last_tool_payload` を保持。
`MemorySaver` により thread_id 単位でカートや注文履歴が文脈として残る。

### ツール (7 種)

| Tool | 役割 |
|---|---|
| `search_products(query, max_price?, category?)` | 商品検索 |
| `get_product_detail(product_id)` | 商品詳細 |
| `add_to_cart(product_id, quantity)` | カート追加 |
| `view_cart()` | カート表示 |
| `remove_from_cart(product_id)` | カート削除 |
| `checkout(payment_method, shipping_address)` | 注文確定 |
| `get_order_status(order_id)` | 注文状況確認 |

商品マスタは `backend/app/data/products.json`（12 件、カテゴリ:
tops/bottoms/shoes/accessories）。カート・注文は LangGraph State に
メモリ保持（再起動で消える）。

### SSE プロトコル

`POST /api/chat` は type 判別式の SSE を返す:

```json
{"type":"content","content":"…"}                       // LLM トークン (final_responder)
{"type":"tool","name":"search_products","result":{…}}  // ツール完了時の構造化結果
{"type":"done"}                                        // 完了
{"type":"error","error":"…"}                           // エラー
```

フロントは `result.data` に応じて `ProductCard` / `CartView` /
`OrderSummary` を吹き出し内に描画する。

## 前提

- Docker Desktop
- ホスト PC で Ollama が起動済み (`ollama serve`)
- gemma4 モデル取得済み: `ollama pull gemma4`

## 起動

```bash
cp .env.example .env   # 必要に応じて編集
docker compose up --build
```

- フロント: http://localhost:5173
- バックエンド: http://localhost:8000

## 動作確認

```bash
# ヘルスチェック
curl http://localhost:8000/health

# 商品検索 (search_products ツールが発火)
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"白いTシャツを探して","thread_id":"shop-1"}'

# 同じ thread_id で「2番をカートに入れて」
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"2番をカートに入れて","thread_id":"shop-1"}'
```

UI シナリオ例:

1. 「白い T シャツを探して」 → 商品グリッドが描画される
2. 「2 番をカートに入れて」 → カート表が描画される
3. 「カートを見せて」 → 現在のカート
4. 「購入手続きをして、支払いはクレジットカードで配送先は東京都千代田区…」 → 注文サマリ

## ディレクトリ構成

```
.
├── docker-compose.yml
├── .env.example
├── backend/                 # FastAPI + LangGraph (uv 管理)
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── Dockerfile
│   └── app/
│       ├── main.py          # FastAPI: /health, /api/chat (SSE 拡張版)
│       ├── agent.py         # 3 ノード LangGraph (agent / tools / final_responder)
│       ├── tools.py         # 7 ツール (Command + InjectedState)
│       ├── state.py         # ECState (MessagesState 拡張)
│       ├── schemas.py
│       └── data/products.json
└── frontend/                # React + TypeScript + Vite
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx
        ├── main.tsx
        ├── styles.css
        ├── types.ts
        ├── api/chat.ts      # 判別ユニオン SSE パーサー
        └── components/
            ├── ChatUI.tsx
            ├── ToolEventView.tsx
            ├── ProductCard.tsx
            ├── CartView.tsx
            └── OrderSummary.tsx
```

## モデルの差し替え

`.env` で変更:

```env
MODEL_NAME=qwen2.5:7b-instruct
```

差し替える場合はホストで `ollama pull <name>` を先に実行する。

### gemma4 で tool calling が不安定な場合

gemma 系は Ollama の native tool calling 対応が弱く、`bind_tools` での
ツール呼び出しが空に終わる、本文に JSON が混入する、などが起きうる。
本実装には自動フォールバックを組み込んでいる:

- 起動時に `bind_tools` の成否を判定。失敗時は自動でプロンプト + JSON
  出力モードに切り替わる。
- native でも `tool_calls` 空のときは本文中の JSON を救済パースする。

うまく動かない場合は次の順で対応する:

1. `.env` に `USE_TOOL_FALLBACK=always` を設定して再起動
2. それでも不安定なら `MODEL_NAME=qwen2.5:7b-instruct` または
   `MODEL_NAME=llama3.1:8b` へ差し替え（どちらも `ollama pull` 必須）

## 採用バージョン

| 種別 | 名前 | バージョン |
|---|---|---|
| ランタイム | Python | 3.14 |
| ランタイム | Node.js | 24 LTS |
| バックエンド | fastapi / uvicorn | 0.136.1 / 0.46.0 |
| バックエンド | langgraph | 1.1.10 |
| バックエンド | langchain-core / langchain-ollama | 1.3.3 / 1.1.0 |
| フロント | react | 19.2.6 |
| フロント | typescript / vite | 6.0.3 / 8.0.11 |
