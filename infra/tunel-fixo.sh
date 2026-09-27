#!/usr/bin/env bash
# Expõe a API local numa URL **fixa**, por um túnel nomeado da Cloudflare.
#
# Diferente de `tunel.sh`, que sorteia um endereço `trycloudflare.com` e morre com o terminal,
# aqui o endereço é um subdomínio seu e não muda. O túnel é criado e roteado no painel da
# Cloudflare; desta máquina sai só o processo que o conecta, com o token. O passo a passo do
# painel está em infra/README.md.
#
# Não é deploy. A API continua sem autenticação, então quem tiver a URL lê e grava
# neste banco. Fechar é com Cloudflare Access, no mesmo painel.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$RAIZ/.env" ] && set -a && . "$RAIZ/.env" && set +a

PORTA="${PORTA:-8000}"
ALVO="http://localhost:${PORTA}"
TOKEN="${TUNEL_TOKEN_ARQUIVO:-$HOME/.cloudflared/token-arco}"

if ! command -v cloudflared >/dev/null; then
  echo "cloudflared não está instalado: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" >&2
  exit 1
fi

if [ ! -f "$TOKEN" ]; then
  cat >&2 <<FIM
Não achei o token do túnel em ${TOKEN}.

O túnel nomeado é criado no painel da Cloudflare, que devolve um token. Grave-o assim:

  install -m 600 /dev/stdin "$TOKEN" <<< 'COLE_O_TOKEN_AQUI'

Outro caminho de arquivo: defina TUNEL_TOKEN_ARQUIVO no .env.
O passo a passo do painel está em infra/README.md.
FIM
  exit 1
fi

# Dois cloudflared com o mesmo token não dão erro: a Cloudflare os aceita como réplicas e
# reparte as chamadas. Empilha em silêncio, e o segundo não avisa nada.
for pid in $(pgrep -x cloudflared 2>/dev/null); do
  if grep -qa "$(basename "$TOKEN")" "/proc/$pid/cmdline" 2>/dev/null; then
    echo "O túnel já está em pé, no pid ${pid}. Nada foi iniciado." >&2
    echo "Derrube com \`kill ${pid}\`, ou Ctrl+C no terminal que o subiu." >&2
    exit 1
  fi
done

if ! curl -fsS --max-time 3 "${ALVO}/saude" >/dev/null; then
  echo "A API não respondeu em ${ALVO}/saude. Suba com \`make api\`, ou use \`make servidor\`," >&2
  echo "que sobe a API e o túnel juntos." >&2
  exit 1
fi

echo "Túnel fixo no ar, ligando ${PUBLICO:-o hostname do painel} a ${ALVO}. Ctrl+C derruba."
# IPv4 por padrão. Com `auto`, o padrão do cloudflared, numa máquina sem rota IPv6 confiável até
# a Cloudflare, parte das conexões do túnel cai com "network is unreachable" e fica
# reconectando, e quem chama nesse meio-tempo recebe 502. Quem tem IPv6 de verdade pode pôr
# `TUNNEL_EDGE_IP_VERSION=auto` no ambiente.
exec cloudflared tunnel --no-autoupdate --edge-ip-version "${TUNNEL_EDGE_IP_VERSION:-4}" \
  run --token-file "$TOKEN"
