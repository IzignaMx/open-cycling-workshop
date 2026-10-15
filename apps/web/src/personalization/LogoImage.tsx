import { useState } from 'react'
import { inspectLogoBacking, LOGO_BACKINGS, type LogoBacking } from './logo-backing.js'

interface Props {
  src: string
  alt: string
  width: string
  height: string
  className?: string
  onError?: () => void
}

export function LogoImage({ src, className, ...props }: Props) {
  const [plate, setPlate] = useState<{ source: string; backing: LogoBacking } | null>(null)
  const backing = plate?.source === src ? plate.backing : 'light'
  return (
    <img
      {...props}
      src={src}
      className={`logo-image${className ? ` ${className}` : ''}`}
      data-logo-backing={backing}
      style={{ backgroundColor: LOGO_BACKINGS[backing] }}
      onLoad={(event: { currentTarget: HTMLImageElement }) => {
        const chosen = inspectLogoBacking(event.currentTarget, src)
        if (chosen !== null) setPlate({ source: src, backing: chosen })
      }}
    />
  )
}
