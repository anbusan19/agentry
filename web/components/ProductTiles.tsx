"use client";

interface Product {
  name: string;
  price: string;
  url: string;
}

export interface ProductBatch {
  query: string;
  results: Product[];
}

/**
 * Renders search_products results as a strip of interactive tiles instead
 * of the model retyping a product list as prose — the actual structured
 * data (name/price/url) comes straight from server.py's /api/chat response,
 * pulled out of the Strands Agent's own tool-call trace for that turn.
 */
export default function ProductTiles({
  batches,
  onAdd,
  addingUrl,
}: {
  batches: ProductBatch[];
  onAdd: (item: Product) => void;
  addingUrl: string | null;
}) {
  return (
    <div className="tiles">
      {batches.map((batch, bi) => (
        <div className="tiles__batch" key={bi}>
          {batch.query && <span className="tiles__query">&ldquo;{batch.query}&rdquo;</span>}
          <div className="tiles__row">
            {batch.results.map((item) => {
              const isAdding = addingUrl === item.url;
              return (
                <div className="tile" key={item.url}>
                  <span className="tile__name">{item.name}</span>
                  <div className="tile__foot">
                    <span className="tile__price">{item.price}</span>
                    <button
                      className="tile__add"
                      onClick={() => onAdd(item)}
                      disabled={isAdding}
                    >
                      {isAdding ? "Adding…" : "Add"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
