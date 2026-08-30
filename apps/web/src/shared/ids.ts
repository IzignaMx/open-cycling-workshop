let lastMs = -1
let sequence = 0

function randomBits(bits: number): bigint {
  const byteCount = Math.ceil(bits / 8)
  const bytes = new Uint8Array(byteCount)
  crypto.getRandomValues(bytes)
  let value = 0n
  for (const byte of bytes) value = (value << 8n) | BigInt(byte)
  return value & ((1n << BigInt(bits)) - 1n)
}

export function newUuidV7(): string {
  const current = Date.now()
  if (current > lastMs) {
    lastMs = current
    sequence = Number(randomBits(12))
  } else {
    sequence += 1
    if (sequence > 0xfff) {
      lastMs += 1
      sequence = 0
    }
  }

  const timestamp = BigInt(lastMs) & ((1n << 48n) - 1n)
  const randA = BigInt(sequence & 0xfff)
  const randB = randomBits(62)
  const value = (timestamp << 80n) | (0x7n << 76n) | (randA << 64n) | (0x2n << 62n) | randB
  const hex = value.toString(16).padStart(32, '0')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
