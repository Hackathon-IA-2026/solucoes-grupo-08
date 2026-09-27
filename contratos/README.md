# contratos

`openapi.json` é gerado pela API com `make contrato` (`python -m arco_api.contrato`). É a fronteira entre `api/` e `web/`: o cliente TypeScript é gerado a partir dele. Nunca editar à mão; a CI falha quando o arquivo difere do que a API gera.
