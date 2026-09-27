import { Fragment } from 'react'
import { Link } from 'react-router'
import { cn } from '@/utils/cn'

export type Crumb = {
  label: string
  /** Sem destino, o item é texto: a página atual, ou um nível que ainda não carregou. */
  to?: string
}

const SHORT_LABEL = 20

type BreadcrumbsProps = {
  items: Crumb[]
  className?: string
}

/**
 * A trilha de navegação do topo das telas: do nível mais alto até a página atual, a última. Numa
 * linha só: os nomes longos encurtam com reticências (o nome inteiro fica no `title`).
 */
export function Breadcrumbs({ items, className }: BreadcrumbsProps) {
  return (
    <nav aria-label="Trilha de navegação" className={className}>
      <ol className="flex min-w-0 items-center gap-x-1.5 whitespace-nowrap text-xs font-semibold text-(--sim-muted-foreground)">
        {items.map((item, index) => {
          const last = index === items.length - 1
          // Só nome longo encurta; os níveis curtos ("Simulações", "Relatório 3") ficam inteiros.
          const long = item.label.length > SHORT_LABEL
          return (
            <Fragment key={`${index}-${item.label}`}>
              <li
                className={cn(
                  long ? 'min-w-0 max-w-[24rem] truncate' : 'shrink-0',
                  long && (last ? 'shrink' : 'shrink-[3]'),
                )}
                title={item.label}
              >
                {item.to && !last ? (
                  <Link to={item.to} className="transition-colors hover:text-(--sim-brand)">
                    {item.label}
                  </Link>
                ) : (
                  <span
                    aria-current={last ? 'page' : undefined}
                    className={cn(last && 'text-(--sim-brand-ink)')}
                  >
                    {item.label}
                  </span>
                )}
              </li>
              {!last && (
                <li aria-hidden="true" className="shrink-0 select-none">
                  /
                </li>
              )}
            </Fragment>
          )
        })}
      </ol>
    </nav>
  )
}
