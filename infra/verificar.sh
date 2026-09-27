#!/usr/bin/env bash
# Confere o que `make servidor` precisa antes de subir qualquer coisa, e diz o que falta.
#
# Obrigatório trava: sem ele a API ou o MCP não sobem, ou sobem sem servir o produto. Opcional só
# avisa: o túnel e o painel não são do `make servidor`. Sai 1 se faltar algo obrigatório.
#
# Aqui ficam as ferramentas da máquina. O que depende do código do ARCO (banco, esquema,
# snapshot, chave do modelo e portas) é conferido em Python, em `arco_api.verificar`, com a
# mesma configuração que a API usa.
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORTA="${PORTA:-8000}"
# O .env da raiz, pelo mesmo caminho de `tunel-fixo.sh`: é de lá que vem TUNEL_TOKEN_ARQUIVO.
[ -f "$RAIZ/.env" ] && set -a && . "$RAIZ/.env" && set +a

faltou=""
linha() { printf '  %-6s %s\n' "$1" "$2"; }
dica() { printf '         → %s\n' "$1"; }
falta() {
  linha falta "$1"
  dica "$2"
  faltou="sim"
}

echo "Conferindo o que o make servidor precisa."
echo
echo "Obrigatório:"

if command -v uv >/dev/null 2>&1; then
  linha ok "$(uv --version)"
else
  falta "uv não encontrado" "instale: https://docs.astral.sh/uv/getting-started/installation/"
fi

if command -v curl >/dev/null 2>&1; then
  linha ok "curl"
else
  falta "curl não encontrado" "instale pelo gerenciador de pacotes do sistema"
fi

if ! command -v docker >/dev/null 2>&1; then
  falta "Docker não encontrado" "instale o Docker com Compose: https://docs.docker.com/get-docker/"
elif ! erro_docker="$(docker info 2>&1 >/dev/null)"; then
  if grep -qi "permission denied" <<<"$erro_docker"; then
    falta "Docker sem permissão para este usuário" \
      "sudo usermod -aG docker \$USER e abra um terminal novo"
  else
    falta "Docker instalado, mas o serviço não responde" \
      "inicie o Docker (Docker Desktop, ou sudo systemctl start docker)"
  fi
elif ! docker compose version >/dev/null 2>&1; then
  falta "Docker sem o Compose" "instale o plugin: https://docs.docker.com/compose/install/"
else
  linha ok "Docker com Compose, no ar"
fi

if command -v uv >/dev/null 2>&1; then
  # A porta do MCP sai da configuração do próprio pacote, como em `servidor.sh`. É também a
  # primeira vez que o ambiente Python é montado: se falhar aqui, o resto não tem como rodar.
  if MCP_PORTA="$(uv run --quiet --directory "$RAIZ" python -c \
    'from arco_agentes.config import Configuracao; print(Configuracao().mcp_porta)' 2>/dev/null)"; then
    uv run --quiet --directory "$RAIZ" python -m arco_api.verificar \
      --porta-api "$PORTA" --porta-mcp "$MCP_PORTA" || faltou="sim"
  else
    falta "O ambiente Python do projeto não montou" "rode make instalar e veja o erro"
  fi
else
  linha "—" "Banco, esquema, snapshot, chave e portas ficam sem conferir: precisam do uv"
fi

echo
echo "Opcional (só avisa):"

TOKEN="${TUNEL_TOKEN_ARQUIVO:-$HOME/.cloudflared/token-arco}"
if ! command -v cloudflared >/dev/null 2>&1; then
  linha aviso "cloudflared não encontrado: sem túnel, API e MCP ficam só nesta máquina"
elif [ ! -f "$TOKEN" ]; then
  linha aviso "Sem o token do túnel em $TOKEN: API e MCP ficam só nesta máquina"
else
  linha ok "Túnel: cloudflared e token"
fi

if ! command -v pnpm >/dev/null 2>&1 || ! command -v node >/dev/null 2>&1; then
  linha aviso "Node ou pnpm não encontrado: o painel (make web) não sobe"
elif [ ! -d "$RAIZ/web/node_modules" ]; then
  linha aviso "Dependências do painel não instaladas: rode make instalar antes de make web"
else
  linha ok "Painel: $(node --version) e pnpm $(pnpm --version)"
fi

echo
if [ -n "$faltou" ]; then
  echo "Falta o que está marcado acima. Nada foi iniciado." >&2
  exit 1
fi
echo "Tudo pronto."
