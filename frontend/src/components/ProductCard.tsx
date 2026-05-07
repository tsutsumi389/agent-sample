import type { Product } from "../types";

export function ProductCard({ product }: { product: Product }) {
  return (
    <article className="product-card">
      <img className="product-image" src={product.image_url} alt={product.name} />
      <div className="product-body">
        <div className="product-id">{product.id}</div>
        <div className="product-name">{product.name}</div>
        <div className="product-desc">{product.description}</div>
        <div className="product-meta">
          <span className="product-price">¥{product.price.toLocaleString()}</span>
          <span className="product-stock">在庫{product.stock}</span>
          <span className="product-category">{product.category}</span>
        </div>
      </div>
    </article>
  );
}

export function ProductCardList({ products }: { products: Product[] }) {
  if (products.length === 0) {
    return <div className="product-empty">条件に一致する商品はありません。</div>;
  }
  return (
    <div className="product-grid">
      {products.map((p) => (
        <ProductCard key={p.id} product={p} />
      ))}
    </div>
  );
}
