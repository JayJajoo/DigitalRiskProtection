import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { getHealth, type HealthResponse } from '@/lib/api'
import { cn } from '@/lib/utils'

export default function Layout() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setError(true))
  }, [])

  const navClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      'px-3 py-2 rounded-md text-sm font-medium transition-colors',
      isActive
        ? 'bg-primary text-primary-foreground'
        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
    )

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="mx-auto flex h-16 w-full items-center justify-between px-8">
          <Link to="/" className="flex items-center gap-2 font-semibold">
            <ShieldCheck className="h-5 w-5 text-primary" />
            DRP <span className="font-normal text-muted-foreground">Digital Risk Protection</span>
          </Link>
          <nav className="flex items-center gap-2">
            <NavLink to="/part1" className={navClass}>
              Part 1 · Ingestion
            </NavLink>
            <NavLink to="/part2" className={navClass}>
              Part 2 · Pipeline
            </NavLink>
            <NavLink to="/metrics" className={navClass}>
              Metrics
            </NavLink>
          </nav>
          <div className="flex items-center gap-2 text-xs">
            <span
              className={cn(
                'h-2 w-2 rounded-full',
                error ? 'bg-destructive' : health ? 'bg-green-500' : 'bg-yellow-400',
              )}
            />
            <span className="text-muted-foreground">
              {error ? 'API offline' : health ? `API v${health.version}` : 'connecting…'}
            </span>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full px-8 py-8">
        <Outlet />
      </main>
    </div>
  )
}
