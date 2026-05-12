import type { CartItem } from "../types";
import { formatJPY } from "../utils/format";

export function CartView({
  cart,
  total,
  title = "カート",
}: {
  cart: CartItem[];
  total: number;
  title?: string;
}) {
  if (cart.length === 0) {
    return <div className="cart-empty">{title}は空です。</div>;
  }
  return (
    <div className="cart-view">
      <div className="cart-header">{title}</div>
      <table className="cart-table">
        <thead>
          <tr>
            <th>商品</th>
            <th>単価</th>
            <th>数量</th>
            <th>小計</th>
          </tr>
        </thead>
        <tbody>
          {cart.map((item) => (
            <tr key={item.product_id}>
              <td>
                <span className="cart-product-name">{item.name}</span>
                <span className="cart-product-id">{item.product_id}</span>
              </td>
              <td>{formatJPY(item.unit_price)}</td>
              <td>{item.quantity}</td>
              <td>{formatJPY(item.subtotal)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={3}>合計</td>
            <td>{formatJPY(total)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
