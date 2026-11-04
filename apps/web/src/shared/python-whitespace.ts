// Python str.split/strip/re whitespace, for admission checks only.
// Never use this shadow projection to rewrite stored prepared input.
export const pythonWhitespace =
  '\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000'
const nonWhitespace = new RegExp(`[^${pythonWhitespace}]`, 'u')
export const hasPythonText = (value: string): boolean => nonWhitespace.test(value)
