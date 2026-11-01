import { Link } from 'react-router-dom'
import { BRAND } from '../config/brand'

// Temporary logo: the mark + the name with the "_" in the accent colour. Same mark as public/favicon.svg
export function LogoMark({ className = 'size-8' }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="var(--color-primary)" />
      <path d="M6.5 20.5 12.2 7h2.6l5.7 13.5h-3l-1-2.6h-6l-1 2.6zm5-5h4l-2-5.2z" fill="#fff" />
      <rect x="19" y="23" width="8" height="3" rx="1.5" fill="var(--color-accent)" />
    </svg>
  )
}

export function BrandName({ className = '' }) {
  const [first, ...rest] = BRAND.name.split('_')
  return (
    <span className={`font-extrabold tracking-tight ${className}`}>
      {first}{rest.length > 0 && <span className="text-accent">_</span>}{rest.join('_')}
    </span>
  )
}

export default function Logo({ onClick }) {
  return (
    <Link to="/" onClick={onClick} className="flex shrink-0 items-center gap-2 text-lg text-ink" aria-label={BRAND.name}>
      <LogoMark />
      <BrandName />
    </Link>
  )
}
