import { SearchX } from 'lucide-react'
import { Link } from 'react-router'

type NotFoundProps = {
  /** O que não foi encontrado, para a frase da página. */
  message?: string
}

/** Página inexistente, dentro do layout do produto (cabeçalho e fundo). */
export function NotFound({
  message = 'Esta página não existe ou mudou de endereço.',
}: NotFoundProps) {
  return (
    <div className="sim-page flex items-center justify-center px-4 py-16 sm:px-6">
      <section className="sim-card flex w-full max-w-lg flex-col items-center px-6 py-12 text-center sm:px-10">
        <span
          className="grid size-12 place-items-center rounded-lg bg-(--sim-sky-soft) text-(--sim-brand)"
          aria-hidden="true"
        >
          <SearchX className="size-6" />
        </span>
        <p className="sim-eyebrow mt-5 text-(--sim-brand)">Erro 404</p>
        <h1 className="sim-display mt-2 text-2xl font-semibold text-(--sim-brand-ink) sm:text-3xl">
          Página não encontrada
        </h1>
        <p className="mt-2 max-w-sm text-sm leading-6 text-(--sim-muted-foreground)">{message}</p>
        <div className="mt-7 flex flex-wrap justify-center gap-2">
          <Link to="/" className="sim-btn-primary">
            Voltar para o início
          </Link>
          <Link to="/simulacoes" className="sim-btn-secondary">
            Ver simulações
          </Link>
        </div>
      </section>
    </div>
  )
}
