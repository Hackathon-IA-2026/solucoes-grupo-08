"""Extração determinística do texto da restrição, contra os formatos reais do ONS."""

from __future__ import annotations

from arco_dados.texto import (
    CONTINGENCIADO,
    MONITORADO,
    contingencia,
    extrair,
    instrucao_de_operacao,
    nome_curto,
    normalizar,
    tokens,
)

UM = (
    "Controle de inequação: LIMITAÇÃO DA TRANSMISSÃO NA LT 500 KV "
    "AÇU III / JAGUARUANA II – C1(V7) - IO-ON.NE.5NE"
)
TRES = (
    "Controle de inequação: LIMITAÇÃO DA TRANSMISSÃO NAS LTS 500 KV AÇU III / QUIXADÁ – "
    "C1(V2), AÇU III / MILAGRES II – C1(C2) E AÇU III / JAGUARUANA II – C1(V7) - IO-ON.NE.5NE"
)
COM_QUEBRA = (
    "Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 230 KV IRECÊ / MORRO DO CHAPÉU II"
    " – C1(S5), PREVENINDO\nA PERDA DA LT 500 KV MORRO DO CHAPÉU II / OUROLÂNDIA II – C1(N4)"
    " - IO-ON.NE.2SO e MOP 442-S/2025"
)
ALTERNATIVOS = (
    "Controle de inequação: LIMITAÇÃO DA TRANSMISSÃO DA LT 500 KV "
    "CAMPINA GRANDE III / CEARÁ MIRIM II – C1(L2) OU C2(L3) - IO-ON.NE.5NE"
)
DOIS_CIRCUITOS = (
    "Controle de inequação: CONTROLE DE CARREGAMENTO DAS LT 500 KV "
    "SOBRADINHO / SÃO JOÃO DO PIAUÍ - C1(C5) E C2(C2) - IO-ON.NE.5NE"
)
CONTINGENCIA = (
    "Controle de inequação: CONTROLE DE CARREGAMENTO DA LT 230 KV AÇU III / MOSSORÓ II – "
    "C1(Z7) PARA CONTINGÊNCIA DA LT 500 KV AÇU III / JAGUARUANA II – C1(V7) - IO-ON.NE.5NE"
)


def test_normalizar_junta_o_texto_que_o_espaco_partia() -> None:
    """A maior restrição do escopo aparece com e sem espaço no fim: 108 e 109 caracteres.

    Sem normalizar, agrupar por `dsc_restricao` parte 3.320 GWh em 2.699 e 620, e o ranking
    mostra o maior gargalo do produto duas vezes, cada metade parecendo um gargalo distinto.
    """
    assert len(UM) == 108
    assert len(UM + " ") == 109
    assert normalizar(UM) == normalizar(UM + " ") == UM


def test_normalizar_colapsa_quebra_de_linha_e_espaco_duplo() -> None:
    assert normalizar("A\nB  C ") == "A B C"


def test_um_equipamento() -> None:
    (equipamento,) = extrair(UM)
    assert (equipamento.tensao_kv, equipamento.de, equipamento.para) == (
        500,
        "ACU III",
        "JAGUARUANA II",
    )
    assert equipamento.codigo_circuito == "V7"
    assert equipamento.papel == MONITORADO


def test_tres_equipamentos_num_texto_sem_a_conjuncao_colar_no_nome() -> None:
    citados = extrair(TRES)
    assert [c.para for c in citados] == ["QUIXADA", "MILAGRES II", "JAGUARUANA II"]
    assert {c.de for c in citados} == {"ACU III"}
    assert [c.codigo_circuito for c in citados] == ["V2", "C2", "V7"]


def test_quebra_de_linha_no_meio_e_papel_de_contingencia() -> None:
    monitorado, contingenciado = extrair(COM_QUEBRA)
    assert monitorado.papel == MONITORADO
    assert monitorado.para == "MORRO DO CHAPEU II"
    assert contingenciado.papel == CONTINGENCIADO
    assert contingenciado.tensao_kv == 500


def test_circuitos_alternativos_saem_marcados() -> None:
    primeiro, segundo = extrair(ALTERNATIVOS)
    assert primeiro.codigo_circuito == "L2"
    assert segundo.codigo_circuito == "L3"
    assert segundo.alternativo is True


def test_dois_circuitos_do_mesmo_par_com_hifen_no_lugar_do_travessao() -> None:
    circuitos = [c.codigo_circuito for c in extrair(DOIS_CIRCUITOS)]
    assert circuitos == ["C5", "C2"]


def test_monitorado_e_contingenciado_no_mesmo_texto() -> None:
    monitorado, contingenciado = extrair(CONTINGENCIA)
    assert (monitorado.tensao_kv, monitorado.papel) == (230, MONITORADO)
    assert (contingenciado.tensao_kv, contingenciado.papel) == (500, CONTINGENCIADO)


def test_linhas_no_plural_tambem_ancora() -> None:
    """ "PREVENINDO A PERDA DAS LINHAS 230 KV ..." é âncora; sem isso o nome da subestação
    saía com a frase inteira colada nele."""
    texto = (
        "CONTROLE DE CARREGAMENTO DA LT 230 KV AQUIRAZ II / CAUCAIA II – C1(F1), PREVENINDO "
        "A PERDA DAS LINHAS 230 KV AQUIRAZ II / FORTALEZA – C2(F2) E C3(F3) - IO"
    )
    citados = extrair(texto)
    assert [c.de for c in citados] == ["AQUIRAZ II", "AQUIRAZ II", "AQUIRAZ II"]
    assert [c.papel for c in citados] == [MONITORADO, CONTINGENCIADO, CONTINGENCIADO]


def test_texto_que_nao_nomeia_linha_nao_inventa() -> None:
    assert extrair("Controle de frequência do SIN.") == []
    assert extrair("LIMITAÇÃO DO FLUXO BAHIA SUDOESTE e MOP 489-R") == []


def test_tokens_atravessam_a_abreviacao_do_cadastro() -> None:
    """O cadastro abrevia: o texto escreve por extenso e usa algarismo romano."""
    assert tokens("MORRO DO CHAPÉU II") == tokens("MORRO CHAPEU II")
    assert tokens("CEARÁ MIRIM II") == tokens("CEARA MIRIM 2")
    assert tokens("PAULO AFONSO") & tokens("P.AFONSO III") == {"AFONSO"}


def test_nome_curto_sai_do_monitorado_com_acento_e_caixa_legivel() -> None:
    """O ONS escreve em caixa alta e o casamento trabalha sem acento; a tela quer os dois."""
    assert nome_curto(extrair(CONTINGENCIA)) == "LT 230 kV Açu III / Mossoró II · C1"


def test_nome_curto_deixa_a_contingencia_de_fora() -> None:
    """A contingência descreve o cenário, não a restrição, e dobraria o tamanho do nome."""
    nome = nome_curto(extrair(CONTINGENCIA))
    assert nome is not None and "Jaguaruana" not in nome
    assert contingencia(extrair(CONTINGENCIA)) == "LT 500 kV Açu III / Jaguaruana II · C1"


def test_preposicao_fica_minuscula_e_romano_fica_maiusculo() -> None:
    assert nome_curto(extrair(DOIS_CIRCUITOS)) == "LT 500 kV Sobradinho / São João do Piauí · C1"
    assert nome_curto(extrair(COM_QUEBRA)) == "LT 230 kV Irecê / Morro do Chapéu II · C1"


def test_nome_curto_mantem_o_circuito_mesmo_com_um_so() -> None:
    """Forma fixa vale mais que nome curto: o olho acha a diferença pela posição dela."""
    nome = nome_curto(extrair(ALTERNATIVOS))
    assert nome == "LT 500 kV Campina Grande III / Ceará Mirim II · C1"


def test_sem_equipamento_reconhecido_nao_inventa_nome() -> None:
    assert nome_curto(extrair("Controle de inequação: TEXTO QUE O REGEX NÃO LÊ")) is None
    assert contingencia(extrair(DOIS_CIRCUITOS)) is None, "este texto não cita contingência"


def test_instrucao_de_operacao_sai_do_texto_e_nao_se_inventa() -> None:
    assert instrucao_de_operacao(CONTINGENCIA) == "IO-ON.NE.5NE"
    assert instrucao_de_operacao(COM_QUEBRA) == "IO-ON.NE.2SO", "para antes do MOP"
    assert instrucao_de_operacao("sem código nenhum") is None
