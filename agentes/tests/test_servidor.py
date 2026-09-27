"""O MCP do ARCO pelo cliente MCP do SDK, com a API falsa do `conftest.py` (task 17.13)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Coroutine
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from arco_agentes import servidor as modulo
from arco_agentes.servidor import Contexto, criar_servidor

CONSULTAS = {
    "listar_restricoes",
    "ver_restricao",
    "listar_simulacoes",
    "ver_revisao",
    "ver_relatorio",
}
CHAT = CONSULTAS | {
    "conferir_simulacao",
    "criar_simulacao",
    "salvar_revisao",
    "explorar_variacoes",
    "ver_andamento",
    "gerar_relatorio",
}
EXPLORADOR = CONSULTAS | {"disparar_lote", "encerrar"}


BATERIA: dict[str, Any] = {
    "restricao_id": "abc123def456",
    "nome": "Bateria em Açu III",
    "modalidade": "bateria",
    "potencia_mw": 50,
    "capacidade_mwh": 200,
    "subestacao": "ACU III",
}
"""Uma simulação de bateria como a pessoa escolhe: o que conferir_simulacao e criar_simulacao
recebem."""


def rodar(corrotina: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(corrotina)


async def _chamar(contexto: Contexto, perfil: str, ferramenta: str, **argumentos: Any) -> Any:
    async with Client(criar_servidor(perfil, contexto)) as cliente:  # type: ignore[arg-type]
        return await cliente.call_tool(ferramenta, argumentos)


def chamar(contexto: Contexto, ferramenta: str, perfil: str = "chat", **argumentos: Any) -> Any:
    return rodar(_chamar(contexto, perfil, ferramenta, **argumentos))


async def _icones(contexto: Contexto, perfil: str) -> list[tuple[str | None, str]]:
    async with Client(criar_servidor(perfil, contexto)) as cliente:  # type: ignore[arg-type]
        assert cliente.server_info is not None
        return [(icone.mime_type, icone.src) for icone in cliente.server_info.icons or []]


def test_o_servidor_manda_o_proprio_icone(contexto: Contexto) -> None:
    """Sem ícone declarado, o cliente cai no do domínio de cima, que pode ser de outro serviço.
    PNG primeiro, que todo cliente que desenha ícone aceita; embutido, sem outro endereço."""
    for perfil in ("chat", "explorador"):
        icones = rodar(_icones(contexto, perfil))
        assert [tipo for tipo, _ in icones] == ["image/png", "image/svg+xml"]
        assert all(src.startswith(f"data:{tipo};base64,") for tipo, src in icones)


async def _nomes(contexto: Contexto, perfil: str) -> set[str]:
    async with Client(criar_servidor(perfil, contexto)) as cliente:  # type: ignore[arg-type]
        return {ferramenta.name for ferramenta in await cliente.list_tools()}


def test_cada_perfil_ve_so_as_suas_ferramentas(contexto: Contexto) -> None:
    """O explorador não vê o disparo, e por isso não se chama em recursão; nem `salvar_revisao`,
    que salvaria como pessoa o que ele decidiu."""
    assert rodar(_nomes(contexto, "chat")) == CHAT
    explorador = rodar(_nomes(contexto, "explorador"))
    assert explorador == EXPLORADOR
    assert "explorar_variacoes" not in explorador
    assert "salvar_revisao" not in explorador


def test_descricoes_dizem_as_recusas_de_antemao(contexto: Contexto) -> None:
    async def descricoes() -> dict[str, str]:
        async with Client(criar_servidor("chat", contexto)) as cliente:
            return {
                t.name: " ".join((t.description or "").split()) for t in await cliente.list_tools()
            }

    texto = rodar(descricoes())
    assert "não recebe circuito novo" in texto["conferir_simulacao"]
    assert "confirmado=true" in texto["explorar_variacoes"]
    assert "409" in texto["explorar_variacoes"]


@pytest.mark.parametrize(
    ("ferramenta", "argumentos", "no_texto"),
    [
        ("listar_restricoes", {}, "LT 500 kV Açu III"),
        ("ver_restricao", {"restricao_id": "abc123def456"}, "não recebe circuito novo"),
        ("listar_simulacoes", {}, "Simulação 1"),
        ("ver_revisao", {"revisao_id": 1}, "Bateria cheia com corte sobrando em 4 de 8"),
        ("ver_relatorio", {"simulacao_id": 1}, "Leitura."),
        ("conferir_simulacao", BATERIA, "- potência: 50 MW"),
        ("gerar_relatorio", {"simulacao_id": 1}, "Relatório 35 pedido"),
    ],
)
def test_toda_ferramenta_devolve_texto_e_dado(
    contexto: Contexto, ferramenta: str, argumentos: dict[str, Any], no_texto: str
) -> None:
    resultado = chamar(contexto, ferramenta, **argumentos)

    assert not resultado.is_error
    assert no_texto in resultado.content[0].text
    assert resultado.structured_content


def test_revisao_nao_leva_a_serie_ao_modelo(contexto: Contexto) -> None:
    """A série de cada meia hora fica na API: no contexto do modelo não informa e custa caro."""
    resultado = chamar(contexto, "ver_revisao", revisao_id=1)

    dados = resultado.structured_content
    assert "cortado_mw" not in str(dados)
    assert dados["resultado"]["fracao_recuperada"] == 0.5
    assert dados["diagnosticos"]["saturacao"]["meias_horas_cheia"] == 4


def test_salvar_revisao_e_da_pessoa(contexto: Contexto, api_falsa) -> None:  # type: ignore[no-untyped-def]
    montada = rodar(contexto.api.montar("abc123def456", {"modalidade": "bateria"}))

    chamar(
        contexto,
        "salvar_revisao",
        configuracao=montada["configuracao"],
        simulacao_id=1,
        revisao_base_id=1,
        nota="A pessoa pediu 50 MW.",
    )

    (pedido,) = api_falsa.pedidos("POST", "/simulacoes")
    assert pedido["procedencia"] == "por_pessoa"
    assert (pedido["simulacao_id"], pedido["revisao_base_id"]) == (1, 1)
    assert "restricao_id" not in pedido


def test_recusa_da_api_chega_com_o_status_e_o_motivo(contexto: Contexto, api_falsa) -> None:  # type: ignore[no-untyped-def]
    api_falsa.recusas["/restricoes/abc123def456/montar"] = (
        422,
        "equipamento LT-1 não recebe circuito novo: o método só modela adição de circuito na "
        "linha monitorada, e esta é a que se supõe perder",
    )

    with pytest.raises(ToolError, match="422: equipamento LT-1 não recebe circuito novo"):
        chamar(
            contexto,
            "conferir_simulacao",
            restricao_id="abc123def456",
            nome="Circuito",
            modalidade="equipamento",
            cod_equipamento="LT-1",
            ganho_limite_mw=40,
        )


def test_explorar_sem_confirmacao_mostra_o_resumo_e_nao_cria_tarefa(
    contexto: Contexto, api_falsa
) -> None:  # type: ignore[no-untyped-def]
    resultado = chamar(contexto, "explorar_variacoes", simulacao_id=1, pedido="Onde achata?")

    texto = resultado.content[0].text
    assert "confirme com a pessoa" in texto
    assert "potência da bateria, de 25 a 400 MW" in texto
    assert "Fica fixo: cenário referencia, taxa de desconto 8 %" in texto
    assert "bateria_capex_kwh 1.375" in texto
    assert "confirmado=true" in texto
    assert "Confirmar ou Cancelar" in texto
    assert api_falsa.pedidos("POST", "/simulacoes/1/tarefas") == []
    cartao = resultado.structured_content
    assert _nos(cartao, "Svg"), "o desenho dos agentes"
    assert _nos(cartao, "Button") == [], "quem confirma é a pergunta do cliente"
    tudo = json.dumps(cartao, ensure_ascii=False)
    assert "até 30 variações da simulação 1" in tudo
    assert "25 a 400 MW" not in tudo and "1.375" not in tudo, "os números ficam no texto"


def test_explorar_sem_explorador_recusa_antes_de_criar(contexto: Contexto, api_falsa) -> None:  # type: ignore[no-untyped-def]
    contexto.iniciar_exploracao = None
    with pytest.raises(ToolError, match="nada foi criado"):
        chamar(contexto, "explorar_variacoes", simulacao_id=1, pedido="x", confirmado=True)
    assert api_falsa.pedidos("POST", "/simulacoes/1/tarefas") == []


def test_explorar_confirmado_cria_a_tarefa_e_quem_dispara_e_a_api(
    contexto: Contexto, api_falsa
) -> None:  # type: ignore[no-untyped-def]
    """O MCP só cria a tarefa: a API dispara, pela rota `/exploracoes`, como faz com o painel.
    Se o MCP também soltasse o explorador, a exploração rodaria duas vezes."""
    recebidas: list[dict[str, Any]] = []

    async def iniciar(tarefa: dict[str, Any]) -> None:
        recebidas.append(tarefa)

    contexto.iniciar_exploracao = iniciar

    async def explorar() -> Any:
        async with Client(criar_servidor("chat", contexto)) as cliente:
            resultado = await cliente.call_tool(
                "explorar_variacoes",
                {"simulacao_id": 1, "pedido": "Onde achata?", "teto": 12, "confirmado": True},
            )
            await asyncio.sleep(0)  # daria vez a uma exploração solta em fundo
            return resultado

    resultado = rodar(explorar())

    (pedido,) = api_falsa.pedidos("POST", "/simulacoes/1/tarefas")
    assert (pedido["pedido"], pedido["teto"]) == ("Onde achata?", 12)
    assert "disparar" not in pedido, "vale o padrão da API: disparar"
    assert recebidas == []
    assert "http://painel/simulacoes/1/exploracoes/7" in resultado.content[0].text
    assert "0 revisões prontas" in resultado.content[0].text
    assert "limite de 12" in resultado.content[0].text


def test_explorar_com_outra_em_andamento_diz_qual(contexto: Contexto, api_falsa) -> None:  # type: ignore[no-untyped-def]
    async def iniciar(tarefa: dict[str, Any]) -> None:
        return None

    contexto.iniciar_exploracao = iniciar
    api_falsa.tarefa_ja_existe = True

    with pytest.raises(ToolError, match="409: já há exploração, a tarefa 4"):
        chamar(contexto, "explorar_variacoes", simulacao_id=1, pedido="x", confirmado=True)


def _com_tarefa(contexto: Contexto, api_falsa, teto: int = 30) -> None:  # type: ignore[no-untyped-def]
    rodar(contexto.api.criar_tarefa(1, {"pedido": "x", "teto": teto}))
    api_falsa.chamadas.clear()


def test_lote_anuncia_confere_e_roda(contexto: Contexto, api_falsa) -> None:  # type: ignore[no-untyped-def]
    """Quatro pedidas: uma fora da faixa, uma repetida no lote, uma que a API recusa como
    repetida na simulação e uma que vira revisão. `rodada_decidida` sai antes de tudo, só com
    as que vão rodar e o `variacao_id` de cada uma; as recusas do lote vêm depois, sem id."""
    _com_tarefa(contexto, api_falsa)
    api_falsa.repetidas.add("150.0")

    resultado = chamar(
        contexto,
        "disparar_lote",
        perfil="explorador",
        tarefa_id=7,
        revisao_partida_id=1,
        variacoes=[
            {"alavanca": "bateria.potencia_mw", "valor": 100},
            {"alavanca": "bateria.potencia_mw", "valor": 500},
            {"alavanca": "bateria.potencia_mw", "valor": 100},
            {"alavanca": "bateria.potencia_mw", "valor": 150},
        ],
        porque="Rodada 1: a grade de tamanhos mostra onde a curva achata.",
    )

    assert api_falsa.tipos()[:3] == ["rodada_decidida", "variacao_recusada", "variacao_recusada"]
    anunciada = api_falsa.eventos[0]
    assert anunciada["rodada"] == 1
    assert [(v["valor"], v["variacao_id"]) for v in anunciada["variacoes"]] == [
        (100.0, "r1-v1"),
        (150.0, "r1-v4"),
    ]
    assert all(e.get("variacao_id") is None for e in api_falsa.eventos[1:3])
    enviadas = api_falsa.pedidos("POST", "/simulacoes/1/variacoes")
    assert sorted(p["variacao_id"] for p in enviadas) == ["r1-v1", "r1-v4"]
    assert all(p["nota"].startswith("Rodada 1") and p["rodada"] == 1 for p in enviadas)
    assert all("preco_energia_reais_mwh" not in p for p in enviadas)

    desfechos = sorted((d["valor"], d["estado"]) for d in resultado.structured_content["desfechos"])
    assert desfechos == [
        (100.0, "pronta"),
        (100.0, "recusada"),
        (150.0, "recusada"),
        (500.0, "recusada"),
    ]
    texto = resultado.content[0].text
    assert "fora da faixa permitida, de 25 a 400" in texto
    assert "repetida dentro do lote" in texto
    assert "409: configuração igual à da revisão 3" in texto


def test_lote_para_no_teto(contexto: Contexto, api_falsa) -> None:  # type: ignore[no-untyped-def]
    """Teto de 2 revisões: de três pedidas, roda duas; a terceira volta recusada pelo teto."""
    _com_tarefa(contexto, api_falsa, teto=2)

    resultado = chamar(
        contexto,
        "disparar_lote",
        perfil="explorador",
        tarefa_id=7,
        revisao_partida_id=1,
        variacoes=[{"alavanca": "bateria.potencia_mw", "valor": v} for v in (100, 150, 200)],
        porque="Rodada 1.",
    )

    assert len(api_falsa.pedidos("POST", "/simulacoes/1/variacoes")) == 2
    assert "teto de 2 revisões" in resultado.content[0].text


def test_encerrar_pede_o_relatorio_e_termina_por_ultimo(
    contexto: Contexto, api_falsa, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(modulo, "INTERVALO_DO_RELATORIO_S", 0.0)
    _com_tarefa(contexto, api_falsa)

    resultado = chamar(
        contexto, "encerrar", perfil="explorador", tarefa_id=7, motivo="A curva achatou."
    )

    assert api_falsa.tipos() == ["relatorio_pedido", "relatorio_pronto", "tarefa_terminada"]
    assert api_falsa.eventos[-1] == {
        "tipo": "tarefa_terminada",
        "estado": "concluida",
        "motivo": "A curva achatou.",
    }
    assert "Relatório 35: pronto" in resultado.content[0].text
    with pytest.raises(ToolError, match="409"):
        chamar(contexto, "encerrar", perfil="explorador", tarefa_id=7, motivo="de novo")


def test_andamento_traz_a_contagem_da_api_e_o_link(contexto: Contexto, api_falsa) -> None:  # type: ignore[no-untyped-def]
    _com_tarefa(contexto, api_falsa, teto=15)

    resultado = chamar(contexto, "ver_andamento", tarefa_id=7)

    assert "0 revisões prontas, 0 trabalhando" in resultado.content[0].text
    assert "limite de 15" in resultado.content[0].text
    assert resultado.structured_content["link"] == "http://painel/simulacoes/1/exploracoes/7"


def _acoes(no: Any, tipo: str) -> list[dict[str, Any]]:
    """Todas as ações de um tipo na árvore do cartão, onde quer que estejam."""
    achadas: list[dict[str, Any]] = []
    if isinstance(no, dict):
        if no.get("action") == tipo:
            achadas.append(no)
        for valor in no.values():
            achadas += _acoes(valor, tipo)
    elif isinstance(no, list):
        for item in no:
            achadas += _acoes(item, tipo)
    return achadas


def test_cartao_de_andamento_pergunta_a_ver_andamento_e_leva_ao_painel(
    contexto: Contexto, api_falsa
) -> None:  # type: ignore[no-untyped-def]
    """A contagem se atualiza a cada meio segundo por `ver_andamento`, enquanto a exploração está em
    andamento, e o botão abre o link configurado da tela Ver processamento."""

    async def iniciar(tarefa: dict[str, Any]) -> None:
        return None

    contexto.iniciar_exploracao = iniciar
    resultado = chamar(
        contexto, "explorar_variacoes", simulacao_id=1, pedido="Onde achata?", confirmado=True
    )

    cartao = resultado.structured_content
    assert "Exploração disparada" in resultado.content[0].text, "texto equivalente"
    (intervalo,) = _acoes(cartao, "setInterval")
    assert intervalo["duration"] == 500
    assert intervalo["while"] == "{{ tarefa.estado == 'em_andamento' }}"
    (pergunta,) = _acoes(intervalo, "toolCall")
    assert (pergunta["tool"], pergunta["arguments"]) == ("ver_andamento", {"tarefa_id": 7})
    (abrir,) = _acoes(cartao, "openLink")
    assert abrir["url"] == "http://painel/simulacoes/1/exploracoes/7"
    assert cartao["state"]["tarefa"]["contagem"]["prontas"] == 0


def test_lista_de_restricoes_segue_na_conversa(contexto: Contexto) -> None:
    resultado = chamar(contexto, "listar_restricoes")

    (mensagem,) = _acoes(resultado.structured_content, "sendMessage")
    assert "abc123def456" in mensagem["content"]
    assert "1.000 MWh" in resultado.content[0].text


def test_no_explorador_a_lista_de_restricoes_e_dado_e_nao_cartao(contexto: Contexto) -> None:
    resultado = chamar(contexto, "listar_restricoes", perfil="explorador")

    assert "$prefab" not in resultado.structured_content
    assert resultado.structured_content["itens"][0]["restricao_id"] == "abc123def456"


async def _instrucoes(contexto: Contexto, perfil: str) -> str:
    async with Client(criar_servidor(perfil, contexto)) as cliente:  # type: ignore[arg-type]
        return cliente.instructions or ""


def test_so_o_chat_recebe_a_ordem_das_perguntas(contexto: Contexto) -> None:
    """Sem a ordem, o modelo abria a própria pergunta de modalidade ao lado da lista, antes de a
    pessoa escolher a restrição no cartão. O explorador não tem cartão nem pergunta."""
    chat = rodar(_instrucoes(contexto, "chat"))
    explorador = rodar(_instrucoes(contexto, "explorador"))

    assert "Uma pergunta de cada vez" in chat
    assert "Criar uma simulação é um processo só" in chat
    assert "ver_andamento com aguardar=true" in chat
    assert "Confirmar ou Alterar valor" in chat
    assert "cartão" not in explorador
    assert "disparar_lote" in explorador


def test_texto_do_chat_manda_esperar_a_escolha_no_cartao(contexto: Contexto) -> None:
    """O texto segue completo, para cliente sem cartão, e termina dizendo ao modelo o que a
    pessoa faz no cartão."""
    lista = chamar(contexto, "listar_restricoes").content[0].text
    conferencia = chamar(contexto, "conferir_simulacao", **BATERIA).content[0].text
    no_explorador = chamar(contexto, "listar_restricoes", perfil="explorador").content[0].text

    assert "1.000 MWh" in lista and "pelo botão Simular" in lista
    assert "duas opções, Confirmar e Alterar valor" in conferencia
    assert "Simular" not in no_explorador


def _nos(no: Any, tipo: str) -> list[dict[str, Any]]:
    """Todos os componentes de um tipo na árvore do cartão."""
    achados: list[dict[str, Any]] = []
    if isinstance(no, dict):
        if no.get("type") == tipo:
            achados.append(no)
        for valor in no.values():
            achados += _nos(valor, tipo)
    elif isinstance(no, list):
        for item in no:
            achados += _nos(item, tipo)
    return achados


def test_conferir_mostra_so_os_campos_sem_edicao_e_nao_salva(contexto: Contexto, api_falsa) -> None:  # type: ignore[no-untyped-def]
    """A simulação ainda não existe: o cartão mostra os campos que a criam, sem edição, e mais
    nada — nem investimento, nem premissa, nem botão. O ARCO só confere os valores."""
    resultado = chamar(contexto, "conferir_simulacao", **BATERIA)

    assert api_falsa.pedidos("POST", "/simulacoes") == []
    assert api_falsa.chamadas[0][:2] == ("GET", "/restricoes/abc123def456/montar")
    cartao = resultado.structured_content
    campos = _nos(cartao, "Input")
    assert all(campo.get("readOnly") for campo in campos)
    assert [campo["value"] for campo in campos] == [
        "Bateria em Açu III",
        "LT 500 kV Açu III / Jaguaruana II · C1",
        "Bateria",
        "Referência",
        "50",
        "200",
        "ACU III",
    ]
    assert _nos(cartao, "Button") == []
    assert _acoes(cartao, "toolCall") == []
    tudo = json.dumps(cartao, ensure_ascii=False)
    assert "Nova simulação, para confirmar" in tudo
    assert "até 30 variações desta simulação" in tudo
    assert _nos(cartao, "Svg"), "o desenho dos agentes"
    assert "R$" not in tudo and "Investimento" not in tudo and "premissa" not in tudo
    assert "ainda não salva" in resultado.content[0].text


def test_conferir_combinada_mostra_a_linha_e_a_bateria(contexto: Contexto) -> None:
    resultado = chamar(
        contexto,
        "conferir_simulacao",
        **BATERIA | {"modalidade": "combinada", "cod_equipamento": "LT-1", "ganho_limite_mw": 40},
    )

    valores = [campo["value"] for campo in _nos(resultado.structured_content, "Input")]
    assert "ACU III – JAGUARUANA II, 500 kV (LT-1)" in valores
    assert {"40", "50", "200"} <= set(valores)


async def _criar(contexto: Contexto, escolhas: dict[str, Any]) -> Any:
    async with Client(criar_servidor("chat", contexto)) as cliente:  # type: ignore[arg-type]
        resultado = await cliente.call_tool("criar_simulacao", escolhas)
        await asyncio.sleep(0)  # a exploração roda em tarefa de fundo
        return resultado


def test_criar_simulacao_salva_pela_pessoa_e_dispara_a_exploracao(
    contexto: Contexto, api_falsa
) -> None:  # type: ignore[no-untyped-def]
    """No Confirmar, um processo só: o ARCO monta com as escolhas e salva pela pessoa, e a
    exploração parte da revisão criada, com o pedido padrão e até 30 variações. Quem põe o
    explorador para rodar é a API, ao criar a tarefa."""
    recebidas: list[dict[str, Any]] = []

    async def iniciar(tarefa: dict[str, Any]) -> None:
        recebidas.append(tarefa)

    contexto.iniciar_exploracao = iniciar
    escolhas: dict[str, Any] = BATERIA | {"potencia_mw": 80}

    resultado = rodar(_criar(contexto, escolhas))

    assert [c[:2] for c in api_falsa.chamadas] == [
        ("GET", "/restricoes/abc123def456"),
        ("GET", "/restricoes/abc123def456/montar"),
        ("POST", "/simulacoes"),
        ("POST", "/simulacoes/1/tarefas"),
    ]
    assert api_falsa.chamadas[1][2]["potencia_mw"] == "80.0"
    (salva,) = api_falsa.pedidos("POST", "/simulacoes")
    assert (salva["procedencia"], salva["nome"]) == ("por_pessoa", "Bateria em Açu III")
    (exploracao,) = api_falsa.pedidos("POST", "/simulacoes/1/tarefas")
    assert (exploracao["teto"], exploracao["revisao_partida_id"]) == (30, 11)
    assert exploracao["pedido"].startswith(
        "Explorar variações de potência, duração e subestação da bateria na restrição "
        "LT 500 kV Açu III / Jaguaruana II · C1, a partir da revisão 11 ("
    )
    assert "disparar" not in exploracao
    assert recebidas == []
    texto = resultado.content[0].text
    assert texto.startswith("Simulação 1 criada, com a revisão 11, e a exploração 7 disparada.")
    assert "chame ver_andamento com tarefa_id=7 e aguardar=true" in texto
    (intervalo,) = _acoes(resultado.structured_content, "setInterval")
    assert intervalo["duration"] == 500


def test_criar_simulacao_leva_o_objetivo_e_o_teto_da_pessoa(contexto: Contexto, api_falsa) -> None:  # type: ignore[no-untyped-def]
    escolhas: dict[str, Any] = BATERIA | {
        "objetivo": "Com quanta potência paga em 20 anos?",
        "teto": 12,
    }

    rodar(_criar(contexto, escolhas))

    (exploracao,) = api_falsa.pedidos("POST", "/simulacoes/1/tarefas")
    assert (exploracao["pedido"], exploracao["teto"]) == (
        "Com quanta potência paga em 20 anos?",
        12,
    )


def test_sem_explorador_nada_se_cria_pelo_chat(contexto: Contexto, api_falsa) -> None:  # type: ignore[no-untyped-def]
    """Criar pelo chat já explora: sem explorador, nem a conferência aparece, e nada se salva."""
    contexto.iniciar_exploracao = None

    for ferramenta in ("conferir_simulacao", "criar_simulacao"):
        with pytest.raises(ToolError, match="nada foi criado"):
            chamar(contexto, ferramenta, **BATERIA)
    assert api_falsa.pedidos("POST", "/simulacoes") == []


def test_exploracao_que_nao_comeca_deixa_a_simulacao_e_diz_por_que(
    contexto: Contexto, api_falsa
) -> None:  # type: ignore[no-untyped-def]
    api_falsa.tarefa_ja_existe = True

    resultado = chamar(contexto, "criar_simulacao", **BATERIA)

    assert len(api_falsa.pedidos("POST", "/simulacoes")) == 1
    texto = resultado.content[0].text
    assert "Simulação 1 criada, com a revisão 11, mas a exploração não começou (409" in texto
    assert resultado.structured_content["exploracao"] is None


def _em_andamento(contexto: Contexto, api_falsa: Any) -> None:
    rodar(contexto.api.criar_tarefa(1, {"pedido": "x", "teto": 30}))
    api_falsa.chamadas.clear()


def test_andamento_sem_aguardar_responde_na_hora(contexto: Contexto, api_falsa) -> None:  # type: ignore[no-untyped-def]
    _em_andamento(contexto, api_falsa)
    api_falsa.consultas_ate_terminar = 3

    resultado = chamar(contexto, "ver_andamento", tarefa_id=7)

    assert len(api_falsa.pedidos("GET", "/tarefas/7")) == 1
    assert resultado.structured_content["estado"] == "em_andamento"


def test_andamento_com_aguardar_segura_ate_terminar(
    contexto: Contexto, api_falsa, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    """Depois de disparar, o modelo acompanha dentro do turno: a resposta só volta quando a
    exploração termina, e ele já pode ler o relatório."""
    monkeypatch.setattr(modulo, "INTERVALO_DA_ESPERA_S", 0.0)
    _em_andamento(contexto, api_falsa)
    api_falsa.consultas_ate_terminar = 3

    resultado = chamar(contexto, "ver_andamento", tarefa_id=7, aguardar=True)

    assert len(api_falsa.pedidos("GET", "/tarefas/7")) == 3
    assert resultado.structured_content["estado"] == "concluida"


def test_andamento_com_aguardar_devolve_no_prazo_se_nao_terminou(
    contexto: Contexto, api_falsa, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    """O prazo fica abaixo do tempo limite de uma chamada de ferramenta: exploração mais longa
    pede outra chamada."""
    monkeypatch.setattr(modulo, "INTERVALO_DA_ESPERA_S", 0.01)
    monkeypatch.setattr(modulo, "ESPERA_MAXIMA_S", 0.05)
    _em_andamento(contexto, api_falsa)

    resultado = chamar(contexto, "ver_andamento", tarefa_id=7, aguardar=True)

    assert resultado.structured_content["estado"] == "em_andamento"
    assert len(api_falsa.pedidos("GET", "/tarefas/7")) > 1


def test_barra_do_andamento_anima_enquanto_roda_e_enche_no_fim(contexto: Contexto) -> None:
    """Quantas variações haverá, só o agente sabe: uma porcentagem enquanto roda voltava para
    trás a cada rodada nova. A barra anima enquanto a exploração trabalha e enche quando ela
    termina; o limite fica numa nota discreta."""
    resultado = chamar(
        contexto, "explorar_variacoes", simulacao_id=1, pedido="Onde achata?", confirmado=True
    )

    cartao = resultado.structured_content
    (barra,) = [no for no in _nos(cartao, "Condition") if "arco-barra-rodando" in json.dumps(no)]
    ((rodando,),) = [caso["children"] for caso in barra["cases"]]
    assert barra["cases"][0]["when"] == "{{ tarefa.estado == 'em_andamento' }}"
    assert rodando["cssClass"] == "arco-barra-rodando"
    ((cheia,),) = [barra["else"]]
    assert (cheia["type"], cheia["value"], cheia["max"]) == ("Progress", 100, 100)
    tudo = json.dumps(cartao, ensure_ascii=False)
    assert "de até" not in tudo
    assert "Limite de {{ tarefa.teto }} variações." in tudo


def test_resposta_da_espera_diz_o_proximo_passo(
    contexto: Contexto, api_falsa, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    """Nem todo cliente entrega as instruções do servidor ao modelo: a própria resposta diz se
    é para esperar de novo ou ler o relatório."""
    monkeypatch.setattr(modulo, "INTERVALO_DA_ESPERA_S", 0.0)
    monkeypatch.setattr(modulo, "ESPERA_MAXIMA_S", 0.0)
    _em_andamento(contexto, api_falsa)

    rodando = chamar(contexto, "ver_andamento", tarefa_id=7, aguardar=True).content[0].text
    assert "Ainda em andamento: chame ver_andamento com tarefa_id=7 e aguardar=true" in rodando

    api_falsa.tarefa["estado"] = "concluida"
    api_falsa.tarefa["relatorio_id"] = 35
    terminou = chamar(contexto, "ver_andamento", tarefa_id=7, aguardar=True).content[0].text
    assert "ver_relatorio (simulacao_id=1, relatorio_id=35)" in terminou

    sem_espera = chamar(contexto, "ver_andamento", tarefa_id=7).content[0].text
    assert "ver_relatorio" not in sem_espera, "o cartão pergunta sem aguardar"


def test_cartoes_levam_a_logo_do_preloader(contexto: Contexto) -> None:
    """A logo no alto dos cartões é a do preloader do painel, em contornos e com o degradê; o
    ícone do servidor é outra coisa (o favicon)."""
    for resultado in (
        chamar(contexto, "listar_restricoes"),
        chamar(contexto, "conferir_simulacao", **BATERIA),
    ):
        logos = [
            no["content"]
            for no in _nos(resultado.structured_content, "Svg")
            if 'aria-label="ARCO"' in no["content"]
        ]
        assert len(logos) == 1
        assert 'stop-color="#3ec46a"' in logos[0] and 'stop-color="#1f47b0"' in logos[0]
