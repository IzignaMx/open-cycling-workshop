// Aggregate-only diagnostics. Never serialize names, errors, output or environment.
// This is source-bound troubleshooting metadata, not an authenticity/qualification proof.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const maximum = 9_999_999
const integer = (value) => Number.isInteger(value) && value >= 0 && value <= maximum
const keys = ['tests', 'suites', 'passed', 'failed', 'cancelled', 'skipped', 'todo']
const inventory = new Map()
const runner = readFileSync(new URL('./run-core-tests.mjs', import.meta.url), 'utf8')
for (const match of runner.matchAll(/'((?:tests\/|\.\.\/\.\.\/tests\/)[a-z0-9/-]+\.test\.mjs)'/g)) {
  const absolute = fileURLToPath(new URL(`../${match[1]}`, import.meta.url))
  const relative = match[1].startsWith('../../') ? match[1].slice(6) : `apps/web/${match[1]}`
  if (relative.length <= 200) inventory.set(absolute, relative)
}

export default async function* aggregateReporter(source) {
  const report = { version: 1, failures: [], omitted: 0, overflow: false, counts: null }
  for await (const { type, data } of source) {
    if (type === 'test:fail') {
      if (report.failures.length === 8) {
        if (report.omitted < maximum) report.omitted += 1
        else report.overflow = true
        continue
      }
      const file = inventory.get(data.file) ?? null
      report.failures.push({
        file,
        line: file && integer(data.line) && data.line > 0 ? data.line : null,
        column: file && integer(data.column) && data.column > 0 ? data.column : null,
      })
    } else if (type === 'test:summary' && data.file === undefined) {
      report.counts =
        data.counts && keys.every((key) => integer(data.counts[key]))
          ? Object.fromEntries(keys.map((key) => [key, data.counts[key]]))
          : null
    }
  }
  yield JSON.stringify(report) + '\n'
}
