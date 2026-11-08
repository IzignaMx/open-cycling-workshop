import type { ReactNode } from 'react'

export interface ButtonProps {
  children: ReactNode
  'aria-label'?: string
  disabled?: boolean
  type?: 'button' | 'submit' | 'reset'
  onClick?: () => void
}

export function Button({
  children,
  disabled = false,
  type = 'button',
  onClick,
  'aria-label': ariaLabel,
}: ButtonProps) {
  return (
    <button
      aria-label={ariaLabel}
      type={type}
      disabled={disabled}
      onClick={onClick}
      className="min-h-11 rounded-[var(--ocwp-radius-sm)] bg-[var(--ocwp-color-accent)] px-4 py-2 font-semibold text-[var(--ocwp-color-on-accent)] transition hover:bg-[var(--ocwp-color-accent-strong)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ocwp-color-focus)] disabled:opacity-50"
    >
      {children}
    </button>
  )
}
