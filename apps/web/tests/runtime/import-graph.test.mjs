import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
const root = fileURLToPath(new URL('../../src/', import.meta.url))
test('actual production value-import graph never loads old singleton or legacy sync/repositories', () => {
  const seen = new Set(),
    visit = (file) => {
      if (seen.has(file)) return
      seen.add(file)
      const source = readFileSync(file, 'utf8')
      for (const match of source.matchAll(
        /import\s+(?!type\b)(?:[\s\S]*?\s+from\s+)?['"]([^'"]+)['"]/g,
      )) {
        const spec = match[1]
        if (!spec.startsWith('.')) continue
        const next = path.resolve(path.dirname(file), spec.replace(/\.js$/, '.ts'))
        if (next.endsWith('.css')) continue
        assert.notEqual(
          next,
          path.join(root, 'local/db.ts'),
          'production loaded shared v4 singleton',
        )
        assert.ok(
          !next.includes('/sync/http-transport.ts') && !next.includes('/sync/dexie-store.ts'),
          'production loaded mutable v4 sync',
        )
        try {
          visit(next)
        } catch (error) {
          if (error.code === 'ENOENT') visit(next.replace(/\.ts$/, '.tsx'))
          else throw error
        }
      }
    }
  visit(path.join(root, 'main.tsx'))
  assert.ok(seen.has(path.join(root, 'runtime/controller.ts')))
  assert.ok(seen.has(path.join(root, 'personalization/WorkshopShell.tsx')))
  assert.ok(seen.has(path.join(root, 'features/administration/AdministrationPanel.tsx')))
  assert.ok(seen.has(path.join(root, 'features/administration/controller.ts')))
  assert.ok(seen.has(path.join(root, 'features/administration/transport.ts')))
})

test('administration owns no credential store or durable offline writer', () => {
  for (const file of ['controller.ts', 'transport.ts', 'model.ts', 'contracts.ts']) {
    const source = readFileSync(path.join(root, 'features/administration', file), 'utf8')
    assert.doesNotMatch(
      source,
      /new SessionStore|localStorage|sessionStorage|indexedDB|new Dexie|local\/db|sync\/http-transport/,
    )
    assert.doesNotMatch(source, /setInterval|navigator\.onLine|backgroundSync/)
  }
})
