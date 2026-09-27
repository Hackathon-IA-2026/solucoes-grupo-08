# web

Interface do ARCO: React 19, TypeScript, Vite. Consome a API por cliente gerado do contrato (`src/api/gerado/`). Não faz conta.

```bash
pnpm install
pnpm dev          # http://localhost:5173, com proxy de /api para a API em :8000
pnpm test         # vitest
pnpm lint         # oxlint
pnpm typecheck    # tsc
pnpm build
```

Telas: ranking das restrições, detalhe da restrição, criar simulação, simulações salvas com resultado e revisões, comparador de revisões, relatório e o andamento da exploração por agente.
