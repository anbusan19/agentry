"use client";

import { useState } from "react";

interface Product {
  name: string;
  price: string;
  url: string;
  image?: string;
}

export interface ProductBatch {
  query: string;
  results: Product[];
}

function TileImage({ src, alt }: { src?: string; alt: string }) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    // No photo, or it 404'd — a plain placeholder beats a broken-image icon.
    return (
      <div className="tile__img tile__img--placeholder" aria-hidden="true">
        <span>{alt.slice(0, 1).toUpperCase()}</span>
      </div>
    );
  }

  // Plain <img>, not next/image: these come from whichever storefront's own
  // CDN at request time, an allowlist of remote domains isn't a fit here.
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img className="tile__img" src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} />
  );
}

/**
 * Renders search_products results as a strip of interactive tiles instead
 * of the model retyping a product list as prose — the actual structured
 * data (name/price/url/image) comes straight from server.py's /api/chat
 * response, pulled out of the Strands Agent's own tool-call trace for that
 * turn.
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
                  <TileImage src={item.image} alt={item.name} />
                  <div className="tile__body">
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
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
