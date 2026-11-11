import { Link } from 'react-router-dom'
import { BRAND } from '../config/brand'

// Temporary logo: the mark + the name with its last word in the primary colour. Same mark as public/favicon.svg
export function LogoMark({ className = 'size-8' }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="var(--color-primary)" />
      <path d="M9 22.75 14.7 9.25h2.6l5.7 13.5h-3l-1-2.6h-6l-1 2.6zm5-5h4l-2-5.2z" fill="#fff" />
      <circle cx="25.5" cy="6.5" r="2.5" fill="var(--color-accent)" />
    </svg>
  )
}

export function BrandName({ className = '' }) {
  const words = BRAND.name.split(' ')
  const last = words.pop()
  return (
    <span className={`font-extrabold tracking-tight ${className}`}>
      {words.length > 0 && `${words.join(' ')} `}<span className="text-primary">{last}</span>
    </span>
  )
}

export default function Logo({ onClick, to = '/' }) {
  return (
    <Link to={to} onClick={onClick} className="flex shrink-0 items-center gap-2 text-lg whitespace-nowrap text-ink" aria-label={BRAND.name}>
      <LogoMark />
      <BrandName />
    </Link>
  )
}
