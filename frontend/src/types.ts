export type Product = {
  id: string;
  name: string;
  description: string;
  price: number;
  category: string;
  stock: number;
  image_url: string;
};

export type CartItem = {
  product_id: string;
  name: string;
  unit_price: number;
  quantity: number;
  subtotal: number;
};

export type OrderStatus =
  | "pending"
  | "paid"
  | "shipped"
  | "delivered"
  | "cancelled";

export type Order = {
  order_id: string;
  items: CartItem[];
  total: number;
  payment_method: string;
  shipping_address: string;
  status: OrderStatus;
  created_at: string;
};

export type ToolEvent =
  | {
      name: "search_products";
      data: { products: Product[]; query?: string };
    }
  | {
      name: "get_product_detail";
      data: { ok: boolean; product?: Product; reason?: string };
    }
  | {
      name: "add_to_cart";
      data: {
        ok: boolean;
        cart?: CartItem[];
        total?: number;
        reason?: string;
      };
    }
  | {
      name: "view_cart";
      data: { cart: CartItem[]; total: number };
    }
  | {
      name: "remove_from_cart";
      data: {
        ok: boolean;
        cart?: CartItem[];
        total?: number;
        reason?: string;
      };
    }
  | {
      name: "checkout";
      data: { ok: boolean; order?: Order; reason?: string };
    }
  | {
      name: "get_order_status";
      data: { ok: boolean; order?: Order; reason?: string };
    };

export type ToolEventName = ToolEvent["name"];

export type StreamEvent =
  | { type: "content"; content: string }
  | { type: "tool"; name: ToolEventName; result: ToolEvent }
  | { type: "done" }
  | { type: "error"; error: string };
