import type { ToolEvent } from "../types";
import { CartView } from "./CartView";
import { OrderSummary } from "./OrderSummary";
import { ProductCardList } from "./ProductCard";

export function ToolEventView({ event }: { event: ToolEvent }) {
  switch (event.name) {
    case "search_products":
      return <ProductCardList products={event.data.products} />;

    case "get_product_detail":
      if (!event.data.ok || !event.data.product) {
        return <div className="tool-error">{event.data.reason ?? "詳細を取得できませんでした。"}</div>;
      }
      return <ProductCardList products={[event.data.product]} />;

    case "view_cart":
      return <CartView cart={event.data.cart} total={event.data.total} />;

    case "add_to_cart":
    case "remove_from_cart": {
      if (!event.data.ok) {
        return <div className="tool-error">{event.data.reason ?? "カートを更新できませんでした。"}</div>;
      }
      return (
        <CartView
          cart={event.data.cart ?? []}
          total={event.data.total ?? 0}
          title={event.name === "add_to_cart" ? "カート(追加後)" : "カート(削除後)"}
        />
      );
    }

    case "checkout":
      if (!event.data.ok || !event.data.order) {
        return <div className="tool-error">{event.data.reason ?? "決済できませんでした。"}</div>;
      }
      return <OrderSummary order={event.data.order} />;

    case "get_order_status":
      if (!event.data.ok || !event.data.order) {
        return <div className="tool-error">{event.data.reason ?? "注文が見つかりません。"}</div>;
      }
      return <OrderSummary order={event.data.order} />;
  }
}
