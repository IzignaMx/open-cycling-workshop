import eslint from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  {
    ignores: [
      '**/node_modules/**',
      '**/dist/**',
      '**/.tmp-*/**',
      '**/playwright-report/**',
      '**/test-results/**',
      'packages/api-client/openapi.json',
    ],
  },
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.mjs'],
    languageOptions: {
      // Node test/tool scripts (node:test, node:assert) plus the browser fetch
      // globals (Response, Headers, URL) used by in-process API mocks.
      globals: { ...globals.node, ...globals.browser },
    },
  },
  {
    files: ['**/*.{ts,tsx}'],
    plugins: {
      'react-hooks': reactHooks,
    },
    rules: {
      ...reactHooks.configs.flat.recommended.rules,
      '@typescript-eslint/consistent-type-imports': ['error', { prefer: 'type-imports' }],
      '@typescript-eslint/no-explicit-any': 'error',
      // Leading-underscore members are intentionally omitted via rest siblings
      // (e.g. stripping persisted fields before building sync envelopes).
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', ignoreRestSiblings: true },
      ],
    },
  },
  {
    // static-shims.d.ts provides ambient module declarations so offline
    // typechecks work without node_modules; declaring those modules as `any`
    // is its entire purpose and must not leak into product code rules.
    files: ['apps/web/tools/static-shims.d.ts'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
)
