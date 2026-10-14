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
  new URL('../.tmp-personalization/', import.meta.url),
  new URL('../.tmp-kernel/', import.meta.url),
  new URL('../.tmp-runtime/', import.meta.url),
  new URL('../.tmp-administration/', import.meta.url),
]

for (const output of outputs) rmSync(output, { recursive: true, force: true })
try {
  run(process.execPath, [tsc, '-p', 'tsconfig.sync-test.json', '--pretty', 'false'])
  run(process.execPath, [tsc, '-p', 'tsconfig.customer-test.json', '--pretty', 'false'])
  run(process.execPath, [tsc, '-p', 'tsconfig.conflict-test.json', '--pretty', 'false'])
  run(process.execPath, [tsc, '-p', 'tsconfig.auth-test.json', '--pretty', 'false'])
  run(process.execPath, [tsc, '-p', 'tsconfig.order-test.json', '--pretty', 'false'])
  run(process.execPath, [tsc, '-p', 'tsconfig.personalization-test.json', '--pretty', 'false'])
  run(process.execPath, [tsc, '-p', 'tsconfig.kernel-test.json', '--pretty', 'false'])
  run(process.execPath, [tsc, '-p', 'tsconfig.kernel-browser.json', '--pretty', 'false'])
  run(process.execPath, [tsc, '-p', 'tsconfig.runtime-test.json', '--pretty', 'false'])
  run(process.execPath, [tsc, '-p', 'tsconfig.administration-test.json', '--pretty', 'false'])
  run(process.execPath, [
    '--test',
    'tests/access-kernel/context.test.mjs',
    'tests/access-kernel/cutover-context.test.mjs',
    'tests/access-kernel/server-context.test.mjs',
    'tests/access-kernel/baseline-wire.test.mjs',
    'tests/access-kernel/baseline-transport.test.mjs',
    'tests/access-kernel/baseline-state.test.mjs',
    'tests/access-kernel/baseline-coordinator.test.mjs',
    'tests/access-kernel/kernel.test.mjs',
    'tests/access-kernel/migration.test.mjs',
    'tests/access-kernel/session-admission.test.mjs',
    'tests/access-kernel/client-provenance.test.mjs',
    'tests/access-kernel/client-queries.test.mjs',
    'tests/access-kernel/incremental-wire.test.mjs',
    'tests/access-kernel/incremental-state.test.mjs',
    'tests/access-kernel/incremental-transport.test.mjs',
    'tests/access-kernel/incremental-coordinator.test.mjs',
    'tests/access-kernel/push-runtime.test.mjs',
    'tests/runtime/controller.test.mjs',
    'tests/runtime/account-access.test.mjs',
    'tests/administration/model.test.mjs',
    'tests/administration/transport.test.mjs',
    'tests/administration/controller.test.mjs',
    'tests/administration/panels.test.mjs',
    'tests/administration/draft-revision.test.mjs',
    'tests/administration/draft-state.test.mjs',
    'tests/runtime/issues.test.mjs',
    'tests/runtime/transport.test.mjs',
    'tests/runtime/reachability-probe.test.mjs',
    'tests/runtime/import-graph.test.mjs',
    'tests/runtime/legacy-preservation.test.mjs',
    'tests/pwa/navigation-policy.test.mjs',
    'tests/pwa/legacy-fixture.test.mjs',
    'tests/pwa/upgrade-fixture.test.mjs',
    '../../tests/operations/local_runtime_browser_protocol.test.mjs',
    'tests/sync/coordinator.test.mjs',
    'tests/sync/dexie-store.test.mjs',
    'tests/sync/retry-policy.test.mjs',
    'tests/sync/dexie-v3.test.mjs',
    'tests/sync/merge-workshop-core.test.mjs',
    'tests/orders/state-machine.test.mjs',
    'tests/orders/local-order.test.mjs',
    'tests/orders/order-model.test.mjs',
    'tests/auth/session.test.mjs',
    'tests/auth/view-generation.test.mjs',
    'tests/auth/workshop-read-access.test.mjs',
    'tests/personalization/preferences.test.mjs',
    'tests/customers/local-customer.test.mjs',
    'tests/sync/conflict-center.test.mjs',
  ])
} finally {
  for (const output of outputs) rmSync(output, { recursive: true, force: true })
}
