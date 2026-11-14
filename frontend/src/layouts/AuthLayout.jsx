import { Outlet } from 'react-router-dom'
import LangSwitch from '../components/LangSwitch'
import Logo from '../components/Logo'

// Phase 16.3: the login and registration pages have one minimal top bar — the logo (to the home page) and languages
export default function AuthLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-bg">
      <header className="border-b border-line bg-surface pt-[env(safe-area-inset-top)]">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-3 px-4 md:px-6">
          <Logo />
          <LangSwitch />
        </div>
      </header>
      <main className="flex w-full flex-1 flex-col px-4 py-6 md:px-6 lg:justify-center lg:py-8">
        <Outlet />
      </main>
    </div>
  )
}
