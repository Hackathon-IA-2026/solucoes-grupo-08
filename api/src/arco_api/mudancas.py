"""O que mudou de uma revisão para a anterior, em uma frase.

A coluna existe na tela de simulações salvas e ninguém a digita: ela sai da comparação entre a
configuração desta revisão e a da anterior, **mais as premissas usadas nas duas**. Nota escrita à
mão envelhece e mente; comparação não.

Comparar só a configuração deixava de fora `fonte` e `correcao_minutos`, que são premissa e não
campo de `Configuracao`: uma revisão que só trocava a fonte saía como "Recalculada com os mesmos
parâmetros" com o número diferente ao lado.

O rótulo de cada campo é o mesmo que a tela de criar simulação usa, e vem da tabela de
`docs/features/contrato-criar-simulacao/04-campos-da-configuracao-ao-calculo.md`. Um teste exige
que os dois lados sejam iguais: rótulo que mudar no documento quebra o teste até o código
acompanhar.
"""

from __future__ import annotations

from typing import Any

from arco_motor.relatorio import numero_br

ROTULOS: dict[str, str] = {
    "modalidade": "Modalidade",
    "bateria.subestacao": "Subestação de conexão da bateria",
    "bateria.potencia_mw": "Potência da bateria",
    "bateria.capacidade_mwh": "Capacidade da bateria",
    "bateria.soc_inicial": "Carga no início da janela",
    "bateria.soc_min": "Carga mínima",
    "bateria.soc_max": "Carga máxima",
    "bateria.eficiencia_ida_volta": "Eficiência de ida e volta",
    "bateria.disponibilidade": "Disponibilidade da bateria",
    "bateria.degradacao_por_ciclo": "Degradação por ciclo",
    "bateria.degradacao_por_ano": "Degradação por ano",
    "bateria.vida_util_anos": "Vida útil da bateria",
    "equipamento.tipo": "Tipo de intervenção",
    "equipamento.cod_equipamento": "Linha que recebe o circuito",
    "equipamento.capacidade_depois_mva": "Capacidade depois da adição",
    "equipamento.ganho_limite_mw": "Ganho de limite",
    "equipamento.disponibilidade": "Disponibilidade do circuito",
    "equipamento.vida_util_anos": "Vida útil do circuito",
    "financeira.cenario": "Cenário",
    "financeira.taxa_desconto_aa": "Taxa de desconto",
    "financeira.horizonte_anos": "Horizonte",
    "financeira.capex_reais": "Investimento inicial",
    "financeira.opex_fixo_reais_ano": "Custo fixo de operação",
    "financeira.opex_variavel_reais_mwh": "Custo variável de operação",
    "financeira.reposicoes[].ano": "Ano da reposição",
    "financeira.reposicoes[].valor_reais": "Valor da reposição",
    "financeira.valor_residual_reais": "Valor residual",
    "financeira.preco_energia_reais_mwh": "Preço da energia",
    "financeira.receitas_adicionais_reais_ano": "Receitas adicionais",
}

ROTULOS_PREMISSA: dict[str, str] = {
    "fonte_geracao": "Fonte de geração",
    "correcao_minutos": "Correção pelos minutos",
    "sensibilidade_equipamento": "Sensibilidade do equipamento",
    "despacho_bateria": "Estratégia de despacho da bateria",
    "bateria_carrega_so_do_corte": "Bateria carrega só do corte",
    "ordem_combinada": "Ordem na modalidade combinada",
    "regra_ocorrencia_intervalos_tolerados": "Folga tolerada dentro da ocorrência",
    "preco_energia": "Preço da energia padrão",
    "agregacao_minutos": "Agregação dos minutos",
    "anualizacao": "Anualização do período",
    "bateria_duracao_horas": "Duração calibrada da bateria",
    "teto_alavanca_capacidade": "Teto da alavanca pela capacidade da linha",
}
"""Rótulo de cada premissa, em dicionário separado do de configuração porque premissa não é
campo de formulário: a tabela de `04-campos-da-configuracao-ao-calculo.md` é de campo, e pôr
`anualizacao` nela diria que existe um controle na tela que não existe. `preco_energia` ganha
"padrão" no nome para não colidir com o campo `financeira.preco_energia_reais_mwh`, que é o
valor digitado e vence a premissa. Um teste exige que toda premissa do motor tenha rótulo."""

ORIGINAL = "Original, primeira revisão desta simulação."
LIMITE_DE_MUDANCAS = 4
"""Quantas mudanças cabem na frase antes de virar contagem. A coluna é uma linha de tabela."""


def _folhas(valor: Any, prefixo: str = "") -> dict[str, Any]:
    """A configuração achatada em caminho pontuado. A lista de reposições fica inteira."""
    if not isinstance(valor, dict):
        return {prefixo: valor}
    achatado: dict[str, Any] = {}
    for chave, dentro in valor.items():
        caminho = f"{prefixo}.{chave}" if prefixo else str(chave)
        if isinstance(dentro, dict):
            achatado |= _folhas(dentro, caminho)
        else:
            achatado[caminho] = dentro
    return achatado


def _numero(valor: Any) -> str:
    """Número sem cauda de ponto flutuante: 0.85 vira 0,85 e 40.0 vira 40."""
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        return str(valor)
    texto = f"{valor:.6f}".rstrip("0").rstrip(".") if isinstance(valor, float) else str(valor)
    return texto.replace(".", ",")


def _escrever(valor: Any) -> str:
    if valor is None:
        return "vazio"
    if isinstance(valor, bool):
        # Só premissa é booleana; nenhum campo de `Configuracao` é. "True → False" não é texto
        # de tela.
        return "sim" if valor else "não"
    if isinstance(valor, list):
        return f"{len(valor)} linha" if len(valor) == 1 else f"{len(valor)} linhas"
    return _numero(valor)


def _rotulo(caminho: str) -> str:
    return ROTULOS.get(caminho, caminho)


def _premissas_mudadas(agora: dict[str, Any] | None, antes: dict[str, Any] | None) -> list[str]:
    """Premissas que mudaram de valor, **só as presentes nas duas revisões**.

    A interseção não é economia: `premissas_usadas` carimba premissa conforme a modalidade, então
    trocar bateria por combinada faz nascer `ordem_combinada` e `sensibilidade_equipamento`.
    Reportá-las seria chamar de mudança própria o que é consequência da modalidade — que a linha
    da modalidade já diz —, e são três linhas falsas numa coluna que mostra quatro. Premissa que
    só existe de um lado também aparece ao ler revisão salva antes de a premissa ser carimbada,
    e "vazio → eolica" descreveria como alteração do usuário o que foi mudança de versão.
    """
    if not agora or not antes:
        return []
    mudancas: list[str] = []
    for id, premissa in agora.items():
        anterior = antes.get(id)
        if anterior is None:
            continue
        de, para = anterior.get("valor"), premissa.get("valor")
        if de != para:
            mudancas.append(f"{ROTULOS_PREMISSA.get(id, id)}: {_escrever(de)} → {_escrever(para)}")
    return mudancas


def descrever(
    configuracao: dict[str, Any],
    anterior: dict[str, Any] | None,
    snapshot_id: str,
    snapshot_anterior: str | None,
    posicao_anterior: int | None,
    premissas: dict[str, Any] | None = None,
    premissas_anteriores: dict[str, Any] | None = None,
) -> str:
    """A frase da coluna "o que mudou", pronta para a tela.

    Sem revisão anterior, é a original. Com anterior, lista o que saiu do lugar; quando nada saiu,
    diz o que sobrou para explicar por que a revisão existe — quase sempre dado novo do ONS.
    """
    if anterior is None:
        return ORIGINAL

    referencia = f"rev {posicao_anterior}" if posicao_anterior is not None else "a anterior"
    antes, depois = _folhas(anterior), _folhas(configuracao)
    mudancas: list[str] = []
    for caminho in dict.fromkeys([*antes, *depois]):
        de, para = antes.get(caminho), depois.get(caminho)
        if de == para:
            continue
        mudancas.append(f"{_rotulo(caminho)}: {_escrever(de)} → {_escrever(para)}")

    # Premissa depois da configuração: a configuração é o que o usuário desenhou, a premissa é
    # sob que hipótese aquilo foi calculado. `fonte` e `correcao_minutos` entram por aqui, porque
    # são premissa e não fazem parte de `Configuracao`.
    mudancas += _premissas_mudadas(premissas, premissas_anteriores)

    if not mudancas:
        if snapshot_id != snapshot_anterior:
            return f"Snapshot do ONS diferente; parâmetros iguais à {referencia}."
        return f"Recalculada com os mesmos parâmetros e o mesmo dado da {referencia}."

    if len(mudancas) > LIMITE_DE_MUDANCAS:
        sobraram = len(mudancas) - LIMITE_DE_MUDANCAS
        mudancas = [*mudancas[:LIMITE_DE_MUDANCAS], f"e mais {sobraram}"]
    frase = "; ".join(mudancas) + "."
    if snapshot_id != snapshot_anterior:
        return f"{frase} Snapshot do ONS também mudou."
    return frase


CENARIOS = {
    "conservador": "cenário conservador",
    "referencia": "cenário de referência",
    "otimista": "cenário otimista",
}


def resumir(configuracao: dict[str, Any]) -> str:
    """A configuração em uma frase, para a trilha do relatório quando a revisão não tem nota.

    "Bateria de 50 MW e 200 MWh em Açu III, cenário de referência". Template, não modelo: a
    frase só diz o que está na configuração, e por isso nunca precisa de conferência. O número
    sai como na coluna alavanca do relatório (`arco_motor.relatorio.numero_br`), para a trilha e
    a tabela escreverem 1.500 MW do mesmo jeito.
    """
    partes: list[str] = []
    equipamento = configuracao.get("equipamento")
    bateria = configuracao.get("bateria")
    if equipamento:
        partes.append(
            f"circuito novo em {equipamento.get('cod_equipamento')} com ganho de "
            f"{numero_br(float(equipamento.get('ganho_limite_mw') or 0))} MW"
        )
    if bateria:
        partes.append(
            f"bateria de {numero_br(float(bateria.get('potencia_mw') or 0))} MW e "
            f"{numero_br(float(bateria.get('capacidade_mwh') or 0))} MWh em "
            f"{bateria.get('subestacao')}"
        )
    frase = " e ".join(partes) or f"modalidade {configuracao.get('modalidade')}"
    cenario = (configuracao.get("financeira") or {}).get("cenario")
    if cenario in CENARIOS:
        frase = f"{frase}, {CENARIOS[cenario]}"
    return frase[0].upper() + frase[1:]
