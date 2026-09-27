#!/usr/bin/env bash
# Sobe a API, o MCP do ARCO e, junto, o túnel da URL fixa. Um Ctrl+C derruba os três.
#
# É o modo de deixar a API e o MCP alcançáveis de fora sem lembrar de subir três coisas em três
# terminais. Sem o token do túnel, API e MCP sobem sozinhos e o script avisa — desenvolver na
# própria máquina não deve depender de ter túnel configurado. Sem o MCP, a API e o túnel seguem:
# o painel depende só da API.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORTA="${PORTA:-8000}"
# A porta do MCP sai da configuração do próprio pacote (`ARCO_MCP_PORTA`, no ambiente ou no
# `.env`), para o script não ter uma segunda regra que um dia diverge da primeira.
MCP_PORTA="$(uv run --directory "$RAIZ" python -c \
  'from arco_agentes.config import Configuracao; print(Configuracao().mcp_porta)')"

# Rodar duas vezes não pode empilhar. Sem esta checagem, o uvicorn morre com "address already
# in use", o `curl /saude` seguinte é respondido pela instância **antiga**, o script conclui que
# subiu e conecta mais um cloudflared — que a Cloudflare aceita como réplica. O resultado é uma
# API a menos e um túnel a mais, sem nenhum erro na tela.
ja_em_pe=()
if curl -fsS --max-time 2 "http://localhost:${PORTA}/saude" >/dev/null 2>&1; then
  ja_em_pe+=("a API, respondendo em http://localhost:${PORTA}/saude")
fi
if curl -fsS --max-time 2 "http://localhost:${MCP_PORTA}/saude" >/dev/null 2>&1; then
  ja_em_pe+=("o MCP, respondendo em http://localhost:${MCP_PORTA}/saude")
fi
tuneis_em_pe() {
  # `pgrep -f` casaria com a própria linha de comando de quem pergunta, e inventaria um túnel
  # que não existe. Aqui a busca é pelo binário, e a linha de comando confirma o token.
  local pid
  for pid in $(pgrep -x cloudflared 2>/dev/null); do
    grep -qa "$(basename "$TOKEN")" "/proc/$pid/cmdline" 2>/dev/null && printf '%s ' "$pid"
  done
  # Sem isto a função devolve o status do último `grep`, e "não achei nenhum túnel" — o caso
  # normal, com só o cloudflared de outro serviço rodando — viraria erro. Com `set -e`, o
  # script morria aí, sem imprimir nada.
  return 0
}
TOKEN="${TUNEL_TOKEN_ARQUIVO:-$HOME/.cloudflared/token-arco}"
pids_tunel="$(tuneis_em_pe)"
if [ -n "${pids_tunel// /}" ]; then
  ja_em_pe+=("o túnel (pid ${pids_tunel% })")
fi
if [ ${#ja_em_pe[@]} -gt 0 ]; then
  echo "Já está em pé:" >&2
  for item in "${ja_em_pe[@]}"; do echo "  - ${item}" >&2; done
  echo >&2
  echo "Nada foi iniciado, para não empilhar processo." >&2
  echo "Se o que está em pé veio de outro terminal, o Ctrl+C lá é o caminho limpo. Senão:" >&2
  echo >&2
  # O pid vai literal de propósito. `pkill -f cloudflared` derrubaria o túnel de qualquer outro
  # serviço nesta máquina junto, e quem roda o comando não tem como saber disso na hora.
  [ -n "${pids_tunel// /}" ] && echo "  kill ${pids_tunel% }" >&2
  echo "  pkill -f 'uvicorn arco_api'" >&2
  echo "  pkill -f 'arco-agentes servir'" >&2
  exit 1
fi

filhos=()
encerrar() {
  for pid in "${filhos[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap encerrar EXIT
trap 'exit 130' INT TERM

uv run --directory "$RAIZ" uvicorn arco_api.main:app --reload --port "$PORTA" &
filhos+=($!)

# O túnel só conecta depois que a API responde: cloudflared que sobe antes fica devolvendo 502
# para quem chamar, o que parece com túnel quebrado e não é.
for _ in $(seq 1 60); do
  # A ordem importa: conferir o processo **antes** do curl. Ao contrário, uma API alheia na
  # mesma porta responderia por esta, e o script seguiria com a sua já morta.
  kill -0 "${filhos[0]}" 2>/dev/null || { echo "A API não subiu." >&2; exit 1; }
  curl -fsS --max-time 2 "http://localhost:${PORTA}/saude" >/dev/null 2>&1 && break
  sleep 0.5
done

# O MCP sobe depois da API, que é quem ele chama, e antes do túnel, que expõe os dois. Ele
# chama a API que este script subiu, na porta dela, e não a do `.env`, se as duas diferirem.
ARCO_API_URL="http://localhost:${PORTA}" uv run --directory "$RAIZ" arco-agentes servir &
pid_mcp=$!
filhos+=("$pid_mcp")
mcp_no_ar=""
for _ in $(seq 1 60); do
  kill -0 "$pid_mcp" 2>/dev/null || break
  if curl -fsS --max-time 2 "http://localhost:${MCP_PORTA}/saude" >/dev/null 2>&1; then
    mcp_no_ar="sim"
    break
  fi
  sleep 0.5
done
if [ -z "$mcp_no_ar" ]; then
  echo "O MCP não subiu em http://localhost:${MCP_PORTA}. A API e o túnel seguem sem ele." >&2
fi

if PORTA="$PORTA" "$RAIZ/infra/tunel-fixo.sh" 2>/tmp/arco-tunel.err; then
  :
else
  echo
  echo "A API está no ar em http://localhost:${PORTA}${mcp_no_ar:+, e o MCP em http://localhost:${MCP_PORTA}/mcp},"
  echo "mas o túnel não subiu:"
  sed 's/^/  /' /tmp/arco-tunel.err >&2
  echo
  wait "${filhos[0]}"
fi
