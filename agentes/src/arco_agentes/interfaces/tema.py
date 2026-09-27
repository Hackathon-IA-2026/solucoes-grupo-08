"""O tema dos cartões, o mesmo das telas do painel.

As telas desenham com a paleta `.sim-tokens` de `web/src/styles/simulation-result.css` (fundo
cinza-azulado, superfície branca, azul da marca, tinta azul-escura, Sora), e é ela que vem aqui,
com os mesmos nomes. Os tons de estado (aviso, sucesso, perigo) são os do `@theme` de
`web/src/app/app.css`, que a paleta não redefine. Os tokens `--v-*` de
`web/src/styles/cojeev/tokens.css` não aparecem nas telas e não entram.

Cada regra de `CSS` copia a classe do painel que faz o mesmo papel (`.sim-eyebrow`,
`.sim-metric-label`, `.sim-list-table th`, os botões e o `Badge` de `components/ui/`), aplicada
aos ganchos `pf-*` dos componentes da Prefab dentro de `.arco-cartao`.

A logo no alto de cada cartão é a do preloader do painel (`web/src/components/layout/
route-loading.tsx`): "ARCO" em Orbitron 700 (SIL Open Font License), com o espaçamento de
`route-loading.css`. Em `logo.svg`, as letras já são contornos, para a logo não depender de a
fonte carregar no chat; e o degradê é estático, um quadro do que corre no preloader: o verde e o
azul-escuro dele (`--rl-g4`, `--rl-g1`) e, no fim, o começo do azul-claro (`--rl-g2`).
"""

from __future__ import annotations

from pathlib import Path

from fastmcp.apps import PrefabAppConfig, ResourceCSP
from prefab_ui.components import Column, Svg, Text
from prefab_ui.themes.base import Theme

SIM = {
    "radius": "0.5rem",
    "background": "oklch(0.977 0.008 255)",
    "surface": "oklch(1 0 0)",
    "foreground": "oklch(0.235 0.035 260)",
    "muted": "oklch(0.968 0.007 247.896)",
    "muted-foreground": "oklch(0.53 0.025 255)",
    "border": "oklch(0.929 0.013 255.508)",
    "ring": "oklch(0.58 0.18 259)",
    "brand": "oklch(0.49 0.22 262)",
    "brand-deep": "oklch(0.34 0.15 264)",
    "brand-ink": "oklch(0.25 0.105 265)",
    "brand-foreground": "oklch(0.985 0.004 255)",
    "sky-soft": "oklch(0.91 0.055 254)",
    "alert": "oklch(0.62 0.14 55)",
    "alert-soft": "oklch(0.975 0.02 75)",
}
"""`.sim-tokens`, de `web/src/styles/simulation-result.css`."""

ESTADOS = {
    "primary-light": "color-mix(in oklab, var(--sim-sky-soft) 55%, var(--sim-surface))",
    "warning": "#c65d12",
    "warning-light": "#fff0e6",
    "success": "#16803c",
    "success-light": "#e3f6e9",
    "danger": "#e7000b",
    "danger-light": "#fdebeb",
}
"""Os tons de estado do `Badge` do painel: `@theme` de `app.css`, e `primary-light` da paleta."""

VARIAVEIS = (
    " ".join(f"--sim-{nome}: {valor};" for nome, valor in SIM.items())
    + " "
    + " ".join(f"--arco-{nome}: {valor};" for nome, valor in ESTADOS.items())
    + " --background: var(--sim-background); --foreground: var(--sim-foreground);"
    " --card: var(--sim-surface); --card-foreground: var(--sim-foreground);"
    " --popover: var(--sim-surface); --popover-foreground: var(--sim-foreground);"
    " --primary: var(--sim-brand); --primary-foreground: var(--sim-brand-foreground);"
    " --secondary: var(--sim-muted); --secondary-foreground: var(--sim-brand-ink);"
    " --muted: var(--sim-muted); --muted-foreground: var(--sim-muted-foreground);"
    " --accent: var(--sim-muted); --accent-foreground: var(--sim-brand-ink);"
    " --border: var(--sim-border); --input: var(--sim-border); --ring: var(--sim-ring);"
    " --radius: var(--sim-radius);"
)
"""A paleta e o mapeamento para as variáveis da Prefab, como `.sim-tokens` faz com as do
Tailwind."""

CSS = """
.arco-cartao { background: var(--sim-surface); border: 1px solid var(--sim-border);
  border-radius: var(--sim-radius); padding: 1rem 1.25rem; color: var(--sim-foreground);
  font-size: 0.8125rem; }
.arco-logo { line-height: 0; }
.arco-logo svg { height: 18px; width: auto; display: block; }
.arco-titulo { color: var(--sim-brand-ink); font-size: 1rem; font-weight: 600; }
.arco-subtitulo, .arco-nota { color: var(--sim-muted-foreground); font-size: 0.75rem;
  line-height: 1.25rem; }
.arco-rotulo, .arco-cartao .pf-label { color: var(--sim-muted-foreground); font-size: 0.68rem;
  font-weight: 800; text-transform: uppercase; letter-spacing: 0.06em; }
.arco-valor { color: var(--sim-brand-ink); font-size: 1.5rem; font-weight: 600; }
.arco-destaque { color: var(--sim-brand-ink); font-weight: 700; }

.arco-cartao .pf-table-head { color: var(--sim-muted-foreground); font-size: 0.68rem;
  font-weight: 800; text-transform: uppercase; letter-spacing: 0.06em; padding: 0.75rem;
  height: auto; }
.arco-cartao .pf-table-cell { color: var(--sim-foreground); font-size: 0.75rem;
  padding: 0.85rem 0.75rem; }
.arco-cartao .pf-table-row { border-color: var(--sim-border); }
.arco-cartao .pf-table-body .pf-table-row:hover { background: var(--sim-muted); }

.arco-cartao .pf-button { border-radius: 0.375rem; font-size: 0.8rem; font-weight: 700;
  height: 2.25rem; padding: 0 1rem; box-shadow: none; }
.arco-cartao .pf-button-size-sm { height: 2rem; padding: 0 0.8rem; }
.arco-cartao .pf-button-variant-default { background: var(--sim-brand);
  color: var(--sim-brand-foreground); }
.arco-cartao .pf-button-variant-default:hover { background: var(--sim-brand-deep); }
.arco-cartao .pf-button-variant-outline { background: var(--sim-surface);
  border: 1px solid var(--sim-border); color: var(--sim-brand-ink); }
.arco-cartao .pf-button-variant-outline:hover { background: var(--sim-muted); }

.arco-cartao .pf-input, .arco-cartao .pf-select-trigger { background: var(--sim-background);
  border: 1px solid var(--sim-border); border-radius: 0.375rem; height: 2.5rem;
  font-size: 0.8125rem; color: var(--sim-brand-ink); box-shadow: none; }

.arco-cartao .pf-badge { border-radius: 0.375rem; border: 1px solid transparent;
  padding: 0.125rem 0.5rem; font-size: 0.75rem; font-weight: 500; }
.arco-cartao .pf-badge-variant-default { background: var(--arco-primary-light);
  color: var(--sim-brand); }
.arco-cartao .pf-badge-variant-warning { background: var(--arco-warning-light);
  color: var(--arco-warning); }
.arco-cartao .pf-badge-variant-success { background: var(--arco-success-light);
  color: var(--arco-success); }
.arco-cartao .pf-badge-variant-destructive { background: var(--arco-danger-light);
  color: var(--arco-danger); }
.arco-cartao .pf-badge-variant-outline { background: var(--sim-surface);
  border-color: var(--sim-border); color: var(--sim-foreground); }

.arco-cartao .pf-alert-variant-warning { background: var(--sim-alert-soft);
  border: 1px solid var(--sim-alert); border-radius: var(--sim-radius); }
.arco-cartao .pf-alert-variant-warning svg { color: var(--sim-alert); }
.arco-cartao .pf-alert-variant-warning .pf-alert-description {
  color: var(--sim-muted-foreground); font-size: 0.75rem; line-height: 1.25rem; }

.arco-cartao .pf-separator { background: var(--sim-border); }
.arco-cartao .pf-progress-track { background: var(--sim-muted); border-radius: 999px; }

.arco-barra-rodando { position: relative; height: 0.5rem; overflow: hidden;
  border-radius: 999px; background: var(--sim-muted); }
.arco-barra-rodando-faixa { position: absolute; top: 0; bottom: 0; width: 35%;
  border-radius: 999px; background: var(--sim-brand);
  animation: arco-vaivem 1.4s ease-in-out infinite; }
@keyframes arco-vaivem { 0% { left: -35%; } 100% { left: 100%; } }
@media (prefers-reduced-motion: reduce) {
  .arco-barra-rodando-faixa { animation: none; left: 0; width: 100%; opacity: 0.35; }
}

.arco-agentes { background: var(--sim-background); border: 1px solid var(--sim-border);
  border-radius: var(--sim-radius); padding: 1rem 1.25rem; }
.arco-agentes-titulo { color: var(--sim-brand-ink); font-size: 0.875rem; font-weight: 600; }
.arco-passo { color: var(--sim-foreground); font-size: 0.75rem; line-height: 1.25rem; }
.arco-desenho svg { width: 100%; height: auto; display: block; }
.arco-desenho text { font-family: 'Sora', sans-serif; font-size: 11px;
  fill: var(--sim-muted-foreground); }
.arco-no { fill: var(--sim-surface); stroke: var(--sim-brand); stroke-width: 2; }
.arco-agente { fill: var(--sim-brand); }
.arco-agente-olho { fill: var(--sim-brand-foreground); }
.arco-fio { stroke: var(--sim-sky-soft); stroke-width: 2; fill: none; stroke-dasharray: 4 4;
  animation: arco-fluxo 0.8s linear infinite; }
.arco-volta { stroke: var(--sim-brand); stroke-width: 1.5; fill: none; stroke-dasharray: 3 4;
  opacity: 0.6; animation: arco-fluxo 1.2s linear infinite reverse; }
.arco-variacao { fill: var(--sim-brand); transform-box: fill-box; transform-origin: center;
  animation: arco-surge 6s ease-in-out infinite; }
.arco-relatorio { fill: var(--sim-surface); stroke: var(--sim-brand-ink); stroke-width: 2;
  animation: arco-fim 6s ease-in-out infinite; }
.arco-pulso { transform-box: fill-box; transform-origin: center;
  animation: arco-pulso 1.6s ease-in-out infinite; }
@keyframes arco-fluxo { from { stroke-dashoffset: 16; } to { stroke-dashoffset: 0; } }
@keyframes arco-surge { 0%, 8% { opacity: 0.12; transform: scale(0.5); }
  18%, 78% { opacity: 1; transform: scale(1); }
  92%, 100% { opacity: 0.12; transform: scale(0.5); } }
@keyframes arco-fim { 0%, 70% { opacity: 0.25; } 80%, 92% { opacity: 1; } 100% { opacity: 0.25; } }
@keyframes arco-pulso { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.08); } }
@media (prefers-reduced-motion: reduce) {
  .arco-desenho * { animation: none !important; opacity: 1 !important; transform: none !important; }
}
"""

TEMA = Theme(mode="light", font="Sora", light_css=VARIAVEIS, css=CSS, gradient=False)

APP = PrefabAppConfig(
    csp=ResourceCSP(resource_domains=["https://fonts.googleapis.com", "https://fonts.gstatic.com"])
)
"""O renderizador da Prefab, mais as fontes do Google, que a política do app bloquearia."""


LOGO = (Path(__file__).parent / "logo.svg").read_text(encoding="utf-8")
"""A logo do preloader do painel, em contornos."""


def cabecalho(titulo: str, subtitulo: str | None = None) -> Column:
    """O alto de todo cartão: a logo do ARCO, título e linha de apoio."""
    with Column(gap=1) as bloco:
        Svg(content=LOGO, css_class="arco-logo mb-1")
        Text(titulo, css_class="arco-titulo")
        if subtitulo:
            Text(subtitulo, css_class="arco-subtitulo")
    return bloco


def indicador(rotulo: str, valor: str) -> Column:
    """Rótulo e número, como `.sim-metric-label` e `.sim-metric-value`."""
    with Column(gap=1) as bloco:
        Text(rotulo, css_class="arco-rotulo")
        Text(valor, css_class="arco-valor")
    return bloco
