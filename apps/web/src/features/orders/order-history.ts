import type { LocalServiceOrderEvent } from '../../local/service-order-types.js'

/** Read-time provenance only. Never persist this projection or infer delivery status from it. */
export interface OrderHistoryEvent extends LocalServiceOrderEvent {
  recordSource: 'local' | 'server'
}

/** Control/format characters cannot produce a reliable visible identifier. Source stays unchanged. */
export function historyActorId(value: unknown): string {
  return typeof value === 'string' &&
    value.length > 0 &&
    value.length <= 36 &&
    !/[\s/?#\p{Cc}\p{Cf}]/u.test(value)
    ? value
    : 'No disponible'
}

/** Keep the recorded offset and precision; never guess a timezone or normalize an invalid date. */
export function historyOccurrence(value: unknown): string | null {
  if (typeof value !== 'string' || value.length > 64) return null
  const match =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$/.exec(value)
  if (!match) return null
  const year = Number(match[1]),
    month = Number(match[2]),
    day = Number(match[3])
  const hour = Number(match[4]),
    minute = Number(match[5]),
    second = Number(match[6])
  const zone = match[7]!
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
  if (
    year < 1 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > days[month - 1]! ||
    hour > 23 ||
    minute > 59 ||
    second > 59
  )
    return null
  // RFC 3339 -00:00 explicitly means that the local offset is unknown.
  if (
    zone === '-00:00' ||
    (zone !== 'Z' && (Number(zone.slice(1, 3)) > 23 || Number(zone.slice(4, 6)) > 59))
  )
    return null
  return value
}
