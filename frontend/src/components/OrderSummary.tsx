import type { Order } from "../types";

const STATUS_LABEL: Record<Order["status"], string> = {
  pending: "保留中",
  paid: "支払済",
  shipped: "発送済",
  delivered: "配達済",
  cancelled: "キャンセル",
};

export function OrderSummary({ order }: { order: Order }) {
  return (
    <div className="order-summary">
      <div className="order-header">
        <span className="order-id">{order.order_id}</span>
        <span className={`order-status order-status-${order.status}`}>
          {STATUS_LABEL[order.status]}
        </span>
      </div>
      <div className="order-meta">
        <div>
          <span className="order-label">合計:</span>
          <span className="order-total">¥{order.total.toLocaleString()}</span>
        </div>
        <div>
          <span className="order-label">支払:</span>
          {order.payment_method}
        </div>
        <div>
          <span className="order-label">配送先:</span>
          {order.shipping_address}
        </div>
      </div>
      <table className="order-items">
        <thead>
          <tr>
            <th>商品</th>
            <th>数量</th>
            <th>小計</th>
          </tr>
        </thead>
        <tbody>
          {order.items.map((item) => (
            <tr key={item.product_id}>
              <td>{item.name}</td>
              <td>{item.quantity}</td>
              <td>¥{item.subtotal.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
