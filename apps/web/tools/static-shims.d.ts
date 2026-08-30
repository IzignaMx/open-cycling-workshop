declare namespace JSX {
  interface IntrinsicElements {
    [name: string]: any
  }
}

declare module 'react' {
  export type ReactNode = any
  export type FormEvent<T = Element> = { preventDefault(): void; currentTarget: T }
  export type ChangeEvent<T = Element> = { currentTarget: T }
  export function useMemo<T>(factory: () => T, deps: readonly unknown[]): T
  export function useCallback<T extends (...args: any[]) => any>(callback: T, deps: readonly unknown[]): T
  export function useState<T>(initial: T | (() => T)): [T, (value: T | ((previous: T) => T)) => void]
  export function useEffect(effect: () => void | (() => void), deps?: readonly unknown[]): void
}

declare module 'react/jsx-runtime' {
  export const Fragment: any
  export function jsx(type: any, props: any, key?: any): any
  export function jsxs(type: any, props: any, key?: any): any
}

declare module 'react-dom/client' {
  export function createRoot(element: Element): { render(node: any): void }
}

declare module 'vite' {
  export function defineConfig(config: any): any
}

declare module '@vitejs/plugin-react' {
  export default function react(options?: any): any
}

declare module '@tailwindcss/vite' {
  export default function tailwindcss(options?: any): any
}

declare module 'vite-plugin-pwa' {
  export function VitePWA(options?: any): any
}

declare module '*.css' {
  const value: string
  export default value
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}
