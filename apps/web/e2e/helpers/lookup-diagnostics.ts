/** Test-only closed diagnostic projection. Never returns names, identifiers or raw text. */
export function lookupDiagnostic(input: {
  stage: string
  phase: string
  expectedIds: readonly string[]
  admittedIds: readonly string[]
  optionIds: readonly string[]
  targetId: string
  targetNameMatches: boolean
  query: string
  expectedQuery: string
  status: string
  selectedId: string
}) {
  const expected = new Set(input.expectedIds.slice(0, 51))
  const admitted = new Set(input.admittedIds.slice(0, 52))
  const status = input.status.slice(0, 512)
  const pageMatch = /(?:^|\s)(\d{1,3}) páginas revisadas\./.exec(status)
  return {
    schema: 1,
    stage: ['baseline', 'page_one', 'page_two', 'done'].includes(input.stage)
      ? input.stage
      : 'unknown',
    phase: ['READY', 'BOOTING', 'VERIFYING', 'HELD', 'ANONYMOUS'].includes(input.phase)
      ? input.phase
      : 'unknown',
    baselineCount: Math.min(input.admittedIds.length, 52),
    baselineExact:
      expected.size === 51 &&
      input.admittedIds.length === 51 &&
      [...expected].every((id) => admitted.has(id)),
    targetAdmitted: expected.has(input.targetId) && admitted.has(input.targetId),
    targetNameMatches: input.targetNameMatches === true,
    queryMatches: input.query === input.expectedQuery,
    pages: pageMatch ? Math.min(Number(pageMatch[1]), 99) : null,
    status: status.includes('No se pudo consultar la lista local.')
      ? 'read_failed'
      : status.includes('Consultando clientes locales')
        ? 'busy'
        : status.includes('Quedan páginas locales por revisar.')
          ? 'more'
          : status.includes('Fin de los registros disponibles localmente;')
            ? 'exhausted'
            : status.includes('Escribe un nombre')
              ? 'query_required'
              : 'unknown',
    optionCount: Math.min(input.optionIds.length, 52),
    optionOverflow: input.optionIds.length > 52,
    unexpectedOption: input.optionIds.slice(0, 52).some((id) => id !== '' && !expected.has(id)),
    targetOption:
      expected.has(input.targetId) && input.optionIds.slice(0, 52).includes(input.targetId),
    selectionEmpty: input.selectedId === '',
  }
}
