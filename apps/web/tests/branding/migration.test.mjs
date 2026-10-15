import 'fake-indexeddb/auto'
import test from 'node:test'
import assert from 'node:assert/strict'
import { createKernelDatabase } from '../../.tmp-kernel/src/access-kernel/database.js'

function request(r) {
  return new Promise((resolve, reject) => {
    r.onsuccess = () => resolve(r.result)
    r.onerror = () => reject(r.error)
  })
}
test('additive native60→70 preserves every v6 store exactly and closes the old tab', async () => {
  const name = 'branding-upgrade-' + crypto.randomUUID(),
    template = createKernelDatabase(name)
  const schemas = template.tables
    .filter((table) => table.name !== 'brandingSnapshots')
    .map((table) => ({ name: table.name, schema: table.schema }))
  const open = indexedDB.open(name, 60)
  open.onupgradeneeded = () => {
    for (const { name, schema } of schemas) {
      const store = open.result.createObjectStore(name, {
        keyPath: schema.primKey.keyPath,
        autoIncrement: schema.primKey.auto,
      })
      for (const index of schema.indexes)
        store.createIndex(index.name, index.keyPath, {
          unique: index.unique,
          multiEntry: index.multi,
        })
    }
  }
  const source = await request(open),
    originals = new Map()
  const tx = source.transaction(
    schemas.map((s) => s.name),
    'readwrite',
  )
  for (const { name, schema } of schemas) {
    const row = { unknown: { exact: ['retained', null, 7] } }
    for (const key of Array.isArray(schema.primKey.keyPath)
      ? schema.primKey.keyPath
      : [schema.primKey.keyPath])
      row[key] = key === 'sequence' ? 7 : `original-${key}`
    originals.set(name, row)
    tx.objectStore(name).add(row)
  }
  await new Promise((resolve, reject) => {
    tx.oncomplete = resolve
    tx.onabort = () => reject(tx.error)
  })
  let closed = false
  source.onversionchange = () => {
    closed = true
    source.close()
  }
  try {
    await template.open()
    assert.equal(template.backendDB().version, 70)
    assert.equal(closed, true)
    assert.equal(template.tables.length, 17)
    assert.equal(await template.brandingSnapshots.count(), 0)
    for (const { name } of schemas)
      assert.deepEqual(await template.table(name).toArray(), [originals.get(name)], name)
  } finally {
    source.close()
    template.close()
    await template.delete()
  }
})
