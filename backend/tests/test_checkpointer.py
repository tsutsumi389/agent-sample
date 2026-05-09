"""AsyncPostgresSaver が put → get で同じ thread_id の state を復元できることを確認する。

LangGraph 全体を起動するとモデル(Ollama)に依存してしまうため、
本テストは checkpointer 単体の永続化のみを検証する。
"""
from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import Checkpoint, empty_checkpoint


pytestmark = pytest.mark.asyncio


async def test_checkpointer_roundtrip(saver, thread_id):
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}

    cp: Checkpoint = empty_checkpoint()
    cp["channel_values"] = {
        "messages": [HumanMessage(content="hello-from-test")],
        "cart": [{"product_id": "P001", "qty": 2}],
    }
    cp["channel_versions"] = {"messages": "1", "cart": "1"}

    await saver.aput(config, cp, {"source": "test"}, {"messages": "1", "cart": "1"})

    got = await saver.aget_tuple(config)
    assert got is not None
    restored = got.checkpoint["channel_values"]
    assert restored["cart"] == [{"product_id": "P001", "qty": 2}]
    assert restored["messages"][0].content == "hello-from-test"
