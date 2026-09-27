import { Suspense } from 'react'
import { Outlet } from 'react-router'
import { Header } from '@/components/layout/header'
import { RouteLoading } from '@/components/layout/route-loading'

export default function Layout() {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="relative min-w-0 flex-1">
        <Suspense fallback={<RouteLoading />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  )
}
