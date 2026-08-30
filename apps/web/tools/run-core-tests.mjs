import { rmSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const webRoot = fileURLToPath(new URL('../', import.meta.url))

function run(command, args) {
  const result = spawnSync(command, args, { cwd: webRoot, stdio: 'inherit', shell: false })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status ?? 1)
}

const outputs = [
  new URL('../.tmp-sync/', import.meta.url),
  new URL('../.tmp-customer/', import.meta.url),
  new URL('../.tmp-conflict/', import.meta.url),
  new URL('../.tmp-auth/', import.meta.url),
]

for (const output of outputs) rmSync(output, { recursive: true, force: true })
try {
  run('tsc', ['-p', 'tsconfig.sync-test.json', '--pretty', 'false'])
  run('tsc', ['-p', 'tsconfig.customer-test.json', '--pretty', 'false'])
  run('tsc', ['-p', 'tsconfig.conflict-test.json', '--pretty', 'false'])
  run('tsc', ['-p', 'tsconfig.auth-test.json', '--pretty', 'false'])
  run('node', ['--test', 'tests/sync/coordinator.test.mjs', 'tests/sync/dexie-store.test.mjs', 'tests/auth/session.test.mjs', 'tests/customers/local-customer.test.mjs', 'tests/sync/conflict-center.test.mjs'])
} finally {
  for (const output of outputs) rmSync(output, { recursive: true, force: true })
}
