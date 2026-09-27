import './route-loading.css'

export function RouteLoading() {
  return (
    <div
      role="status"
      aria-label="Carregando"
      className="route-loading fixed inset-0 z-50 flex flex-col items-center justify-center gap-18 bg-(--rl-bg)"
    >
      <div className="flex flex-col items-center gap-0">
        <h1 className="route-loading-word">ARCO</h1>
        <p
          className="mt-1 text-center text-lg font-light text-(--rl-text2) sm:text-2xl"
          style={{ fontFamily: "'Exo 2', 'Outfit', sans-serif" }}
        >
          Análise Retrospectiva do Corte
        </p>
      </div>

      <div>
        <div className="route-loading-bar" role="progressbar" aria-label="Carregando">
          <span />
        </div>
        <p className="mt-3.5 text-center text-sm text-(--rl-muted)">
          Carregando o histórico do ONS
        </p>
      </div>
    </div>
  )
}
