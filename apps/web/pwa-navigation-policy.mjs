// API and operational endpoints must never become successful HTML responses
// through the service worker's offline application-shell fallback. Caddy path
// matching is case insensitive and decodes escapes; reject encoded pathnames
// conservatively rather than implement a divergent decoding algorithm here.
// Current application routes use plain paths/UUIDs; query escapes are allowed.
export const navigationFallbackDenylist = [
  /^\/+api(?:\/|\?|$)/i,
  /^\/+health(?:\/|\?|$)/i,
  /^[^?]*%/,
]
