import { rmSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const packageRoot = fileURLToPath(new URL('../', import.meta.url))
const require = createRequire(import.meta.url)
// Resolve the real tsc entrypoint (a plain JS file) and execute it with the
// current Node binary: this avoids OS-specific npm bin shims (tsc.cmd) and
// works identically on POSIX CI runners and Windows workstations.
const tsc = require.resolve('typescript/bin/tsc')

function run(command, args) {
  const result = spawnSync(command, args, { cwd: packageRoot, stdio: 'inherit' })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status ?? 1)
}

const output = new URL('../.tmp-test/', import.meta.url)
rmSync(output, { recursive: true, force: true })
try {
  run(process.execPath, [tsc, '-p', 'tsconfig.test.json', '--pretty', 'false'])
  run(process.execPath, ['--test', 'tests/client.test.mjs'])
} finally {
  rmSync(output, { recursive: true, force: true })
}
