from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Optional
from uuid import uuid4

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from app.state import CartItem, ECState, Order, Product

_PRODUCTS_PATH = Path(__file__).parent / "data" / "products.json"
_PRODUCTS: list[Product] = json.loads(_PRODUCTS_PATH.read_text(encoding="utf-8"))
_BY_ID: dict[str, Product] = {p["id"]: p for p in _PRODUCTS}


def _filter_products(
    query: Optional[str],
    max_price: Optional[int],
    category: Optional[str],
) -> list[Product]:
    q = (query or "").strip().lower()
    cat = (category or "").strip().lower() or None
    results: list[Product] = []
    for p in _PRODUCTS:
        if q:
            haystack = f"{p['name']} {p['description']} {p['category']}".lower()
            if q not in haystack:
                continue
        if cat and p["category"].lower() != cat:
            continue
        if max_price is not None and p["price"] > max_price:
            continue
        results.append(p)
    return results


def _coerce_int(value, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def _format_products_summary(products: list[Product]) -> str:
    if not products:
        return "条件に合う商品は見つかりませんでした。"
    lines = [f"{len(products)} 件見つかりました:"]
    for i, p in enumerate(products, start=1):
        lines.append(f"{i}. [{p['id']}] {p['name']} - ¥{p['price']:,} (在庫{p['stock']})")
    return "\n".join(lines)


@tool
def search_products(
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    max_price: Optional[int] = None,
    category: Optional[str] = None,
) -> Command:
    """商品をキーワード/価格上限/カテゴリで検索する。

    Args:
        query: 商品名や説明に対するフリーキーワード(例: "白Tシャツ", "デニム")
        max_price: 価格の上限(JPY整数)。省略可。
        category: カテゴリ名(tops/bottoms/shoes/accessories)。省略可。
    """
    max_price_int = _coerce_int(max_price)
    products = _filter_products(query, max_price_int, category)
    summary = _format_products_summary(products)
    return Command(
        update={
            "last_search": products,
            "messages": [ToolMessage(content=summary, tool_call_id=tool_call_id)],
            "last_tool_payload": {
                "name": "search_products",
                "data": {"products": products, "query": query},
            },
        }
    )


@tool
def get_product_detail(
    product_id: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """商品IDから商品の詳細情報を取得する。

    Args:
        product_id: 商品ID(例: "P001")
    """
    product = _BY_ID.get(product_id)
    if product is None:
        msg = f"商品ID {product_id} は存在しません。"
        return Command(
            update={
                "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
                "last_tool_payload": {
                    "name": "get_product_detail",
                    "data": {"ok": False, "reason": msg},
                },
            }
        )
    msg = f"[{product['id']}] {product['name']} ¥{product['price']:,} 在庫{product['stock']} - {product['description']}"
    return Command(
        update={
            "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
            "last_tool_payload": {
                "name": "get_product_detail",
                "data": {"ok": True, "product": product},
            },
        }
    )


def _cart_total(cart: list[CartItem]) -> int:
    return sum(int(it["subtotal"]) for it in cart)


@tool
def add_to_cart(
    product_id: str,
    quantity: int,
    state: Annotated[Any, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """指定商品をカートに追加する。既にカート内にあれば数量を加算する。

    Args:
        product_id: 商品ID(例: "P001")
        quantity: 追加する数量(1以上の整数)
    """
    qty = _coerce_int(quantity)
    product = _BY_ID.get(product_id)
    if product is None:
        msg = f"商品ID {product_id} は存在しません。"
        return Command(
            update={
                "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
                "last_tool_payload": {
                    "name": "add_to_cart",
                    "data": {"ok": False, "reason": msg},
                },
            }
        )
    if qty is None or qty <= 0:
        msg = "数量は1以上の整数で指定してください。"
        return Command(
            update={
                "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
                "last_tool_payload": {
                    "name": "add_to_cart",
                    "data": {"ok": False, "reason": msg},
                },
            }
        )

    cart: list[CartItem] = list(state.get("cart") or [])
    existing_qty = next((c["quantity"] for c in cart if c["product_id"] == product_id), 0)
    new_qty = existing_qty + qty
    if new_qty > product["stock"]:
        msg = f"在庫が不足しています({product['name']}の在庫: {product['stock']})。"
        return Command(
            update={
                "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
                "last_tool_payload": {
                    "name": "add_to_cart",
                    "data": {"ok": False, "reason": msg},
                },
            }
        )

    updated: list[CartItem] = []
    found = False
    for item in cart:
        if item["product_id"] == product_id:
            updated.append(
                {
                    **item,
                    "quantity": new_qty,
                    "subtotal": new_qty * item["unit_price"],
                }
            )
            found = True
        else:
            updated.append(item)
    if not found:
        updated.append(
            {
                "product_id": product["id"],
                "name": product["name"],
                "unit_price": product["price"],
                "quantity": qty,
                "subtotal": product["price"] * qty,
            }
        )

    total = _cart_total(updated)
    msg = f"{product['name']} を {qty} 個カートに追加しました。現在の合計: ¥{total:,}"
    return Command(
        update={
            "cart": updated,
            "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
            "last_tool_payload": {
                "name": "add_to_cart",
                "data": {"ok": True, "cart": updated, "total": total},
            },
        }
    )


@tool
def view_cart(
    state: Annotated[Any, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """現在のカートの中身と合計金額を返す。"""
    cart: list[CartItem] = list(state.get("cart") or [])
    total = _cart_total(cart)
    if not cart:
        msg = "カートは空です。"
    else:
        lines = [f"カート({len(cart)}点, 合計¥{total:,}):"]
        for c in cart:
            lines.append(f"- {c['name']} x{c['quantity']} = ¥{c['subtotal']:,}")
        msg = "\n".join(lines)
    return Command(
        update={
            "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
            "last_tool_payload": {
                "name": "view_cart",
                "data": {"cart": cart, "total": total},
            },
        }
    )


@tool
def remove_from_cart(
    product_id: str,
    state: Annotated[Any, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """指定商品をカートから完全に削除する。

    Args:
        product_id: 削除する商品ID
    """
    cart: list[CartItem] = list(state.get("cart") or [])
    new_cart = [c for c in cart if c["product_id"] != product_id]
    if len(new_cart) == len(cart):
        msg = f"カートに {product_id} は入っていません。"
        return Command(
            update={
                "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
                "last_tool_payload": {
                    "name": "remove_from_cart",
                    "data": {"ok": False, "reason": msg, "cart": cart, "total": _cart_total(cart)},
                },
            }
        )
    total = _cart_total(new_cart)
    msg = f"{product_id} をカートから削除しました。合計: ¥{total:,}"
    return Command(
        update={
            "cart": new_cart,
            "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
            "last_tool_payload": {
                "name": "remove_from_cart",
                "data": {"ok": True, "cart": new_cart, "total": total},
            },
        }
    )


@tool
def checkout(
    payment_method: str,
    shipping_address: str,
    state: Annotated[Any, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """カート内容を注文確定する。注文後はカートを空にする。

    Args:
        payment_method: 支払い方法(例: "credit_card", "convenience_store")
        shipping_address: 配送先住所
    """
    cart: list[CartItem] = list(state.get("cart") or [])
    if not cart:
        msg = "カートが空のため決済できません。"
        return Command(
            update={
                "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
                "last_tool_payload": {
                    "name": "checkout",
                    "data": {"ok": False, "reason": msg},
                },
            }
        )
    if not payment_method or not payment_method.strip():
        msg = "支払い方法を指定してください。"
        return Command(
            update={
                "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
                "last_tool_payload": {
                    "name": "checkout",
                    "data": {"ok": False, "reason": msg},
                },
            }
        )
    if not shipping_address or not shipping_address.strip():
        msg = "配送先住所を指定してください。"
        return Command(
            update={
                "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
                "last_tool_payload": {
                    "name": "checkout",
                    "data": {"ok": False, "reason": msg},
                },
            }
        )

    total = _cart_total(cart)
    order: Order = {
        "order_id": "ORD-" + uuid4().hex[:8].upper(),
        "items": cart,
        "total": total,
        "payment_method": payment_method.strip(),
        "shipping_address": shipping_address.strip(),
        "status": "paid",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    orders: list[Order] = list(state.get("orders") or []) + [order]
    msg = f"注文を確定しました。order_id={order['order_id']} 合計¥{total:,}"
    return Command(
        update={
            "cart": [],
            "orders": orders,
            "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
            "last_tool_payload": {
                "name": "checkout",
                "data": {"ok": True, "order": order},
            },
        }
    )


@tool
def get_order_status(
    order_id: str,
    state: Annotated[Any, InjectedState],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """注文IDから注文ステータスを取得する。

    Args:
        order_id: 注文ID(例: "ORD-XXXXXXXX")
    """
    orders: list[Order] = list(state.get("orders") or [])
    order = next((o for o in orders if o["order_id"] == order_id), None)
    if order is None:
        msg = f"注文ID {order_id} は見つかりません。"
        return Command(
            update={
                "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
                "last_tool_payload": {
                    "name": "get_order_status",
                    "data": {"ok": False, "reason": msg},
                },
            }
        )
    msg = f"{order['order_id']} status={order['status']} 合計¥{order['total']:,}"
    return Command(
        update={
            "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)],
            "last_tool_payload": {
                "name": "get_order_status",
                "data": {"ok": True, "order": order},
            },
        }
    )


ALL_TOOLS = [
    search_products,
    get_product_detail,
    add_to_cart,
    view_cart,
    remove_from_cart,
    checkout,
    get_order_status,
]
