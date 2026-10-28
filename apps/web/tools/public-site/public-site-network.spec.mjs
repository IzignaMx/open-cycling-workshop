import { createServer } from 'node:http'
import { expect, test } from '@playwright/test'
import { guardPublicSiteNetwork } from './public-site-network'

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      if (!address || typeof address === 'string') return reject(new Error('Missing address'))
      resolve(`http://127.0.0.1:${address.port}`)
    })
  })
}

function close(server) {
  server.closeAllConnections()
  return new Promise((resolve, reject) =>
    server.close((error) => (error ? reject(error) : resolve())),
  )
}

test('network guard refuses real redirects before contacting an out-of-scope origin', async ({
  browser,
}) => {
  let trapHits = 0
  let sourceHits = 0
  const trap = createServer((_request, response) => {
    trapHits += 1
    response.end('must never be requested')
  })
  const trapURL = await listen(trap)
  const source = createServer((_request, response) => {
    sourceHits += 1
    response.writeHead(302, { Location: `${trapURL}/outside` })
    response.end()
  })
  const sourceURL = await listen(source)
  const context = await browser.newContext({ serviceWorkers: 'block' })
  try {
    const rejected = []
    await guardPublicSiteNetwork(context, `${sourceURL}/project/`, rejected)
    const page = await context.newPage()
    await expect(page.goto(`${sourceURL}/project/`)).rejects.toThrow()
    expect(sourceHits).toBe(1)
    expect(trapHits).toBe(0)
    expect(rejected).toEqual(['redirect-or-status'])
    await expect(page.goto(`${trapURL}/outside`)).rejects.toThrow()
    expect(trapHits).toBe(0)
    expect(rejected).toEqual(['redirect-or-status', 'destination'])
  } finally {
    await context.close()
    await close(source)
    await close(trap)
  }
})
