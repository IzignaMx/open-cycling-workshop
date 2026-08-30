import { rmSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const packageRoot = fileURLToPath(new URL('../', import.meta.url))

function run(command, args) {
  const result = spawnSync(command, args, { cwd: packageRoot, stdio: 'inherit', shell: false })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status ?? 1)
}

const output = new URL('../.tmp-test/', import.meta.url)
rmSync(output, { recursive: true, force: true })
try {
  run('tsc', ['-p', 'tsconfig.test.json', '--pretty', 'false'])
  run('node', ['--test', 'tests/client.test.mjs'])
} finally {
  rmSync(output, { recursive: true, force: true })
}
