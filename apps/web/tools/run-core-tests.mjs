import { rmSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const webRoot = fileURLToPath(new URL('../', import.meta.url))
const require = createRequire(import.meta.url)
// Resolve the real tsc entrypoint (a plain JS file) and execute it with the
// current Node binary: this avoids OS-specific npm bin shims (tsc.cmd) and
// works identically on POSIX CI runners and Windows workstations.
const tsc = require.resolve('typescript/bin/tsc')

function run(command, args) {
  const result = spawnSync(command, args, { cwd: webRoot, stdio: 'inherit' })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status ?? 1)
}

const outputs = [
  new URL('../.tmp-sync/', import.meta.url),
  new URL('../.tmp-customer/', import.meta.url),
  new URL('../.tmp-conflict/', import.meta.url),
  new URL('../.tmp-auth/', import.meta.url),
  new URL('../.tmp-orders/', import.meta.url),
]

for (const output of outputs) rmSync(output, { recursive: true, force: true })
try {
  run(process.execPath, [tsc, '-p', 'tsconfig.sync-test.json', '--pretty', 'false'])
  run(process.execPath, [tsc, '-p', 'tsconfig.customer-test.json', '--pretty', 'false'])
  run(process.execPath, [tsc, '-p', 'tsconfig.conflict-test.json', '--pretty', 'false'])
  run(process.execPath, [tsc, '-p', 'tsconfig.auth-test.json', '--pretty', 'false'])
  run(process.execPath, [tsc, '-p', 'tsconfig.order-test.json', '--pretty', 'false'])
  run(process.execPath, [
    '--test',
    'tests/sync/coordinator.test.mjs',
    'tests/sync/dexie-store.test.mjs',
    'tests/sync/retry-policy.test.mjs',
    'tests/sync/dexie-v3.test.mjs',
    'tests/sync/merge-workshop-core.test.mjs',
    'tests/orders/state-machine.test.mjs',
    'tests/orders/local-order.test.mjs',
    'tests/orders/order-model.test.mjs',
    'tests/auth/session.test.mjs',
    'tests/customers/local-customer.test.mjs',
    'tests/sync/conflict-center.test.mjs',
  ])
} finally {
  for (const output of outputs) rmSync(output, { recursive: true, force: true })
}
