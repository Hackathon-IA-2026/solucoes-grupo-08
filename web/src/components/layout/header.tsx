import { Database, Menu } from 'lucide-react'
import { Link, useLocation } from 'react-router'
import { useSnapshot } from '@/features/snapshot/api/get-snapshot'
import { Button } from '@/components/ui/button'
import { Sheet, SheetClose, SheetContent, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { InfoTooltip } from '@/components/ui/tooltip'
import { cn } from '@/utils/cn'
import './route-loading.css'
import { formatPeriod, formatSnapshotId } from '@/utils/format'

type NavItem = {
  label: string
  href: string
  available: boolean
}

const navItems: NavItem[] = [
  { label: 'Restrições', href: '/', available: true },
  { label: 'Simulações', href: '/simulacoes', available: true },
]

const navLinkClass =
  'rounded-md px-3 py-2 text-sm font-semibold text-(--sim-muted-foreground) transition-colors hover:bg-(--sim-muted) hover:text-(--sim-brand-ink)'
const navLinkActiveClass =
  'bg-(--sim-sky-soft)/50 text-(--sim-brand) hover:bg-(--sim-sky-soft)/50 hover:text-(--sim-brand)'

/** A marca: a palavra ARCO com o gradiente da tela de carregamento. */
function Brand() {
  return (
    <Link
      to="/"
      aria-label="ARCO, início"
      className="rounded-sm transition-opacity hover:opacity-80 focus-visible:ring-2 focus-visible:ring-focus focus-visible:outline-none"
    >
      <span className="arco-wordmark block text-2xl" aria-hidden="true">
        ARCO
      </span>
    </Link>
  )
}

export function Header() {
  const { data: snapshot, isPending, isError } = useSnapshot()
  const { pathname } = useLocation()
  // Ativo pela rota, e não pelo className em função do NavLink: o Slot do SheetClose o descarta.
  // Restrições fica ativa também no detalhe e na nova simulação, que moram em /restricoes.
  const isActive = (href: string) =>
    href === '/'
      ? pathname === '/' || pathname.startsWith('/restricoes')
      : pathname.startsWith(href)

  const snapshotInfo = isPending ? (
    <span>carregando…</span>
  ) : isError ? (
    <span className="text-warning">snapshot indisponível</span>
  ) : (
    <span className="flex items-center gap-1.5">
      {formatPeriod(snapshot.periodo_inicio, snapshot.periodo_fim)}
      <InfoTooltip label={`Ajuda: snapshot ${formatSnapshotId(snapshot.id)}`}>
        Cópia datada e imutável do dado aberto do ONS; nenhum cálculo lê o dado ao vivo. Snapshot{' '}
        {formatSnapshotId(snapshot.id)}.
      </InfoTooltip>
    </span>
  )

  return (
    <header className="sim-tokens h-16 shrink-0 border-b border-(--sim-border) bg-(--sim-surface)">
      <div className="mx-auto flex h-full max-w-screen-2xl items-center justify-between gap-6 md:justify-start px-4 sm:px-6 lg:px-8">
        {/* Abaixo de md: hambúrguer primeiro, abrindo a sidebar colapsada com a navegação e o
          snapshot dentro. Acima de md: some, e os links ficam lado a lado no próprio cabeçalho. */}
        <Sheet>
          <SheetTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="md:hidden"
              aria-label="Abrir menu"
            >
              <Menu aria-hidden="true" />
            </Button>
          </SheetTrigger>
          <SheetContent className="sim-tokens">
            <SheetTitle className="px-4 pb-4 pt-5">
              <Brand />
            </SheetTitle>
            <nav aria-label="Navegação principal" className="flex flex-col gap-1 px-2">
              {navItems.map((item) =>
                item.available ? (
                  <SheetClose key={item.href} asChild>
                    <Link
                      to={item.href}
                      aria-current={isActive(item.href) ? 'page' : undefined}
                      className={cn(navLinkClass, isActive(item.href) && navLinkActiveClass)}
                    >
                      {item.label}
                    </Link>
                  </SheetClose>
                ) : (
                  <span
                    key={item.href}
                    title="Ainda não implementado"
                    className="cursor-not-allowed rounded-md px-3 py-2 text-sm font-medium text-text-muted"
                  >
                    {item.label}
                  </span>
                ),
              )}
            </nav>
            <div className="mt-auto flex flex-col gap-1 border-t border-(--sim-border) px-4 py-3 text-xs text-(--sim-muted-foreground)">
              <span className="sim-eyebrow">Dados do ONS</span>
              <span className="font-semibold text-(--sim-brand-ink)">{snapshotInfo}</span>
            </div>
          </SheetContent>
        </Sheet>

        <Brand />

        {/* Acima de md: links lado a lado. Abaixo: some, e o hambúrguer assume a navegação. */}
        <nav aria-label="Navegação principal" className="hidden items-center gap-1 md:flex">
          {navItems.map((item) =>
            item.available ? (
              <Link
                key={item.href}
                to={item.href}
                aria-current={isActive(item.href) ? 'page' : undefined}
                className={cn(navLinkClass, isActive(item.href) && navLinkActiveClass)}
              >
                {' '}
                {item.label}{' '}
              </Link>
            ) : (
              <span
                key={item.href}
                title="Ainda não implementado"
                className="cursor-not-allowed rounded-md px-3 py-2 text-sm font-medium text-text-muted"
              >
                {item.label}
              </span>
            ),
          )}
        </nav>

        <div className="ml-auto hidden items-center gap-2 rounded-full border border-(--sim-border) bg-(--sim-background) px-3 py-1.5 text-xs text-(--sim-muted-foreground) md:flex">
          <Database className="size-3.5 text-(--sim-brand)" aria-hidden="true" />
          <span>Dados do ONS</span>
          <span aria-hidden="true">·</span>
          <span className="font-semibold text-(--sim-brand-ink)">{snapshotInfo}</span>
        </div>
      </div>
    </header>
  )
}
