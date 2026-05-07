# agent-sample

LangGraph + FastAPI + React (TypeScript) + Ollama (gemma4) による AI チャットエージェントの最小構成サンプル。

## 構成

```
frontend (React + Vite)  ──/api──▶  backend (FastAPI + LangGraph)  ──HTTP──▶  Host Ollama (gemma4)
        :5173                              :8000                                   :11434
```

- **LLM**: ホスト PC で動く Ollama の `gemma4` モデル
- **エージェント**: LangGraph の最小グラフ（単一 LLM ノード + `MemorySaver`）
- **応答**: Server-Sent Events によるストリーミング
- **会話履歴**: プロセス内 `MemorySaver`（再起動で消える）

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

# /api/chat の SSE ストリーム
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"こんにちは","thread_id":"test-1"}'

# 会話履歴（同じ thread_id で文脈が乗る）
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"私の名前はTaroです","thread_id":"mem-1"}'
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"私の名前は何ですか?","thread_id":"mem-1"}'
```

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
│       ├── main.py          # FastAPI: /health, /api/chat (SSE)
│       ├── agent.py         # LangGraph グラフ（gemma4）
│       └── schemas.py
└── frontend/                # React + TypeScript + Vite
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts       # /api を backend にプロキシ
    └── src/
        ├── App.tsx
        ├── main.tsx
        ├── components/ChatUI.tsx
        └── api/chat.ts      # SSE ストリーム読み取り
```

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

## モデルの差し替え

`.env` で変更:

```env
MODEL_NAME=gemma3
```

別モデルに差し替える場合はホストで `ollama pull <name>` を先に実行する。
