"""ARCO, ia: extração de equipamento e relatório da simulação.

Parte essencial do produto: sem o vínculo que a extração produz não há ranking nem simulação
([ADR 0007](../../../docs/adr/0007-servidor-com-internet-e-ia-essencial.md)).
"""


class IndisponivelSemChave(RuntimeError):
    """Sem chave de API. Quem chama falha alto e diz o que ficou faltando; nunca segue calado."""
