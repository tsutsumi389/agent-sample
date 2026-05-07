from __future__ import annotations

from typing import Annotated, Any, Literal, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class Product(TypedDict):
    id: str
    name: str
    description: str
    price: int
    category: str
    stock: int
    image_url: str


class CartItem(TypedDict):
    product_id: str
    name: str
    unit_price: int
    quantity: int
    subtotal: int


OrderStatus = Literal["pending", "paid", "shipped", "delivered", "cancelled"]


class Order(TypedDict):
    order_id: str
    items: list[CartItem]
    total: int
    payment_method: str
    shipping_address: str
    status: OrderStatus
    created_at: str


class ToolPayload(TypedDict, total=False):
    name: str
    data: Any


class ECState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    cart: list[CartItem]
    orders: list[Order]
    last_search: list[Product]
    last_tool_payload: Optional[ToolPayload]
