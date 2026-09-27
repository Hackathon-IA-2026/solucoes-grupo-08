"""Premissas: catálogo coerente com `Configuracao`; status validada exige autor."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError
from test_spec_tela_criar_simulacao import campos

from arco_motor.cenarios import (
    CUSTOS_POR_CENARIO,
    PREMISSAS_POR_CENARIO,
    valores_iniciais,
)
from arco_motor.premissas import PREMISSAS_PADRAO, Premissa, StatusPremissa
from arco_motor.tipos import Cenario, Configuracao, Modalidade, TipoIntervencao


def test_todo_cenario_preenche_campo_que_existe_em_configuracao() -> None:
    """Campo com nome errado abriria vazio na tela, em silêncio: aqui ele falha alto."""
    folhas = set(campos())
    assert set(PREMISSAS_POR_CENARIO) == set(Cenario)
    for cenario, valores in PREMISSAS_POR_CENARIO.items():
        inexistentes = sorted({valor.campo for valor in valores} - folhas)
        assert not inexistentes, f"{cenario}: campo fora de Configuracao: {inexistentes}"
        assert all(valor.premissa.fonte for valor in valores)


def _por_campo(cenario: Cenario, modalidade: Modalidade) -> dict[str, float]:
    valores: dict[str, float] = {}
    for valor in valores_iniciais(cenario, modalidade):
        assert isinstance(valor.premissa.valor, int | float), valor.premissa.id
        valores[valor.campo] = valor.premissa.valor
    return valores


def test_valor_do_catalogo_passa_no_tipo_que_ele_preenche() -> None:
    """Valor fora da faixa do campo faria a tela abrir inválida, e só estouraria no 422."""
    for cenario in Cenario:
        valores = _por_campo(cenario, Modalidade.COMBINADA)

        def bloco(prefixo: str, valores: dict[str, float] = valores) -> dict[str, float]:
            marca = f"{prefixo}."
            return {
                campo.removeprefix(marca): valor
                for campo, valor in valores.items()
                if campo.startswith(marca)
            }

        configuracao = Configuracao.model_validate(
            {
                "modalidade": Modalidade.COMBINADA,
                "bateria": {
                    "potencia_mw": 10.0,
                    "capacidade_mwh": 40.0,
                    "subestacao": "SE TESTE",
                    **bloco("bateria"),
                },
                "equipamento": {
                    "tipo": TipoIntervencao.ADICAO_CIRCUITO,
                    "cod_equipamento": "LT-TESTE-1",
                    "ganho_limite_mw": 10.0,
                },
                "financeira": {
                    "cenario": cenario,
                    "capex_reais": 1_000_000.0,
                    **bloco("financeira"),
                },
            }
        )
        assert configuracao.financeira.taxa_desconto_aa == valores["financeira.taxa_desconto_aa"]
        assert configuracao.bateria is not None
        assert configuracao.bateria.vida_util_anos == valores["bateria.vida_util_anos"]


def test_horizonte_da_bateria_nao_passa_da_vida_util_dela() -> None:
    """Horizonte maior que a vida útil credita energia de um ativo já morto, sem reposição."""
    for cenario in Cenario:
        so_bateria = _por_campo(cenario, Modalidade.BATERIA)
        assert so_bateria["financeira.horizonte_anos"] == so_bateria["bateria.vida_util_anos"]
        com_linha = _por_campo(cenario, Modalidade.COMBINADA)
        assert com_linha["financeira.horizonte_anos"] > com_linha["bateria.vida_util_anos"]


def test_toda_premissa_tem_fonte() -> None:
    assert all(p.fonte for p in PREMISSAS_PADRAO.itens.values())


def test_validada_exige_autor_e_data() -> None:
    with pytest.raises(ValidationError, match="exige validado_por"):
        Premissa(id="x", descricao="x", valor=1, fonte="f", status=StatusPremissa.VALIDADA)
    ok = Premissa(
        id="x",
        descricao="x",
        valor=1,
        fonte="f",
        status=StatusPremissa.VALIDADA,
        validado_por="alguém",
        validado_em=date(2026, 9, 15),
    )
    assert ok.status is StatusPremissa.VALIDADA


def test_alterar_valor_rebaixa_para_proposta() -> None:
    novas = PREMISSAS_PADRAO.com(sensibilidade_equipamento=0.7)
    assert novas.valor("sensibilidade_equipamento") == 0.7
    assert novas.obter("sensibilidade_equipamento").status is StatusPremissa.PROPOSTA
    assert PREMISSAS_PADRAO.valor("sensibilidade_equipamento") == 1.0


def test_premissa_desconhecida_falha_claramente() -> None:
    with pytest.raises(KeyError, match="desconhecida"):
        PREMISSAS_PADRAO.obter("nao_existe")


def test_custo_da_linha_e_o_mesmo_nos_tres_cenarios() -> None:
    """Na linha, a coluna de referência é a de leilão, que o código usa nos três cenários."""
    referencia = CUSTOS_POR_CENARIO[Cenario.REFERENCIA].obter("linha_500kv_simples_km").valor
    for cenario in Cenario:
        linha = CUSTOS_POR_CENARIO[cenario].obter("linha_500kv_simples_km")
        assert linha.valor == referencia
        assert linha.faixa is None, "as colunas do BPR são obras diferentes, não incerteza"
