from __future__ import annotations

import inspect
import json
import logging
import re
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.settings import settings
from app.state import ECState
from app.tools import ALL_TOOLS

_TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}

logger = logging.getLogger("agent")

OLLAMA_BASE_URL = settings.ollama_base_url
MODEL_NAME = settings.model_name
USE_TOOL_FALLBACK = settings.use_tool_fallback.lower()


SYSTEM_AGENT = """あなたは仮想ECサイトのショッピングアシスタントです。
ユーザーの要望に応じて、以下のツールを呼び出して検索→比較→カート→決済までを支援してください。

利用可能ツール:
- search_products(query, max_price?, category?)  商品検索
- get_product_detail(product_id)                  商品詳細
- add_to_cart(product_id, quantity)               カート追加
- view_cart()                                     カート表示
- remove_from_cart(product_id)                    カート削除
- checkout(payment_method, shipping_address)      決済
- get_order_status(order_id)                      注文確認

ルール:
- 商品参照や状態更新はかならずツールを使うこと。憶測で商品を作らない。
- ユーザーが「2番」「白いやつ」などと指示した場合、直前の検索結果を踏まえて
  product_id を推定してツールを呼び出すこと。
- カート操作の前に商品IDと数量を確認すること。
- 決済を行う前に、支払い方法と配送先住所をユーザーに必ず確認すること。
- 同じツールを2回連続で同じ引数で呼ばない。
"""


SYSTEM_FINAL = """あなたはECショッピングアシスタントの応答整形担当です。
直前のツール結果を踏まえ、ユーザーへ簡潔で丁寧な日本語の最終応答を返してください。
追加のツール呼び出しは禁止です。
注文完了の場合は order_id・合計金額・配送先・支払い方法を明示してください。
"""


FALLBACK_SYSTEM = """### ツール呼び出しプロトコル
ツール呼び出しが必要なら、必ず次の JSON のみを出力すること(前後に説明文を付けない):

{"tool": "<tool_name>", "args": { ... }}

ツール呼び出しが不要なら:
{"tool": null, "final": "<最終応答>"}
"""


_base_llm = ChatOllama(model=MODEL_NAME, base_url=OLLAMA_BASE_URL, temperature=0.2)
try:
    llm_with_tools = _base_llm.bind_tools(ALL_TOOLS)
    _BIND_OK = True
except Exception as exc:  # 古い ollama / tool 非対応モデル
    logger.warning("bind_tools failed: %s", exc)
    llm_with_tools = _base_llm
    _BIND_OK = False

llm_plain = _base_llm

logger.warning(
    "[agent] model=%s bind_tools=%s fallback_mode=%s",
    MODEL_NAME,
    _BIND_OK,
    USE_TOOL_FALLBACK,
)


_JSON_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _parse_fallback_json(text: str) -> dict | None:
    if not text:
        return None
    match = _JSON_PATTERN.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _make_tool_call(name: str, args: dict, source_id: int) -> dict:
    return {
        "name": name,
        "args": args or {},
        "id": f"fallback-{source_id}",
        "type": "tool_call",
    }


async def agent_node(state: ECState) -> dict:
    msgs = [SystemMessage(content=SYSTEM_AGENT), *state["messages"]]

    if _BIND_OK and USE_TOOL_FALLBACK != "always":
        ai = await llm_with_tools.ainvoke(msgs)
        if not getattr(ai, "tool_calls", None):
            parsed = _parse_fallback_json(getattr(ai, "content", "") or "")
            if parsed and parsed.get("tool"):
                ai = AIMessage(
                    content="",
                    tool_calls=[_make_tool_call(parsed["tool"], parsed.get("args", {}), id(ai))],
                )
        if getattr(ai, "tool_calls", None):
            ai.tool_calls = ai.tool_calls[:1]
        return {"messages": [ai]}

    fb_msgs = [
        SystemMessage(content=SYSTEM_AGENT + "\n" + FALLBACK_SYSTEM),
        *state["messages"],
    ]
    raw = await llm_plain.ainvoke(fb_msgs)
    parsed = _parse_fallback_json(getattr(raw, "content", "") or "") or {}
    if parsed.get("tool"):
        ai = AIMessage(
            content="",
            tool_calls=[_make_tool_call(parsed["tool"], parsed.get("args", {}), id(raw))],
        )
        return {"messages": [ai]}
    final_text = parsed.get("final") or getattr(raw, "content", "") or ""
    return {"messages": [AIMessage(content=final_text)]}


async def tool_node(state: ECState) -> dict:
    """LangGraph 1.x の InjectedState 周りの差異を回避するための自前ディスパッチャ。

    最後の AIMessage の tool_calls の先頭1件を実行し、`Command(update=...)` の
    update 辞書をそのままノード戻り値として返す(=state を更新する)。
    state を取らないツールには state を渡さない。
    """
    last = state["messages"][-1]
    if not (isinstance(last, AIMessage) and getattr(last, "tool_calls", None)):
        return {}

    tc = last.tool_calls[0]
    name = tc.get("name") or ""
    args = dict(tc.get("args") or {})
    tool_call_id = tc.get("id") or "tool-call"

    tool = _TOOLS_BY_NAME.get(name)
    if tool is None:
        return {
            "messages": [
                ToolMessage(
                    content=f"未知のツール: {name}",
                    tool_call_id=tool_call_id,
                    status="error",
                )
            ]
        }

    sig = inspect.signature(tool.func)
    kwargs = dict(args)
    if "tool_call_id" in sig.parameters:
        kwargs["tool_call_id"] = tool_call_id
    if "state" in sig.parameters:
        kwargs["state"] = state

    try:
        result = tool.func(**kwargs)
    except TypeError as exc:
        return {
            "messages": [
                ToolMessage(
                    content=f"ツール引数エラー({name}): {exc}",
                    tool_call_id=tool_call_id,
                    status="error",
                )
            ]
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("tool execution failed: %s", name)
        return {
            "messages": [
                ToolMessage(
                    content=f"ツール実行エラー({name}): {exc}",
                    tool_call_id=tool_call_id,
                    status="error",
                )
            ]
        }

    if isinstance(result, Command):
        return result.update or {}
    return {
        "messages": [ToolMessage(content=str(result), tool_call_id=tool_call_id)]
    }


async def final_responder_node(state: ECState) -> dict:
    payload = state.get("last_tool_payload") or {}
    hint = json.dumps(payload, ensure_ascii=False) if payload else "(直前のツール出力なし)"
    msgs = [
        SystemMessage(content=SYSTEM_FINAL),
        *state["messages"],
        SystemMessage(content=f"直前のツール結果(参考):\n{hint}"),
    ]
    ai = await llm_plain.ainvoke(msgs)
    return {"messages": [ai], "last_tool_payload": None}


def route_after_agent(state: ECState) -> Literal["tools", "final_responder"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"
    return "final_responder"


def build_graph(checkpointer):
    builder = StateGraph(ECState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("final_responder", final_responder_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "final_responder": "final_responder"},
    )
    builder.add_edge("tools", "agent")
    builder.add_edge("final_responder", END)

    return builder.compile(checkpointer=checkpointer)
