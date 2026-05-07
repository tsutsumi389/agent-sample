import json
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from app.agent import MODEL_NAME, OLLAMA_BASE_URL, graph
from app.schemas import ChatRequest

logger = logging.getLogger("main")

app = FastAPI(title="agent-sample backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "model": MODEL_NAME, "ollama": OLLAMA_BASE_URL}


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _extract_tool_payload(output) -> dict | None:
    """tools ノードの出力(dict)から last_tool_payload を抽出する。"""
    if output is None:
        return None
    if not isinstance(output, dict):
        return None
    payload = output.get("last_tool_payload")
    if isinstance(payload, dict) and "data" in payload:
        return payload
    return None


@app.post("/api/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    config = {
        "configurable": {"thread_id": req.thread_id},
        "recursion_limit": 12,
    }
    inputs = {"messages": [HumanMessage(content=req.message)]}

    async def event_stream():
        try:
            async for event in graph.astream_events(inputs, config=config, version="v2"):
                kind = event["event"]
                metadata = event.get("metadata") or {}
                node = metadata.get("langgraph_node")

                if kind == "on_chat_model_stream":
                    # 最終応答のみをユーザーへストリームする(agent 思考中のテキストは抑制)。
                    if node not in (None, "final_responder"):
                        continue
                    chunk = event["data"]["chunk"]
                    text = getattr(chunk, "content", "")
                    if text:
                        yield _sse({"type": "content", "content": text})
                    continue

                if kind == "on_chain_end" and event.get("name") == "tools":
                    output = event["data"].get("output")
                    payload = _extract_tool_payload(output)
                    if payload is not None:
                        yield _sse(
                            {
                                "type": "tool",
                                "name": payload.get("name", "tool"),
                                "result": payload,
                            }
                        )
                    continue
        except Exception as exc:
            logger.exception("event_stream failed")
            yield _sse({"type": "error", "error": str(exc)})
        finally:
            yield _sse({"type": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
