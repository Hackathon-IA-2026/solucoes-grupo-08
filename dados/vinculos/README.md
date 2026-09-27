# Vínculos

Dado do projeto, versionado: a associação entre uma restrição do ONS e o equipamento do cadastro a que ela se refere, com o papel do equipamento no texto (`monitorado` ou `contingencia`). A intervenção se aplica ao equipamento monitorado.

O vínculo vive em tabela no Postgres, com `status` (`proposto`, `validado`, `rejeitado`). A regra determinística ou o modelo propõem; só entra sozinho o que casa, por código, com o cadastro do snapshot, e o resto espera validação de engenheiro na ferramenta. O que fica aqui é **semente e backup**: os validados são exportados para CSV versionado, e é deles que o banco é recriado. O banco é descartável; a curadoria não.

**`vinculos_validados.csv` é a semente em uso.** Sai de `make exportar-vinculos`, e `make semear` (ou `make banco`) reaplica num banco novo. Traz `restricao_id`, `cod_equipamento`, `papel`, `status`, `validado_por`, `validado_em` e `observacao`. Validou vínculo novo, exporte: sem isso a validação existe só no banco de quem validou, e some quando o volume for apagado.

O casamento com o cadastro é feito pela tripla tensão, par de subestações e circuito, porque o nome de linha no cadastro vem abreviado e sem acento.
