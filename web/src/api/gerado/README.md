Cliente TypeScript gerado de `contratos/openapi.json` pelo `openapi-typescript`.
Nunca editar; regenerar com `make contrato` (raiz) ou `pnpm -C web run gerar-cliente`.

`tipos.ts` traz os tipos de cada rota (`paths`) e esquema (`components['schemas']`,
com atalho `SchemaX`). Não tem função de chamada: quem chama a API é o `httpClient`
de `src/api/client.ts`, e cada `features/<feature>/api/*.ts` usa os tipos daqui.
