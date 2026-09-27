#!/usr/bin/env bash
# Expõe a API local na internet por um túnel rápido da Cloudflare, para outra pessoa do time
# testar contra o seu banco. Sem conta e sem domínio: a URL é sorteada a cada execução e morre
# com o Ctrl+C. Detalhes e cuidados em infra/README.md.
set -euo pipefail

PORTA="${PORTA:-8000}"
ALVO="http://localhost:${PORTA}"

if ! command -v cloudflared >/dev/null; then
  echo "cloudflared não está instalado." >&2
  echo "Instalação: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" >&2
  exit 1
fi

if ! curl -fsS --max-time 3 "${ALVO}/saude" >/dev/null; then
  echo "A API não respondeu em ${ALVO}/saude. Suba com \`make api\` em outro terminal." >&2
  exit 1
fi

LOG="$(mktemp)"
encerrar() {
  kill "${TUNEL:-}" 2>/dev/null || true
  rm -f "$LOG"
}
trap encerrar EXIT
trap 'exit 130' INT TERM

# IPv4 por padrão, pelo mesmo motivo de `tunel-fixo.sh`.
cloudflared tunnel --no-autoupdate --edge-ip-version "${TUNNEL_EDGE_IP_VERSION:-4}" \
  --url "$ALVO" >"$LOG" 2>&1 &
TUNEL=$!

URL=""
for _ in $(seq 1 60); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  kill -0 "$TUNEL" 2>/dev/null || break
  sleep 0.5
done

if [ -z "$URL" ]; then
  echo "O túnel não subiu. Saída do cloudflared:" >&2
  cat "$LOG" >&2
  exit 1
fi

# O endereço leva alguns segundos para propagar.
for _ in $(seq 1 30); do
  curl -fsS --max-time 5 "${URL}/saude" >/dev/null 2>&1 && break
  sleep 1
done

cat <<FIM

  API do ARCO na internet, enquanto este terminal ficar aberto:

    ${URL}
    ${URL}/docs           documentação interativa
    ${URL}/openapi.json   contrato

  Para o front de outra máquina usar esta API, o proxy do Vite aponta para a URL
  acima no lugar de http://localhost:8000. O passo a passo está em infra/README.md.

  Sem autenticação: quem tiver a URL lê e grava simulações neste banco.
  Ctrl+C derruba o túnel, e a URL deixa de existir.

FIM

wait "$TUNEL"
