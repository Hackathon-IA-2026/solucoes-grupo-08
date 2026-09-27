# infra

Docker Compose com o Postgres 18 usado pela API e pela base derivada.

- `make db` sobe e espera o healthcheck. `make db-parar` derruba.
- Credenciais de desenvolvimento: usuário `arco`, senha `arco`, banco `arco`, porta 5432. A URL correspondente está em `.env.exemplo`.
- **Porta ocupada:** se outro Postgres já usa a 5432, defina `ARCO_PG_PORTA` no `.env` e use a mesma porta em `DATABASE_URL`. O `make db` lê o `.env` da raiz. Não crie container à mão: o do projeto é o `arco-postgres`, no projeto `arco` do Compose, com o volume `arco-pgdata`. Os três nomes são fixos no `docker-compose.yml`, para aparecerem como ARCO no Docker e não com o nome da pasta.
- O volume `arco-pgdata` persiste os dados entre reinícios. Para zerar: `docker compose -f infra/docker-compose.yml down -v`.
- O ponto de montagem é `/var/lib/postgresql`, o esperado pelas imagens 18 em diante.

Uso é somente local: não há deploy nem autenticação.

## Túnel: a API local na internet, para o time testar

`make tunel` expõe a API que está rodando na sua máquina por um [túnel rápido da Cloudflare](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/). Serve para quem cuida do `web` testar contra um banco que já tem snapshot carregado e vínculos validados, sem montar nada disso na própria máquina.

Não é deploy. O produto continua de uso local; o túnel é ferramenta de desenvolvimento e vive enquanto o terminal estiver aberto.

### Quem expõe

1. Instalar o `cloudflared` uma vez: [página de downloads da Cloudflare](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/). Não precisa de conta nem de domínio.
2. Subir o banco e a API: `make db` e `make api`.
3. Em outro terminal: `make tunel`. O script confere que a API responde, sobe o túnel e imprime a URL, no formato `https://<palavras-sorteadas>.trycloudflare.com`.
4. Mandar a URL para quem vai testar. `Ctrl+C` derruba o túnel e a URL deixa de existir.

A API em outra porta: `make tunel PORTA=8001`.

### URL fixa, com subdomínio seu

`make tunel` serve para mandar um endereço a alguém agora. Para um endereço que **não muda** —
o front apontar para ele no `.env`, o time guardar o link —, o caminho é um **túnel nomeado**,
criado no painel da Cloudflare. Continua não sendo deploy: quem serve a API é a sua máquina, e o
túnel só a alcança de fora.

Dois alvos, depois de configurado:

- `make tunel-fixo` liga o túnel, com a API já no ar.
- `make servidor` sobe a API, o MCP do ARCO **e** o túnel juntos, e um `Ctrl+C` derruba os
  três. Sem token configurado, API e MCP sobem sozinhos e o script diz o que faltou:
  desenvolver na própria máquina não depende de ter túnel. Se o MCP não subir, a API e o túnel
  seguem, e o script avisa.

**O túnel conecta por IPv4.** Com o `auto` do `cloudflared`, numa máquina sem rota IPv6
confiável até a Cloudflare, parte das conexões cai com `network is unreachable` e fica
reconectando, e quem chama nesse meio-tempo recebe 502. Quem tem IPv6 de verdade pode pôr
`TUNNEL_EDGE_IP_VERSION=auto` no ambiente.

**Chamar duas vezes não empilha.** Os dois alvos conferem o que já está em pé e recusam, dizendo
o pid e como derrubar. Sem isso o segundo `make servidor` sairia pior que um erro: o `uvicorn`
morre com `address already in use`, o teste de saúde seguinte é respondido pela instância
**antiga**, e o script concluiria que subiu — conectando mais um `cloudflared`, que a Cloudflare
aceita como réplica e passa a repartir as chamadas. Uma API a menos e um túnel a mais, sem erro
na tela.

#### No painel da Cloudflare, uma vez

1. **Zero Trust** → **Networks** → **Tunnels**.
2. **Create a tunnel** → **Cloudflared** → um nome, por exemplo `arco`. Se já houver um túnel
   nesta máquina para outro serviço, dá para **reaproveitá-lo**: um túnel serve vários
   hostnames, e aí pule para o passo 5 abrindo o túnel existente.
3. A tela seguinte mostra o comando de instalação com um **token** dentro. Copie só o token.
4. Guarde o token num arquivo só seu, nunca no repositório:

   ```
   install -m 600 /dev/stdin ~/.cloudflared/token-arco <<< 'COLE_O_TOKEN_AQUI'
   ```

5. Aba **Public Hostnames** → **Add a public hostname**:

   | campo | valor |
   |---|---|
   | Subdomain | `arco-dev`, por exemplo |
   | Domain | o seu domínio |
   | Type | `HTTP` |
   | URL | `localhost:8000` |

   `HTTP` e não `HTTPS`: o TLS termina na Cloudflare, e daí até a sua máquina o tráfego vai
   dentro do túnel. Apontar para `HTTPS` faria o `cloudflared` procurar um certificado que a
   API local não tem.

6. O registro de DNS a Cloudflare cria sozinha. Não crie um `CNAME` à mão, e não ligue o
   proxy laranja de um `A` apontando para casa: o túnel dispensa IP público e porta aberta.

#### O MCP do ARCO num segundo hostname

O MCP do ARCO (`make agentes`) roda na mesma máquina, em outra porta, e o Claude web
e o ChatGPT web o alcançam pelo mesmo túnel, num **segundo hostname**. No mesmo túnel, aba
**Public Hostnames** → **Add a public hostname**:

| campo | valor |
|---|---|
| Subdomain | `arco-mcp`, por exemplo |
| Domain | o seu domínio |
| Type | `HTTP` |
| URL | `localhost:8100` (a `ARCO_MCP_PORTA` do `.env`) |

O endereço que se cola no cliente é `https://arco-mcp.seudominio/mcp`, o perfil do chat. O
caminho `/explorador/mcp` é do explorador, que conecta por `localhost`; ele fica alcançável pelo
túnel também, e grava pela API o mesmo que a API já aceita de qualquer um. **O MCP é aberto, sem
autenticação**, como a API (decidido em 2026-09-23): as mesmas cautelas de "Antes de deixar no
ar" valem para ele.

`make servidor` sobe o MCP junto com a API e o túnel, e o aponta para a API que acabou de subir.
`make agentes` sobe só o MCP, com a API já no ar em `ARCO_API_URL`, `http://localhost:8000` por
padrão.

#### No `.env`, uma vez

```
CORS_ORIGENS=http://localhost:5173,http://127.0.0.1:5173,https://o-endereco-do-front
VITE_API_URL=https://arco-dev.seudominio
```

`CORS_ORIGENS` é a origem da **página**, nunca a da API. Pôr ali o endereço do túnel não serve
para nada: o que o navegador manda no cabeçalho `Origin` é de onde o `web` foi servido — o
`localhost:5173` de quem desenvolve, ou a URL pública se o front estiver publicado.

A API **só lê `CORS_ORIGENS` quando sobe**: mudou, reinicie. Sem isso o navegador bloqueia toda
chamada da interface, e o sintoma é `Network Error` sem detalhe, com a URL funcionando quando
aberta direto — foi o que aconteceu em 18/09 e levou um dia para achar.

**Não deixe `*` com URL fixa.** Ele resolve o sintoma e é razoável enquanto `make tunel` durar,
porque a URL sorteada morre com o terminal. Com endereço permanente e sem autenticação, `*`
significa que qualquer página da web chama esta API pelo navegador de quem a visita.

`VITE_API_URL` faz o `web` chamar a API pública em vez do proxy local. Quem desenvolve na mesma
máquina pode deixar vazio e seguir no proxy, que é mais rápido e não depende do túnel.

#### Antes de deixar no ar

**A API não tem autenticação**: o uso previsto é local, e a simulação não guarda autor. Num endereço fixo e permanente, quem tiver
a URL lê e grava simulações neste banco — e o endereço, diferente do sorteado, não some.

Para fechar sem mexer no código: **Zero Trust** → **Access** → **Applications** →
**Add an application** → **Self-hosted**, o mesmo hostname, e uma policy de e-mail. Quem abrir
passa por uma tela de login da Cloudflare antes de chegar à API.

Atenção: com o Access ligado, o `web` que chama a API do navegador também esbarra no login, e
chamada de máquina, como `curl`, precisa de token de serviço. Para o time testar pelo navegador,
funciona; para script, configure um **Service Token** na mesma tela.

### Quem testa

- Pelo navegador: `<URL>/docs` abre a documentação interativa, e `<URL>/openapi.json` é o contrato.
- Pelo front: o `web` não chama a API direto; o Vite encaminha `/api` para `http://localhost:8000` (`web/vite.config.ts`). Para usar o túnel, esse alvo passa a ser a URL recebida, com `changeOrigin: true`, porque a Cloudflare roteia pelo cabeçalho `Host`:

  ```ts
  proxy: {
    '/api': {
      target: 'https://<palavras-sorteadas>.trycloudflare.com',
      changeOrigin: true,
      rewrite: (p) => p.replace(/^\/api/, ''),
    },
  },
  ```

  Como o encaminhamento é feito pelo servidor do Vite, e não pelo navegador, esse caminho não depende de CORS. Essa alteração é local e não entra em commit.
- Pelo navegador chamando a URL do túnel direto, sem o proxy: aí vale o CORS. A API libera por padrão só a interface local (`http://localhost:5173`). Quem expõe põe `CORS_ORIGENS=*` no `.env` e reinicia a API enquanto o túnel durar, ou lista a origem de quem testa.

### Cuidados

- **Não há autenticação.** Quem tiver a URL lê tudo e grava simulações no banco de quem expôs. A URL é sorteada e difícil de adivinhar, mas é pública: não postar em canal aberto e derrubar o túnel ao terminar.
- **A URL muda a cada execução.** Reiniciou o túnel, tem de mandar a URL nova.
- O túnel rápido não tem garantia de disponibilidade e a Cloudflare o descreve como recurso para teste. URL fixa e acesso restrito por e-mail pedem túnel nomeado, com conta e domínio na Cloudflare, o que este repositório não configura.
- O dado servido é derivado de dado público do ONS. O que é de quem expôs são as simulações salvas.

