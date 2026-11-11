import { useState } from 'react'

// Category icons in one style (24 px grid, 1.6 stroke, like lucide). They stand in for product photos until phase 9
const ICONS = {
  cpu: <><rect x="6" y="6" width="12" height="12" rx="1.5" /><rect x="9.5" y="9.5" width="5" height="5" rx=".5" /><path d="M9 2.5v3M12 2.5v3M15 2.5v3M9 18.5v3M12 18.5v3M15 18.5v3M2.5 9h3M2.5 12h3M2.5 15h3M18.5 9h3M18.5 12h3M18.5 15h3" /></>,
  motherboard: <><rect x="3" y="3" width="18" height="18" rx="2" /><rect x="6" y="6" width="5" height="5" rx=".5" /><path d="M14 6v6M17 6v6M6 14.5h12M6 17.5h7" /><circle cx="16.5" cy="17.5" r="1" /></>,
  gpu: <><path d="M2 4v16M2 6h18a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H2M8 18v2h8v-2" /><circle cx="8.5" cy="12" r="3" /><circle cx="15.5" cy="12" r="3" /></>,
  ram: <><rect x="2" y="7" width="20" height="9" rx="1" /><path d="M5 10h2v3H5zM9 10h2v3H9zM13 10h2v3h-2zM17 10h2v3h-2zM4 16v2M7 16v2M10 16v2M14 16v2M17 16v2M20 16v2" /></>,
  ssd: <><rect x="4" y="3" width="16" height="18" rx="2" /><rect x="7" y="6" width="10" height="7" rx="1" /><path d="M7.5 17h4" /><circle cx="16" cy="17" r=".8" /></>,
  hdd: <><rect x="4" y="2" width="16" height="20" rx="2" /><circle cx="12" cy="10" r="5" /><circle cx="12" cy="10" r="1" /><path d="M16.5 18.5 13 11.5" /></>,
  flash: <><rect x="7" y="9" width="10" height="13" rx="2" /><path d="M9 9V3h6v6M11 5.5h.01M13 5.5h.01" /></>,
  psu: <><rect x="2" y="5" width="20" height="14" rx="2" /><circle cx="14.5" cy="12" r="4" /><path d="M14.5 8v8M10.5 12h8M6.5 9 5 12h2.5L6 15" /></>,
  ups: <><rect x="5" y="2.5" width="14" height="19" rx="2" /><path d="m13 6-3 5h4l-3 5M8.5 18.5h7" /></>,
  case: <><rect x="6" y="2" width="12" height="20" rx="2" /><path d="M9 6h6M9 9h6" /><circle cx="12" cy="15.5" r="2.5" /></>,
  cooling: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="1.5" /><path d="M12 10.5c0-3 1-5 3.5-5.5M13.5 12c3 0 5 1 5.5 3.5M12 13.5c0 3-1 5-3.5 5.5M10.5 12c-3 0-5-1-5.5-3.5" /></>,
  monitor: <><rect x="2" y="3" width="20" height="13" rx="2" /><path d="M12 16v4M8 20h8" /></>,
  laptop: <><rect x="4" y="4" width="16" height="11" rx="1.5" /><path d="M2.5 19h19L20 15H4z" /></>,
  aio: <><rect x="2" y="3" width="20" height="15" rx="2" /><path d="M2 14h20M10 18l-1 3h6l-1-3" /></>,
  desktop: <><rect x="2" y="4" width="12" height="10" rx="1.5" /><path d="M8 14v3M5 17h6M18.5 8h2" /><rect x="17" y="4" width="5" height="16" rx="1" /></>,
  keyboard: <><rect x="2" y="6" width="20" height="12" rx="2" /><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M6 14h.01M18 14h.01M9 14h6" /></>,
  mouse: <><rect x="6" y="3" width="12" height="18" rx="6" /><path d="M12 3v6" /></>,
  headphones: <><path d="M3 18v-6a9 9 0 0 1 18 0v6" /><path d="M21 19a2 2 0 0 1-2 2h-1v-6h3zM3 19a2 2 0 0 0 2 2h1v-6H3z" /></>,
  speakers: <><rect x="5" y="2" width="14" height="20" rx="2" /><circle cx="12" cy="14" r="4" /><circle cx="12" cy="6.5" r="1.5" /></>,
  printer: <><path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" /><rect x="6" y="14" width="12" height="8" /></>,
  projector: <><rect x="2" y="7" width="20" height="10" rx="2" /><circle cx="16" cy="12" r="3" /><path d="M5 11h4M5 14h3M6 17v2M18 17v2" /></>,
  chair: <><path d="M8 3h8a1 1 0 0 1 1 1v9H7V4a1 1 0 0 1 1-1zM5 13h14v3H5zM12 16v4M8 21h8" /></>,
  other: <><path d="m21 8-9-5-9 5v8l9 5 9-5zM3 8l9 5 9-5M12 13v8" /></>,
}

export const ICON_CATEGORIES = Object.keys(ICONS)

export function CategoryIcon({ category, className = 'size-6' }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden className={className}>
      {ICONS[category] || ICONS.other}
    </svg>
  )
}

// The picture place of a product: the main photo when there is one (phase 14), otherwise the category icon.
// The size comes from `className` (e.g. "aspect-square w-full"), so a photo fits the same box without layout changes;
// a grey silhouette stays until the photo has loaded (lazy), a broken photo falls back to the icon
export function ProductVisual({ category, image, alt = '', className = '', iconClassName = 'size-1/2 max-h-16 max-w-16' }) {
  const [done, setDone] = useState({}) // { src, state: 'ok' | 'error' } of the last loaded picture
  const state = done.src === image ? done.state : 'loading'
  const setState = (s) => setDone({ src: image, state: s })
  const photo = image && state !== 'error'
  return (
    <div className={`relative flex shrink-0 items-center justify-center overflow-hidden rounded-lg text-primary ${photo ? 'bg-white' : 'bg-primary-soft/60'} ${className}`}>
      {photo && state === 'loading' && (
        <span className="absolute inset-0 flex animate-pulse items-center justify-center bg-surface-2 text-line-strong" aria-hidden>
          <CategoryIcon category={category} className={iconClassName} />
        </span>
      )}
      {photo
        ? <img src={image} alt={alt} loading="lazy" decoding="async" onLoad={() => setState('ok')} onError={() => setState('error')}
            className={`size-full object-contain transition-opacity ${state === 'ok' ? 'opacity-100' : 'opacity-0'}`} />
        : <CategoryIcon category={category} className={iconClassName} />}
    </div>
  )
}
