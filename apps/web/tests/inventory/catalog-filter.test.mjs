import test from 'node:test'
import assert from 'node:assert/strict'
import { filterCatalogPage } from '../../.tmp-inventory/src/features/inventory/catalog-filter.js'
const rows = Object.freeze([
  Object.freeze({ product_id: 'secret-id', name: 'Cadena sintética', sku: 'CH-01', unit: 'piece' }),
  Object.freeze({ product_id: 'other', name: 'Freno', sku: 'BR-02', unit: 'piece' }),
])
test('blank filter preserves source order and identity without mutation', () => {
  const result = filterCatalogPage(rows, '  ')
  assert.deepEqual(result, rows)
  assert.equal(result[0], rows[0])
})
test('filter matches trimmed case-insensitive product name and SKU', () => {
  assert.deepEqual(filterCatalogPage(rows, ' SINTÉTICA '), [rows[0]])
  assert.deepEqual(filterCatalogPage(rows, 'br-02'), [rows[1]])
})
test('filter is literal and does not search IDs or units', () => {
  for (const query of ['secret-id', 'piece', '.*', 'missing'])
    assert.deepEqual(filterCatalogPage(rows, query), [])
})
test('empty page stays empty', () => assert.deepEqual(filterCatalogPage([], 'cadena'), []))

test('rendered catalog has native named search, reset, page boundary and announced count', async () => {
  const { createElement } = await import('react')
  const { renderToStaticMarkup } = await import('react-dom/server')
  const { CatalogPageView } =
    await import('../../.tmp-inventory/src/features/inventory/CatalogPage.js')
  const render = (query, products = rows) =>
    renderToStaticMarkup(
      createElement(CatalogPageView, {
        products,
        query,
        offset: 50,
        selectedProductId: 'secret-id',
        onQuery() {},
        onSelect() {},
      }),
    )
  const html = render('cadena')
  assert.match(html, /Filtrar esta página por nombre o SKU<input type="search"/)
  assert.match(html, /aria-describedby="inventory-filter-help"/)
  assert.match(html, /no busca en todo el catálogo ni consulta/)
  assert.match(html, /aria-live="polite"/)
  assert.match(html, /1 de 2 productos en esta página. Página 2/)
  assert.match(html, /aria-pressed="true"/)
  assert.doesNotMatch(html, /BR-02/)
  assert.match(render('missing'), /No hay coincidencias en esta página/)
  assert.match(render('missing', []), /No hay productos en esta página/)
  assert.match(render(''), /disabled="">Limpiar filtro/)
})
test('rendered catalog escapes names and SKU as text', async () => {
  const { createElement } = await import('react')
  const { renderToStaticMarkup } = await import('react-dom/server')
  const { CatalogPageView } =
    await import('../../.tmp-inventory/src/features/inventory/CatalogPage.js')
  const html = renderToStaticMarkup(
    createElement(CatalogPageView, {
      products: [{ ...rows[0], name: '<script>name</script>', sku: '<img src=x>' }],
      query: '',
      offset: 0,
      selectedProductId: null,
      onQuery() {},
      onSelect() {},
    }),
  )
  assert.match(html, /&lt;script&gt;/)
  assert.match(html, /&lt;img src=x&gt;/)
  assert.doesNotMatch(html, /<script>|<img /)
})
