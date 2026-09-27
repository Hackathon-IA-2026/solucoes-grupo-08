# dados

Tudo que liga o ARCO aos dados abertos do ONS: ingestão, snapshots, base derivada e vínculos.

## Comandos

```bash
uv run arco-dados ingerir --destino dados/snapshots/novo   # baixa do bucket do ONS e escreve o manifesto
uv run arco-dados comparar A/manifesto.json B/manifesto.json  # sai 0 se iguais, 1 se diferentes
uv run arco-dados baixar --tag latest --destino dados/snapshots   # baixa uma release e confere os hashes
uv run arco-dados preparar --snapshot dados/snapshots/<tag>       # base derivada; --com-modelo usa a IA
```

`make snapshot`, `make ingerir` e `make preparar` chamam os mesmos comandos.

## Snapshots

- O ONS regrava arquivos já publicados e o bucket não guarda versão. Por isso cada cópia é datada e imutável.
- O job `.github/workflows/snapshot.yml`, disparado sob demanda, baixa os arquivos, calcula o sha256 de cada um e publica uma release `snapshot/AAAA-MM-DD` só se algum conteúdo mudou.
- `baixar` pega a release mais recente por padrão. Enquanto o repositório for privado, precisa de `GITHUB_TOKEN` no `.env`.
- Os arquivos são gravados com nome achatado `<pasta>__<arquivo>`; o `manifesto.json` guarda a chave original, tamanho, ETag, data de modificação no bucket e sha256.
- `dados/snapshots/` é ignorado pelo git.

## Fontes

A lista de pastas, padrões de nome e finalidade está em `src/arco_dados/fontes.py`. Os dicionários de dados (`DicionarioDados_*`) entram no snapshot junto com os Parquet, para a auditoria citar a versão exata.

Licença dos dados: CC-BY, Operador Nacional do Sistema Elétrico (ONS), Portal de Dados Abertos.

## Vínculos

`vinculos/` guarda a associação, versionada e validada por engenheiro, entre restrição e equipamento. Ver `vinculos/README.md`.
