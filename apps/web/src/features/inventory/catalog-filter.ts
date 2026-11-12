import type { InventoryProduct } from './contracts.js'
export function filterCatalogPage<T extends Pick<InventoryProduct, 'name' | 'sku'>>(
  products: readonly T[],
  query: string,
): readonly T[] {
  const normalized = query.trim().toLowerCase()
  return normalized
    ? products.filter(
        (product) =>
          product.name.toLowerCase().includes(normalized) ||
          product.sku.toLowerCase().includes(normalized),
      )
    : products
}
