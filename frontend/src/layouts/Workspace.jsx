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
//               Phase 12.4: a section may be a group with `children` [{ to, key, badge }] — a heading with its
//               pages on the left on a computer, one tab of the phone bar (active on any of its pages).
//   top       — a line under the top bar (the seller's "Я сейчас в: …")
export default function Workspace({ home, subtitle, actions, sections, navKey, tabKey, menuLabel, sideTitle, top, children }) {
  const { t } = useTranslation()
  const location = useLocation()
  const tabs = sections?.filter((s) => s.tab) || []
  const groupActive = (s) => s.children?.some((c) => pageActive(c, location))
  return (
    <div className="flex min-h-screen flex-col">
      <DemoBanner />
      <header className="sticky top-0 z-30 border-b border-line bg-surface">
        <div className="flex h-14 items-center gap-2 px-4 md:h-16 md:gap-3 md:px-6">
          {/* On a phone the subtitle goes under the name: side by side they don't fit */}
          <div className="flex min-w-0 flex-col sm:flex-row sm:items-center sm:gap-3">
            <Logo to={home} />
            <span className="-mt-1.5 truncate pl-10 text-xs leading-tight font-medium text-muted sm:mt-0 sm:pl-0 sm:text-sm"><span aria-hidden className="hidden sm:inline">· </span>{subtitle}</span>
          </div>
          <div className="flex-1" />
          {actions}
        </div>
      </header>

      {sections ? (
        <div className="flex flex-1">
          <aside className="hidden w-60 shrink-0 border-r border-line bg-surface md:block">
            <nav aria-label={menuLabel} className="sticky top-16 p-3">
              {sideTitle && <p className="mb-2 truncate px-3 text-xs font-semibold tracking-wide text-faint uppercase" title={sideTitle}>{sideTitle}</p>}
              <ul className="grid gap-0.5">
                {sections.map(({ to, key, icon: Icon, end, badge, children: pages }) => (
                  <li key={key}>
                    {pages ? (
                      <>
                        <p className={`flex min-h-10 items-center gap-2.5 px-3 pt-2 text-xs font-semibold tracking-wide uppercase ${groupActive({ children: pages }) ? 'text-primary' : 'text-faint'}`}>
                          <Icon className="size-4 shrink-0" aria-hidden /><span className="flex-1">{t(`${navKey}.${key}`)}</span>
                        </p>
                        <ul className="grid gap-0.5">
                          {pages.map((c) => {
                            const active = pageActive(c, location)
                            return (
                              <li key={c.key}>
                                <NavLink to={c.to} aria-current={active ? 'page' : undefined} className={`flex min-h-10 items-center gap-2 rounded-md py-1 pr-3 pl-9 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary ${
                                  active ? 'bg-primary-soft text-primary' : 'text-muted hover:bg-surface-2 hover:text-ink'}`}>
                                  <span className="flex-1">{t(`${navKey}.${c.key}`)}</span><UnreadBadge count={c.badge} />
                                </NavLink>
                              </li>
                            )
                          })}
                        </ul>
                      </>
                    ) : (
                      <NavLink to={to} end={end} className={({ isActive }) => `flex min-h-11 items-center gap-2.5 rounded-md px-3 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary ${
                        isActive ? 'bg-primary-soft text-primary' : 'text-muted hover:bg-surface-2 hover:text-ink'}`}>
                        <Icon className="size-4 shrink-0" aria-hidden /><span className="flex-1">{t(`${navKey}.${key}`)}</span>
                        <UnreadBadge count={badge} />
                      </NavLink>
                    )}
                  </li>
                ))}
              </ul>
            </nav>
          </aside>
          {/* Bottom padding on a phone: the content does not hide under the tab bar */}
          <main className="mx-auto w-full max-w-6xl min-w-0 flex-1 px-4 pt-5 pb-24 md:px-8 md:py-8">{top}{children}</main>
          <nav aria-label={menuLabel} className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden">
            {/* Every name is read whole: a tab is never narrower than its name ("Добав…" was cut in an equal grid);
                the spare width is shared, and only a very narrow screen would scroll the bar sideways */}
            <ul className="flex overflow-x-auto overscroll-x-contain [scrollbar-width:none]">
              {tabs.map(({ to, key, icon: Icon, end, badge, children: pages }) => (
                <li key={key} className="min-w-max flex-1">
                  <NavLink to={to} end={end} className={({ isActive }) => `relative flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 text-[11px] font-medium outline-none focus-visible:bg-surface-2 ${
                    (pages ? groupActive({ children: pages }) : isActive) ? 'text-primary' : 'text-muted'}`}>
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
