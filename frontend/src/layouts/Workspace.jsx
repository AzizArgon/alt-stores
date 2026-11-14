import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, useLocation } from 'react-router-dom'
import { UnreadBadge } from '../components/Header'
import Logo from '../components/Logo'
import { DemoBanner } from './StoreLayout'

// A work interface apart from the storefront: its own top bar, the sections on the left on a computer and a tab bar
// at the bottom on a phone. No storefront search, city, catalog or footer.
// The seller cabinet uses it now; the admin (phase 12) is meant to be the third interface on the same frame.
//   home      — where the logo leads (the overview)
//   subtitle  — "for sellers" next to the logo
//   actions   — the right side of the top bar (buttons, avatar)
//   sections  — [{ to, key, icon, end, tab }]: key → `${navKey}.${key}`, short tab name → `${tabKey}.${key}`;
//               only sections with `tab` fit the phone bar. Without sections: one centred column (login pages).
//               Phase 12.5: a section may have `pages` [{ to, key, badge, deep }] — one item of the menu (active on
//               any of its pages, the pages are tabs at the top of the page); `side: false` — only in the phone bar.
//   top       — a line above the page (the tabs of the open section)
// Phase 17.1: the left menu folds to icons (names in the hints). The choice is remembered;
// until the user chooses, screens narrower than 1440 px start with the menu folded
export const MENU_KEY = 'alt_menu_folded'
export const FOLD_BELOW = 1440
export function initialFolded(saved, width) {
  if (saved === '1') return true
  if (saved === '0') return false
  return width < FOLD_BELOW
}
function useFolded() {
  const [folded, setFolded] = useState(() => {
    let saved = null
    try { saved = localStorage.getItem(MENU_KEY) } catch { /* private mode */ }
    return initialFolded(saved, globalThis.innerWidth ?? FOLD_BELOW)
  })
  const toggle = () => setFolded((was) => {
    try { localStorage.setItem(MENU_KEY, was ? '0' : '1') } catch { /* private mode */ }
    return !was
  })
  return [folded, toggle]
}

export default function Workspace({ home, subtitle, actions, sections, navKey, tabKey, menuLabel, sideTitle, top, children }) {
  const { t } = useTranslation()
  const location = useLocation()
  const tabs = sections?.filter((s) => s.tab) || []
  const [folded, toggleFolded] = useFolded()
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-surface pt-[env(safe-area-inset-top)]">
        <div className="flex h-14 items-center gap-2 px-4 md:h-16 md:gap-3 md:px-6">
          {/* On a phone the subtitle goes under the name: side by side they don't fit */}
          {/* Phase 15: it may shrink — a long subtitle ("администрирование") is cut, the logo never */}
          <div className="flex min-w-0 shrink flex-col sm:flex-row sm:items-center sm:gap-3">
            <Logo to={home} />
            <span className="-mt-1.5 truncate pl-10 text-xs leading-tight font-medium text-muted sm:mt-0 sm:pl-0 sm:text-sm"><span aria-hidden className="hidden sm:inline">· </span>{subtitle}</span>
          </div>
          <div className="flex-1" />
          {actions}
        </div>
      </header>
      <DemoBanner />

      {sections ? (
        <div className="flex flex-1">
          {/* Phase 12.5: the menu is fixed under the top bar and scrolls apart from the page */}
          <aside data-folded={folded ? '1' : '0'} className={`sticky top-16 hidden h-[calc(100dvh-4rem)] shrink-0 flex-col self-start border-r border-line bg-surface transition-[width] duration-150 md:flex ${folded ? 'w-16' : 'w-60'}`}>
            <nav aria-label={menuLabel} className={`min-h-0 flex-1 overflow-y-auto overscroll-contain ${folded ? 'p-2' : 'p-3'}`}>
              {sideTitle && !folded && <p className="mb-2 truncate px-3 text-xs font-semibold tracking-wide text-faint uppercase" title={sideTitle}>{sideTitle}</p>}
              <ul className="grid gap-0.5">
                {sections.filter((s) => s.side !== false).map((s) => {
                  const { to, key, icon: Icon, end, badge } = s
                  return (
                    <li key={key}>
                      <NavLink to={to} end={end} title={folded ? t(`${navKey}.${key}`) : undefined}
                        className={({ isActive }) => `relative flex min-h-11 items-center gap-2.5 rounded-md text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary ${
                          folded ? 'justify-center px-0' : 'px-3'} ${
                          (s.pages ? sectionActive(s, location) : isActive) ? 'bg-primary-soft text-primary' : 'text-muted hover:bg-surface-2 hover:text-ink'}`}>
                        <Icon className={`shrink-0 ${folded ? 'size-5' : 'size-4'}`} aria-hidden />
                        <span className={folded ? 'sr-only' : 'flex-1'}>{t(`${navKey}.${key}`)}</span>
                        <UnreadBadge count={badge} className={folded ? 'absolute top-0.5 right-0.5' : ''} />
                      </NavLink>
                    </li>
                  )
                })}
              </ul>
            </nav>
            <button type="button" onClick={toggleFolded} aria-expanded={!folded} title={t(folded ? 'nav.menuExpand' : 'nav.menuCollapse')}
              className={`flex min-h-12 shrink-0 items-center gap-2.5 border-t border-line text-sm font-medium text-muted outline-none hover:bg-surface-2 hover:text-ink focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset ${
                folded ? 'justify-center' : 'px-6'}`}>
              {folded ? <PanelLeftOpen className="size-5" aria-hidden /> : <PanelLeftClose className="size-4" aria-hidden />}
              <span className={folded ? 'sr-only' : ''}>{t(folded ? 'nav.menuExpand' : 'nav.menuCollapse')}</span>
            </button>
          </aside>
          {/* Bottom padding on a phone: the content does not hide under the tab bar */}
          {/* Phase 17.1: no width limit — the work area takes all the width beside the menu */}
          <main className="w-full min-w-0 flex-1 px-4 pt-5 pb-24 md:px-8 md:py-8">{top}{children}</main>
          <nav aria-label={menuLabel} className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden">
            {/* Every name is read whole: a tab is never narrower than its name ("Добав…" was cut in an equal grid);
                the spare width is shared, and only a very narrow screen would scroll the bar sideways */}
            <ul className="flex overflow-x-auto overscroll-x-contain [scrollbar-width:none]">
              {tabs.map(({ to, key, icon: Icon, end, badge, pages }) => (
                <li key={key} className="min-w-max flex-1">
                  <NavLink to={to} end={end} className={({ isActive }) => `relative flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 text-[11px] font-medium outline-none focus-visible:bg-surface-2 ${
                    (pages ? sectionActive({ pages }, location) : isActive) ? 'text-primary' : 'text-muted'}`}>
                    <Icon className="size-5 shrink-0" aria-hidden />
                    <UnreadBadge count={badge} className="absolute top-1 left-1/2 ml-1.5" />
                    <span className="whitespace-nowrap">{t(`${tabKey}.${key}`)}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      ) : (
        <main className="w-full flex-1 px-4 py-6 md:py-10">{children}</main>
      )}
    </div>
  )
}

// A page of a group is open: the same path (or below it); a page with "?tab=x" — also that tab
export function pageActive(page, location) {
  const [path, query] = page.to.split('?')
  const here = location.pathname.replace(/\/$/, '')
  if (here !== path && !(page.deep && here.startsWith(`${path}/`))) return false
  if (!query) return true
  const want = new URLSearchParams(query).get('tab')
  return new URLSearchParams(location.search).get('tab') === want
}

// A section with pages is open on any of them (by the path only: "Склад" is open in each of its modes)
export function sectionActive(section, location) {
  return section.pages.some((c) => pageActive({ ...c, to: c.to.split('?')[0] }, location))
}
