import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from app.agent import MODEL_NAME, OLLAMA_BASE_URL, graph
from app.schemas import ChatRequest

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


@app.post("/api/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    config = {"configurable": {"thread_id": req.thread_id}}
    inputs = {"messages": [HumanMessage(content=req.message)]}

    async def event_stream():
        try:
            async for event in graph.astream_events(inputs, config=config, version="v2"):
                if event["event"] != "on_chat_model_stream":
                    continue
                chunk = event["data"]["chunk"]
                text = getattr(chunk, "content", "")
                if not text:
                    continue
                yield f"data: {json.dumps({'content': text}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
