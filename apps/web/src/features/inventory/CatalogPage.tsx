import { useState, type ChangeEvent } from 'react'
import type { InventoryProduct } from './contracts.js'
import { filterCatalogPage } from './catalog-filter.js'
interface Props {
  products: readonly InventoryProduct[]
  offset: number
  selectedProductId: string | null
  onSelect: (id: string) => void
}
export function CatalogPage(props: Props) {
  const [filter, setFilter] = useState({ products: props.products, query: '' })
  // A replacement receipt must never inherit a previous page/scope's query.
  if (filter.products !== props.products) setFilter({ products: props.products, query: '' })
  const query = filter.products === props.products ? filter.query : ''
  return (
    <CatalogPageView
      {...props}
      query={query}
      onQuery={(query) => setFilter({ products: props.products, query })}
    />
  )
}
export function CatalogPageView({
  products,
  offset,
  selectedProductId,
  onSelect,
  query,
  onQuery,
}: Props & { query: string; onQuery: (query: string) => void }) {
  const visible = filterCatalogPage(products, query)
  return (
    <>
      <div className="inventory-actions">
        <label>
          Filtrar esta página por nombre o SKU
          <input
            type="search"
            value={query}
            autoComplete="off"
            aria-describedby="inventory-filter-help"
            onChange={(event: ChangeEvent<HTMLInputElement>) => onQuery(event.currentTarget.value)}
          />
        </label>
        <button type="button" disabled={!query} onClick={() => onQuery('')}>
          Limpiar filtro
        </button>
      </div>
      <p id="inventory-filter-help">
        Solo filtra los productos de esta página; no busca en todo el catálogo ni consulta
        existencias. Al cambiar o actualizar la página se limpia el filtro.
      </p>
      <p role="status" aria-live="polite" aria-atomic="true">
        {visible.length} de {products.length} productos en esta página. Página{' '}
        {Math.floor(offset / 50) + 1}.
      </p>
      {products.length === 0 ? (
        <p>No hay productos en esta página.</p>
      ) : visible.length === 0 ? (
        <p>No hay coincidencias en esta página. Limpia el filtro o consulta otra página.</p>
      ) : (
        <ul className="inventory-products" aria-label="Productos de inventario">
          {visible.map((product) => (
            <li key={product.product_id}>
              <div>
                <strong>{product.name}</strong>
                <span>SKU: {product.sku}</span>
                <span>Unidad: {product.unit}</span>
              </div>
              <button
                type="button"
                aria-label={`Consultar ${product.name}`}
                aria-pressed={selectedProductId === product.product_id}
                onClick={() => onSelect(product.product_id)}
              >
                Consultar producto
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
