/** Synthetic loopback-only route isolation for the current App, not a LAN/WAN model. */
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { startUpgradeFixture } from './upgrade_fixture_server.mjs'
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
export function startCurrentRouteFixture(port = 5176, options = {}) {
  const directory = options.directory ?? resolve(root, 'apps/web/dist')
  // Both states use the same distribution; reuse the tested per-host barrier
  // without mutating the separate historical upgrade host or its API route.
  return startUpgradeFixture(port, {
    closedApiBehavior: 'socket-drop',
    legacyDirectory: directory,
    currentDirectory: directory,
    ...(options.apiPort === undefined ? {} : { apiPort: options.apiPort }),
  })
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  startCurrentRouteFixture()
