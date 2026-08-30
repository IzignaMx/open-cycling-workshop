import type { ReactNode } from 'react'

export interface ButtonProps {
  children: ReactNode
  disabled?: boolean
  type?: 'button' | 'submit' | 'reset'
  onClick?: () => void
}

export function Button({ children, disabled = false, type = 'button', onClick }: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className="min-h-11 rounded-[var(--ocwp-radius-sm)] bg-[var(--ocwp-color-accent)] px-4 py-2 font-semibold text-white transition hover:bg-[var(--ocwp-color-accent-strong)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ocwp-color-accent)] disabled:opacity-50"
    >
      {children}
    </button>
  )
}
