"""O MCP do ARCO: ferramentas escritas à mão, dois perfis, um processo.

Feature 17, marco 1, task 17.13 (spec em `docs/features/agentes/17-marco-1-mcp-e-explorador.md`,
ADR 0013). Cada ferramenta é um adaptador fino
para uma rota da API: as regras de 422 e 409 moram na API, e a descrição da ferramenta as diz
de antemão, para o modelo não tentar o que vai ser recusado. Toda resposta traz o texto
equivalente ao dado estruturado, para cliente que não mostra o estruturado.

**Perfis por escopo**, cada um num caminho:

- `/mcp`, o **chat** (Claude web, ChatGPT web): consultas, `conferir_simulacao`,
  `criar_simulacao`, `salvar_revisao` e o disparo — `explorar_variacoes`, `ver_andamento`,
  `gerar_relatorio`;
- `/explorador/mcp`, o **explorador**, por `localhost`: consultas, `disparar_lote` e
  `encerrar`. Não vê o disparo, e por isso não se chama em recursão; e não vê `salvar_revisao`,
  que aceita configuração inteira e salvaria como pessoa o que o agente decidiu, com preço ou
  taxa trocados. Revisão de agente só nasce pela rota de variação, que monta pelo motor.

**Quem põe o explorador para rodar é a API**, ao criar a tarefa (feature 17, marco 2, ADR 0015):
ela chama `POST /exploracoes/{tarefa_id}` neste processo, que entrega a tarefa ao explorador em
fundo. As ferramentas do chat só criam a tarefa; painel e chat disparam pelo mesmo caminho.

Aberto, sem autenticação, como a API (decidido em 2026-09-23).
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator, Callable, Coroutine, Iterator
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools.base import ToolResult
from pydantic import Field
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from arco_agentes import lote, resumos
from arco_agentes.api import ClienteDaApi, ErroDaApi
from arco_agentes.config import CAMINHO_DO_CHAT, CAMINHO_DO_EXPLORADOR, Configuracao
from arco_agentes.interfaces import cartoes
from arco_agentes.interfaces.icone import ICONES
from arco_agentes.interfaces.tema import APP

Perfil = Literal["chat", "explorador"]

IniciarExploracao = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]
"""Recebe a tarefa recém-criada e roda a exploração até o fim (task 17.14)."""

INTERVALO_DO_RELATORIO_S = 2.0
"""De quanto em quanto `encerrar` pergunta pelo relatório."""
ESPERA_DO_RELATORIO_S = 600.0
"""Quanto `encerrar` espera o relatório antes de encerrar sem ele. A API declara perdido o
relatório em `gerando` depois de 20 minutos; aqui a espera é menor, porque a tarefa não pode
ficar parada tanto tempo sem evento."""

INSTRUCOES = """\
MCP do ARCO, ferramenta que refaz os cortes de geração renovável registrados pelo ONS com uma
intervenção hipotética — bateria, circuito novo na linha, ou os dois — e calcula o efeito
técnico e financeiro. Todo número vem do cálculo da API; nenhum sai do modelo. O ARCO não
recomenda: ordena e compara revisões, e a decisão é de quem lê.

"""

INSTRUCOES_DO_CHAT = """\
Aqui, três ferramentas devolvem um cartão que o cliente desenha na conversa: listar_restricoes,
conferir_simulacao e explorar_variacoes; criar_simulacao e explorar_variacoes confirmada
devolvem o andamento da exploração, também em cartão. Com um cartão na tela, não repita em texto
o que ele mostra e não pergunte o que ele já pergunta.

Criar uma simulação é um processo só: ao confirmar, a simulação é criada e o agente do ARCO já
explora variações dela. Uma pergunta de cada vez e nesta ordem:
1. listar_restricoes; a pessoa escolhe a restrição no cartão, pelo botão Simular. Diga em uma
   frase para escolher no cartão e espere.
2. Com a restrição escolhida, pergunte a modalidade: bateria, circuito novo ou combinada.
3. Pergunte a alavanca que a modalidade pede (ver_restricao dá as subestações e as linhas),
   proponha um nome curto e chame conferir_simulacao. Se o ARCO recusar um valor, diga por quê
   e pergunte de novo.
4. O cartão mostra só esses campos e avisa que, ao confirmar, o agente explora; nada está
   salvo. Logo depois dele, pergunte com a pergunta de escolha do próprio cliente, quando
   houver: Confirmar ou Alterar valor.
5. Confirmar: chame criar_simulacao com os mesmos valores. Ela cria a simulação, dispara a
   exploração e devolve o andamento; diga em uma frase que começou. Alterar valor: pergunte o
   que mudar e chame conferir_simulacao de novo.
6. Acompanhe até o fim, sem esperar a pessoa perguntar: chame ver_andamento com aguardar=true,
   e de novo enquanto a exploração estiver em andamento, sem escrever nada entre as chamadas.
   Quando terminar, leia o relatório com ver_relatorio e conte em poucas linhas o que ele
   encontrou, com o link.
Se a pessoa disse o que quer descobrir, passe em `objetivo` a criar_simulacao; se disse um
limite de variações, passe em `teto`, igual nas duas ferramentas. Não chame salvar_revisao para
criar simulação.

Simulações salvas: listar_simulacoes e ver_revisao, só quando a pessoa pedir as que existem ou
quiser continuar uma. Não liste as salvas para quem pediu para criar.

Explorar de novo uma simulação salva (criada no painel, por exemplo): explorar_variacoes sem
confirmado mostra o aviso no cartão; pergunte Confirmar ou Cancelar e, com Confirmar, chame de
novo com confirmado=true e acompanhe até o fim, como no passo 6. O relatório sai no fim da
exploração, ou por gerar_relatorio.

Cliente que não desenha o cartão: o texto de cada ferramenta traz o mesmo conteúdo, e as
perguntas são na conversa.
"""
"""O que só o chat precisa saber: os cartões, e a ordem das perguntas. Sem isto, o modelo abria
a própria pergunta de modalidade ao lado da lista, antes de a pessoa escolher a restrição, e
listava as simulações salvas para quem pediu para criar uma. A simulação só passa a existir no
Confirmar, e a exploração parte junto: antes, o cartão mostra os campos que a criam e o aviso
dos agentes, e mais nada."""

TETO_MAXIMO = 30
"""Revisões por exploração: o teto duro das regras do explorador, que a API confere
(`TETO_MAXIMO` em `api/src/arco_api/tarefas.py`). A pessoa pode baixar, nunca subir."""

ESPERA_MAXIMA_S = 45.0
"""Quanto `ver_andamento` segura a resposta com `aguardar`: abaixo do tempo limite de uma chamada
de ferramenta nos clientes. Exploração mais longa pede outra chamada."""
INTERVALO_DA_ESPERA_S = 2.0

INSTRUCOES_DO_EXPLORADOR = """\
Aqui se explora uma simulação já salva: consultas para ler as revisões, disparar_lote para cada
rodada e encerrar no fim.
"""


@dataclass
class Contexto:
    """O que as ferramentas usam: a API, a configuração e quem roda a exploração."""

    api: ClienteDaApi
    config: Configuracao
    iniciar_exploracao: IniciarExploracao | None = None
    """`None` quando o explorador não pode rodar neste processo: `explorar_variacoes` recusa
    antes de criar a tarefa, e nenhuma tarefa fica parada até virar `falhou`."""
    explorador_indisponivel: str = "o explorador não está disponível neste servidor"
    """O porquê da recusa quando `iniciar_exploracao` é `None`: sem chave do modelo, por
    exemplo."""
    rodando: dict[int, asyncio.Task[None]] = field(default_factory=dict)
    """As explorações em curso, pelo id da tarefa. Guardadas para o coletor não encerrar a
    tarefa no meio, e para o mesmo disparo não rodar duas vezes."""


def _falha(erro: ErroDaApi) -> ToolError:
    return ToolError(f"{erro.status}: {erro.mensagem}")


def _proximo_passo(tarefa: dict[str, Any]) -> str:
    """O que o modelo faz depois de uma espera: esperar de novo, ou ler o relatório. Dito na
    resposta, porque nem todo cliente entrega as instruções do servidor ao modelo."""
    if tarefa["estado"] == "em_andamento":
        return (
            f"\n\nAinda em andamento: chame ver_andamento com tarefa_id={tarefa['id']} e "
            "aguardar=true de novo."
        )
    if tarefa.get("relatorio_id"):
        return (
            f"\n\nTerminou. Leia o relatório com ver_relatorio (simulacao_id="
            f"{tarefa['simulacao_id']}, relatorio_id={tarefa['relatorio_id']}) e conte em poucas "
            "linhas o que ele encontrou."
        )
    return "\n\nTerminou sem relatório; conte à pessoa o motivo acima."


def _soltar_explorador(contexto: Contexto, tarefa: dict[str, Any]) -> None:
    """Entrega a tarefa criada ao explorador, em tarefa de fundo, guardada para o coletor não a
    encerrar no meio."""
    assert contexto.iniciar_exploracao is not None
    tarefa_id = int(tarefa["id"])
    rodando = asyncio.create_task(contexto.iniciar_exploracao(tarefa))
    contexto.rodando[tarefa_id] = rodando
    rodando.add_done_callback(lambda _: contexto.rodando.pop(tarefa_id, None))


async def disparar_exploracao(contexto: Contexto, tarefa_id: int) -> tuple[int, dict[str, Any]]:
    """O que `POST /exploracoes/{tarefa_id}` responde, com o status: a API chama ao criar a
    tarefa. Confere a tarefa na API antes de soltar o explorador, e não solta duas vezes."""
    ja_roda = 409, {"detail": f"a exploração {tarefa_id} já roda neste processo"}
    if contexto.iniciar_exploracao is None:
        return 503, {"detail": contexto.explorador_indisponivel}
    if tarefa_id in contexto.rodando:
        return ja_roda
    try:
        tarefa = await contexto.api.ver_tarefa(tarefa_id)
    except ErroDaApi as erro:
        return (404 if erro.status == 404 else 502), {"detail": erro.mensagem}
    if tarefa["estado"] != "em_andamento":
        return 409, {"detail": f"a exploração {tarefa_id} já terminou: {tarefa['estado']}"}
    # De novo depois da espera: outro disparo da mesma tarefa pode ter passado por aqui nela.
    if tarefa_id in contexto.rodando:
        return ja_roda
    _soltar_explorador(contexto, tarefa)
    return 202, {"tarefa_id": tarefa_id}


def _escolhas(
    modalidade: str,
    cenario: str,
    potencia_mw: float | None,
    capacidade_mwh: float | None,
    subestacao: str | None,
    cod_equipamento: str | None,
    ganho_limite_mw: float | None,
) -> dict[str, Any]:
    """O que a pessoa escolhe para criar a simulação, como `GET /restricoes/{id}/montar` pede."""
    return {
        "modalidade": modalidade,
        "cenario": cenario,
        "potencia_mw": potencia_mw,
        "capacidade_mwh": capacidade_mwh,
        "subestacao": subestacao,
        "cod_equipamento": cod_equipamento,
        "ganho_limite_mw": ganho_limite_mw,
    }


def criar_servidor(perfil: Perfil, contexto: Contexto) -> FastMCP:
    """O servidor de um perfil. As consultas são as mesmas nos dois."""
    instrucoes = INSTRUCOES + (INSTRUCOES_DO_CHAT if perfil == "chat" else INSTRUCOES_DO_EXPLORADOR)
    servidor = FastMCP(f"ARCO ({perfil})", instructions=instrucoes, icons=ICONES)
    api = contexto.api
    somente_leitura = {"readOnlyHint": True, "openWorldHint": False}
    escreve = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False}

    # Consultas ---------------------------------------------------------------------------

    chat = perfil == "chat"

    @servidor.tool(annotations=somente_leitura, tags={"consulta"}, app=APP if chat else None)
    async def listar_restricoes(
        fonte: Literal["eolica", "solar", "ambas"] = "eolica",
        limite: Annotated[int, Field(ge=1, le=50)] = 10,
    ) -> ToolResult:
        """As restrições do ranking de energia cortada, da maior para a menor, com o id de cada
        uma. Uma simulação é sempre de uma restrição. `409` se a API ainda não tem snapshot."""
        try:
            texto, dados = resumos.restricoes(await api.listar_restricoes(fonte, limite))
        except ErroDaApi as erro:
            raise _falha(erro) from erro
        # No chat, o dado estruturado é o cartão, e o texto leva o mesmo conteúdo ao modelo.
        if not chat:
            return ToolResult(content=texto, structured_content=dados)
        return ToolResult(
            content=texto + cartoes.NO_CARTAO_DA_LISTA,
            structured_content=cartoes.lista_de_restricoes(dados),
        )

    @servidor.tool(annotations=somente_leitura, tags={"consulta"})
    async def ver_restricao(
        restricao_id: str, fonte: Literal["eolica", "solar", "ambas"] = "eolica"
    ) -> ToolResult:
        """Uma restrição: as linhas dela com papel e cadastro, e as subestações onde uma bateria
        pode se conectar. Só a linha `monitorado` recebe circuito novo; a `contingenciado` é a
        que se supõe perder. `404` se a restrição não existe."""
        try:
            texto, dados = resumos.restricao(await api.ver_restricao(restricao_id, fonte))
        except ErroDaApi as erro:
            raise _falha(erro) from erro
        return ToolResult(content=texto, structured_content=dados)

    @servidor.tool(annotations=somente_leitura, tags={"consulta"})
    async def listar_simulacoes(restricao_id: str | None = None) -> ToolResult:
        """As simulações salvas, com as revisões de cada uma: procedência, nota, de onde cada
        revisão nasceu, o que mudou, VPL e energia recuperada. Filtra por restrição."""
        try:
            texto, dados = resumos.simulacoes(await api.listar_simulacoes(restricao_id))
        except ErroDaApi as erro:
            raise _falha(erro) from erro
        return ToolResult(content=texto, structured_content={"simulacoes": dados})

    @servidor.tool(annotations=somente_leitura, tags={"consulta"})
    async def ver_revisao(revisao_id: int) -> ToolResult:
        """Uma revisão, sem as séries: configuração, resultado (energia, fração recuperada, VPL,
        TIR, paybacks, custo por MWh), diagnósticos (bateria cheia com corte sobrando, episódios
        que a pegaram com carga, corte que sobrou por hora do dia), avisos, premissas com
        status, as outras revisões da simulação e onde payback e TIR cruzam entre elas. `404` se
        a revisão não existe."""
        try:
            texto, dados = resumos.revisao(await api.ver_revisao(revisao_id))
        except ErroDaApi as erro:
            raise _falha(erro) from erro
        return ToolResult(content=texto, structured_content=dados)

    @servidor.tool(annotations=somente_leitura, tags={"consulta"})
    async def ver_relatorio(simulacao_id: int, relatorio_id: int | None = None) -> ToolResult:
        """O relatório de uma simulação: estado (`gerando`, `pronto`, `barrado`, `falhou`), a
        prosa conferida por código quando pronto, as fronteiras e o link no painel. Sem
        `relatorio_id`, o mais novo. `404` se a simulação ou o relatório não existem."""
        try:
            if relatorio_id is None:
                lista = await api.listar_relatorios(simulacao_id)
                if not lista:
                    return ToolResult(
                        content=f"A simulação {simulacao_id} não tem relatório. Peça com "
                        "gerar_relatorio.",
                        structured_content={"simulacao_id": simulacao_id, "relatorios": []},
                    )
                relatorio_id = int(lista[0]["id"])
            completo = await api.ver_relatorio(simulacao_id, relatorio_id)
        except ErroDaApi as erro:
            raise _falha(erro) from erro
        link = (
            f"{contexto.config.painel_url.rstrip('/')}/simulacoes/{simulacao_id}/relatorios/"
            f"{relatorio_id}"
        )
        texto, dados = resumos.relatorio(completo, link)
        return ToolResult(content=texto, structured_content=dados)

    if perfil == "chat":
        _acoes_do_chat(servidor, contexto, escreve)
        _disparo(servidor, contexto, escreve, somente_leitura)
    else:
        _do_explorador(servidor, contexto, escreve)
    return servidor


def _acoes_do_chat(servidor: FastMCP, contexto: Contexto, escreve: dict[str, Any]) -> None:
    api = contexto.api

    @servidor.tool(
        annotations={"readOnlyHint": True, "openWorldHint": False}, tags={"acao"}, app=APP
    )
    async def conferir_simulacao(
        restricao_id: str,
        nome: Annotated[str, Field(min_length=1)],
        modalidade: Literal["bateria", "equipamento", "combinada"],
        cenario: Literal["conservador", "referencia", "otimista"] = "referencia",
        potencia_mw: Annotated[float | None, Field(gt=0)] = None,
        capacidade_mwh: Annotated[float | None, Field(gt=0)] = None,
        subestacao: str | None = None,
        cod_equipamento: str | None = None,
        ganho_limite_mw: Annotated[float | None, Field(ge=0)] = None,
        teto: Annotated[int, Field(ge=1, le=TETO_MAXIMO)] = TETO_MAXIMO,
    ) -> ToolResult:
        """Mostra à pessoa a simulação nova para ela confirmar, sem salvar nada: só os campos
        que a criam — nome, restrição, modalidade, cenário e a alavanca — e o aviso de que, ao
        confirmar, o agente do ARCO explora até `teto` variações dela. Proponha o `nome`.
        Bateria pede potência, capacidade e subestação; circuito pede a linha
        (`cod_equipamento`) e o ganho de limite; combinada pede os dois.

        Antes de mostrar, o ARCO confere os valores: `422` quando falta o que a modalidade
        pede, quando a linha é a contingenciada ("não recebe circuito novo: o método só modela
        adição de circuito na linha monitorada, e esta é a que se supõe perder"), quando a
        subestação não é terminal de linha da restrição, ou quando potência ou ganho passam da
        capacidade de longa duração da linha no cadastro. Recusa também quando o explorador não
        pode rodar, porque criar pelo chat já explora. Depois do cartão, pergunte Confirmar ou
        Alterar valor; só com Confirmar chame criar_simulacao."""
        if contexto.iniciar_exploracao is None:
            raise ToolError(f"{contexto.explorador_indisponivel}; nada foi criado")
        escolhas = _escolhas(
            modalidade,
            cenario,
            potencia_mw,
            capacidade_mwh,
            subestacao,
            cod_equipamento,
            ganho_limite_mw,
        )
        try:
            # A montagem só confere os valores: nada dela aparece, porque a simulação ainda não
            # existe.
            await api.montar(restricao_id, escolhas)
            restricao = await api.ver_restricao(restricao_id, "eolica")
        except ErroDaApi as erro:
            raise _falha(erro) from erro
        escolhas["nome"] = nome.strip()
        return ToolResult(
            content=resumos.nova_simulacao(escolhas, restricao)
            + f"\nAo confirmar, o agente do ARCO testa até {teto} variações, em rodadas."
            + cartoes.NO_CARTAO_DA_NOVA_SIMULACAO,
            structured_content=cartoes.cartao_da_nova_simulacao(escolhas, restricao, teto),
        )

    @servidor.tool(annotations=escreve, tags={"acao"}, app=APP)
    async def criar_simulacao(
        restricao_id: str,
        nome: Annotated[str, Field(min_length=1)],
        modalidade: Literal["bateria", "equipamento", "combinada"],
        cenario: Literal["conservador", "referencia", "otimista"] = "referencia",
        potencia_mw: Annotated[float | None, Field(gt=0)] = None,
        capacidade_mwh: Annotated[float | None, Field(gt=0)] = None,
        subestacao: str | None = None,
        cod_equipamento: str | None = None,
        ganho_limite_mw: Annotated[float | None, Field(ge=0)] = None,
        teto: Annotated[int, Field(ge=1, le=TETO_MAXIMO)] = TETO_MAXIMO,
        objetivo: Annotated[str | None, Field(max_length=2000)] = None,
        nota: Annotated[str | None, Field(max_length=1000)] = None,
    ) -> ToolResult:
        """Cria a simulação nova, pela pessoa (procedência `por_pessoa`), e já dispara a
        exploração dela: só depois que ela escolher Confirmar, e com os mesmos valores que
        conferir_simulacao mostrou. O ARCO monta a configuração a partir desses valores; nada
        além deles entra. A exploração parte da revisão criada, com até `teto` variações, e
        procura o `objetivo` que a pessoa disse; sem ele, percorre a faixa da alavanca e mostra
        onde o corte que sobra, o VPL, a TIR e o payback mudam. `nota` é o porquê, se a pessoa
        disse. Devolve o andamento da exploração; em seguida, acompanhe com ver_andamento e
        aguardar=true até ela terminar, e leia o relatório.

        `422` pelas mesmas conferências de conferir_simulacao; `409` se a restrição não tem
        vínculo autorizado com o cadastro. Se o explorador não pode rodar, recusa antes de
        criar; se a exploração não começa depois de a simulação salva, diz por quê, e a
        simulação fica."""
        if contexto.iniciar_exploracao is None:
            raise ToolError(f"{contexto.explorador_indisponivel}; nada foi criado")
        escolhas = _escolhas(
            modalidade,
            cenario,
            potencia_mw,
            capacidade_mwh,
            subestacao,
            cod_equipamento,
            ganho_limite_mw,
        )
        try:
            restricao = await api.ver_restricao(restricao_id, "eolica")
            montada = await api.montar(restricao_id, escolhas)
            salva = await api.salvar(
                {
                    "restricao_id": restricao_id,
                    "nome": nome.strip(),
                    "configuracao": montada["configuracao"],
                    "procedencia": "por_pessoa",
                    "nota": (nota or "").strip() or None,
                }
            )
        except ErroDaApi as erro:
            raise _falha(erro) from erro
        simulacao_id, revisao_id = salva["simulacao_id"], salva["id"]
        criada = f"Simulação {simulacao_id} criada, com a revisão {revisao_id}"
        pedido = (objetivo or "").strip() or resumos.pedido_padrao(
            restricao, revisao_id, montada["configuracao"]
        )
        try:
            tarefa = await api.criar_tarefa(
                simulacao_id,
                {"pedido": pedido, "teto": teto, "revisao_partida_id": revisao_id},
            )
        except ErroDaApi as erro:
            return ToolResult(
                content=f"{criada}, mas a exploração não começou ({erro.status}: "
                f"{erro.mensagem}). A simulação fica salva; diga isso à pessoa.",
                structured_content={
                    "simulacao_id": simulacao_id,
                    "revisao_id": revisao_id,
                    "exploracao": None,
                },
            )
        # Quem põe o explorador para rodar é a API, ao criar a tarefa.
        link = contexto.config.link_ver_processamento(simulacao_id, tarefa["id"])
        texto, _ = resumos.andamento(tarefa, link)
        return ToolResult(
            content=f"{criada}, e a exploração {tarefa['id']} disparada. Pedido: {pedido}\n"
            + texto
            + cartoes.no_cartao_de_andamento(tarefa["id"]),
            structured_content=cartoes.cartao_de_andamento(tarefa, link),
        )

    @servidor.tool(annotations=escreve, tags={"acao"})
    async def salvar_revisao(
        configuracao: Annotated[
            dict[str, Any],
            Field(description="A `configuracao` inteira, como ver_revisao devolve."),
        ],
        restricao_id: str | None = None,
        nome: str | None = None,
        pergunta: str | None = None,
        simulacao_id: int | None = None,
        revisao_base_id: int | None = None,
        nota: Annotated[str | None, Field(max_length=1000)] = None,
        fonte: Literal["eolica", "solar", "ambas"] = "eolica",
    ) -> ToolResult:
        """Calcula e salva, **pela pessoa** (procedência `por_pessoa`): só depois de ela ver a
        configuração e concordar. Para criar simulação a partir das escolhas, o caminho é
        conferir_simulacao e criar_simulacao. Aqui, para uma simulação nova, `restricao_id` e
        `nome`; para uma revisão de simulação existente, `simulacao_id` — exatamente um dos
        dois, senão `422`. `revisao_base_id` diz de qual revisão esta nasce (da mesma simulação,
        senão `422`); sem ele, nasce da mais nova. `nota` é o porquê, em texto.

        `422` também pelas conferências de conferir_simulacao (linha contingenciada, subestação,
        teto pela capacidade). `404` se a simulação não existe; `409` se a restrição não tem
        vínculo autorizado com o cadastro."""
        pedido: dict[str, Any] = {
            "configuracao": configuracao,
            "fonte": fonte,
            "procedencia": "por_pessoa",
            "nome": nome or "Simulação pelo chat",
            "nota": nota,
            "pergunta": pergunta,
        }
        if simulacao_id is not None:
            pedido |= {"simulacao_id": simulacao_id, "revisao_base_id": revisao_base_id}
        else:
            pedido["restricao_id"] = restricao_id
        try:
            salva = await api.salvar(pedido)
            texto, dados = resumos.revisao(await api.ver_revisao(salva["id"]))
        except ErroDaApi as erro:
            raise _falha(erro) from erro
        return ToolResult(content="Salva. " + texto, structured_content=dados)


def _disparo(
    servidor: FastMCP,
    contexto: Contexto,
    escreve: dict[str, Any],
    somente_leitura: dict[str, Any],
) -> None:
    api, config = contexto.api, contexto.config

    @servidor.tool(annotations=escreve, tags={"disparo"}, app=APP)
    async def explorar_variacoes(
        simulacao_id: int,
        pedido: Annotated[str, Field(min_length=1, max_length=2000)],
        teto: Annotated[int, Field(ge=1, le=TETO_MAXIMO)] = TETO_MAXIMO,
        revisao_partida_id: int | None = None,
        alavancas: list[
            Literal[
                "bateria.potencia_mw",
                "bateria.duracao_horas",
                "bateria.subestacao",
                "equipamento.ganho_limite_mw",
            ]
        ]
        | None = None,
        confirmado: bool = False,
    ) -> ToolResult:
        """Explora variações da alavanca física de uma simulação que já existe (criada no
        painel, por exemplo; a criada pelo chat já sai explorando): um agente decide rodadas de
        variações, que rodam em paralelo e viram revisões; no fim sai o relatório.

        **Sem `confirmado=true`, não dispara:** o cartão só avisa que o agente vai explorar, e o
        texto traz para você o resumo — a configuração de partida, o que vai variar e em que
        faixa, o que fica fixo (preço da energia, taxa de desconto, cenário, custo unitário) e
        o teto de revisões. Não repita o resumo: pergunte Confirmar ou Cancelar, e só chame de
        novo com `confirmado=true` depois que a pessoa confirmar. Ela pode baixar o teto (até
        30) e estreitar as `alavancas` ("varia só a potência"), nunca alargar a faixa.

        Com a confirmação, cria a exploração e devolve na hora o andamento e o link Ver
        processamento; acompanhe por ver_andamento, com aguardar=true, até o fim. `409` se já
        há exploração em andamento nesta simulação, com o id dela; `422` se a revisão de partida
        não é da simulação ou a alavanca não é da modalidade; `503` se o explorador não começou,
        e aí a exploração já sai encerrada, sem travar a simulação."""
        try:
            if not confirmado:
                resumo = await api.resumo_da_exploracao(
                    simulacao_id, revisao_partida_id, list(alavancas or [])
                )
                return ToolResult(
                    content=_texto_do_resumo(resumo, teto) + cartoes.NO_CARTAO_DA_EXPLORACAO,
                    structured_content=cartoes.cartao_de_exploracao(simulacao_id, teto),
                )
            if contexto.iniciar_exploracao is None:
                raise ToolError(f"{contexto.explorador_indisponivel}; nada foi criado")
            tarefa = await api.criar_tarefa(
                simulacao_id,
                {
                    "pedido": pedido,
                    "teto": teto,
                    "revisao_partida_id": revisao_partida_id,
                    "alavancas": alavancas,
                },
            )
        except ErroDaApi as erro:
            raise _falha(erro) from erro
        # Quem põe o explorador para rodar é a API, ao criar a tarefa.
        link = config.link_ver_processamento(simulacao_id, tarefa["id"])
        texto, _ = resumos.andamento(tarefa, link)
        return ToolResult(
            content="Exploração disparada. " + texto + cartoes.no_cartao_de_andamento(tarefa["id"]),
            structured_content=cartoes.cartao_de_andamento(tarefa, link),
        )

    @servidor.tool(annotations=somente_leitura, tags={"disparo"})
    async def ver_andamento(tarefa_id: int, aguardar: bool = False) -> ToolResult:
        """O andamento de uma exploração: estado, quantas revisões prontas, quantas trabalhando
        e recusadas, em quantas rodadas, o limite, o relatório quando pedido e o link Ver
        processamento. A contagem é da API, pelos eventos. `404` se a exploração não existe.

        Com `aguardar=true`, segura a resposta até a exploração terminar ou até 45 segundos, o
        que vier primeiro. É assim que se acompanha depois de disparar: chame de novo enquanto
        ela estiver em andamento e, quando terminar, leia o relatório com ver_relatorio."""
        try:
            tarefa = await api.ver_tarefa(tarefa_id)
            if aguardar:
                prazo = time.monotonic() + ESPERA_MAXIMA_S
                while tarefa["estado"] == "em_andamento" and time.monotonic() < prazo:
                    await asyncio.sleep(INTERVALO_DA_ESPERA_S)
                    tarefa = await api.ver_tarefa(tarefa_id)
        except ErroDaApi as erro:
            raise _falha(erro) from erro
        texto, dados = resumos.andamento(
            tarefa, config.link_ver_processamento(tarefa["simulacao_id"], tarefa_id)
        )
        if aguardar:
            texto += _proximo_passo(tarefa)
        return ToolResult(content=texto, structured_content=dados)

    @servidor.tool(annotations=escreve, tags={"disparo"})
    async def gerar_relatorio(simulacao_id: int) -> ToolResult:
        """Pede o relatório de uma simulação, sobre as revisões que ela tem agora. Responde na
        hora, em `gerando`; leia com ver_relatorio em alguns segundos. O relatório compila e não
        recomenda. `404` se a simulação não existe; `409` se já há um em geração."""
        try:
            criado = await api.pedir_relatorio(simulacao_id)
        except ErroDaApi as erro:
            raise _falha(erro) from erro
        return ToolResult(
            content=f"Relatório {criado['id']} pedido, em geração. Leia com ver_relatorio("
            f"simulacao_id={simulacao_id}, relatorio_id={criado['id']}).",
            structured_content=criado,
        )


def _do_explorador(servidor: FastMCP, contexto: Contexto, escreve: dict[str, Any]) -> None:
    api = contexto.api

    @servidor.tool(annotations=escreve, tags={"explorador"})
    async def disparar_lote(
        tarefa_id: int,
        revisao_partida_id: Annotated[
            int, Field(description="De qual revisão da simulação as variações nascem.")
        ],
        variacoes: Annotated[
            list[lote.VariacaoPedida],
            Field(min_length=1, description="Até 10. Cada uma muda uma alavanca só."),
        ],
        porque: Annotated[
            str,
            Field(
                min_length=1,
                max_length=1000,
                description="Por que esta rodada, em texto. Vira a nota de cada revisão. Sem "
                "número de resultado: os números estão nas revisões.",
            ),
        ],
    ) -> ToolResult:
        """Roda uma rodada: as variações nascem todas de `revisao_partida_id`, em paralelo, e
        cada uma vira revisão com a nota. Devolve cada revisão com resultado e diagnósticos, e
        onde payback e TIR cruzam entre as revisões.

        Recusa com o motivo, sem calcular: mais de 10 variações, valor fora da faixa permitida
        da exploração, alavanca que a exploração não varia, variação repetida no lote, e o que
        passa do teto de revisões. A API recusa ainda configuração igual à de revisão que já
        existe (`409`), teto atingido ao salvar (`409`) e as conferências de salvar (`422`).
        Preço, taxa, cenário e custo unitário não variam: são os da revisão de partida."""
        try:
            feito = await lote.disparar(api, tarefa_id, revisao_partida_id, variacoes, porque)
        except ErroDaApi as erro:
            raise _falha(erro) from erro
        return ToolResult(content=lote.texto(feito), structured_content=feito)

    @servidor.tool(annotations=escreve, tags={"explorador"})
    async def encerrar(
        tarefa_id: int,
        motivo: Annotated[
            str,
            Field(
                min_length=1,
                max_length=1000,
                description="Por que parar: o pedido está respondido entre as revisões, ou a "
                "última rodada não mexeu na métrica pedida.",
            ),
        ],
    ) -> ToolResult:
        """Encerra a exploração, bem: pede o relatório sobre as revisões da simulação, espera
        ele terminar e fecha a tarefa como concluída, com o motivo. `409` se a exploração já
        terminou."""
        try:
            fim = await encerrar_exploracao(api, tarefa_id, motivo)
        except ErroDaApi as erro:
            raise _falha(erro) from erro
        return ToolResult(
            content=f"Exploração {tarefa_id} concluída: {motivo} Relatório "
            f"{fim['relatorio_id']}: {fim['estado_do_relatorio']}.",
            structured_content=fim,
        )


async def encerrar_exploracao(api: ClienteDaApi, tarefa_id: int, motivo: str) -> dict[str, Any]:
    """Relatório pedido, esperado e anunciado, e só então `tarefa_terminada`, que é sempre o
    último evento (contrato da tela, `17-ver-processamento-contrato.md`)."""
    tarefa = await api.ver_tarefa(tarefa_id)
    if tarefa["estado"] != "em_andamento":
        raise ErroDaApi(409, f"a exploração {tarefa_id} já terminou: {tarefa['estado']}")
    simulacao_id = tarefa["simulacao_id"]
    try:
        relatorio_id = int((await api.pedir_relatorio(simulacao_id))["id"])
    except ErroDaApi as erro:
        if erro.status != 409:
            raise
        # Já havia um em geração, pedido pela pessoa: é ele que a exploração acompanha.
        relatorio_id = int((await api.listar_relatorios(simulacao_id))[0]["id"])
    await api.registrar_evento(
        tarefa_id, {"tipo": "relatorio_pedido", "relatorio_id": relatorio_id}
    )
    estado = "gerando"
    esperado = 0.0
    while estado == "gerando" and esperado < ESPERA_DO_RELATORIO_S:
        await asyncio.sleep(INTERVALO_DO_RELATORIO_S)
        esperado += INTERVALO_DO_RELATORIO_S
        estado = (await api.ver_relatorio(simulacao_id, relatorio_id))["estado"]
    if estado != "gerando":
        await api.registrar_evento(
            tarefa_id, {"tipo": "relatorio_pronto", "relatorio_id": relatorio_id, "estado": estado}
        )
    await api.registrar_evento(
        tarefa_id, {"tipo": "tarefa_terminada", "estado": "concluida", "motivo": motivo}
    )
    return {"tarefa_id": tarefa_id, "relatorio_id": relatorio_id, "estado_do_relatorio": estado}


def _folhas(valor: Any, prefixo: str = "") -> list[tuple[str, Any]]:
    if not isinstance(valor, dict):
        return [(prefixo, valor)]
    saida: list[tuple[str, Any]] = []
    for chave, dentro in valor.items():
        saida += _folhas(dentro, f"{prefixo}.{chave}" if prefixo else chave)
    return saida


def _texto_do_resumo(resumo: dict[str, Any], teto: int) -> str:
    faixa = resumo["faixa"]
    varia = []
    nomes = {
        "potencia_mw": ("potência da bateria", "MW"),
        "duracao_horas": ("duração da bateria", "h"),
        "ganho_limite_mw": ("ganho de limite do circuito", "MW"),
    }
    for campo, (nome, unidade) in nomes.items():
        if faixa.get(campo):
            limite = faixa[campo]
            varia.append(
                f"{nome}, de {resumos.numero_br(limite['minimo'])} a "
                f"{resumos.numero_br(limite['maximo'])} {unidade}"
            )
    if faixa.get("subestacoes"):
        varia.append(f"subestação de conexão, entre {', '.join(faixa['subestacoes'])}")
    fixas = resumo["condicoes_fixas"]
    custos = "; ".join(
        f"{c['id']} {resumos.numero_br(c['valor'])} {c.get('unidade') or ''} ({c['status']})"
        for c in fixas["custos_unitarios"]
    )
    campos = "\n".join(
        f"  - {caminho}: {valor}" for caminho, valor in _folhas(resumo["configuracao"])
    )
    avisos = " ".join(a["mensagem"] for a in faixa.get("avisos", []))
    return (
        "Antes de disparar, confirme com a pessoa.\n"
        f"Parte da revisão {resumo['revisao_partida_id']} da simulação {resumo['simulacao_id']}: "
        f"{resumos.alavanca(resumo['configuracao'])}. Configuração de partida:\n{campos}\n"
        f"Vai variar: {'; '.join(varia) or 'nada'}.\n"
        f"Fica fixo: cenário {fixas['cenario']}, taxa de desconto "
        f"{resumos.porcentagem(fixas['taxa_desconto_aa'])} ao ano, preço da energia "
        f"{resumos.reais(fixas['preco_energia_reais_mwh'])}/MWh"
        f"{' (premissa preco_energia)' if fixas['preco_da_premissa'] else ''}, custo unitário "
        f"{custos or 'da partida'}.\n"
        f"Teto: {teto} revisões (máximo {resumo['teto_maximo']}).\n"
        + (f"Avisos: {avisos}\n" if avisos else "")
        + "Para disparar, chame explorar_variacoes de novo com confirmado=true."
    )


def criar_app(contexto: Contexto) -> Starlette:
    """Os dois perfis num processo só, cada um no seu caminho, mais `/saude` e a rota por onde a
    API dispara a exploração."""
    chat = criar_servidor("chat", contexto).http_app(path=CAMINHO_DO_CHAT)
    explorador_caminho = CAMINHO_DO_EXPLORADOR.removesuffix(CAMINHO_DO_CHAT)
    explorador = criar_servidor("explorador", contexto).http_app(path=CAMINHO_DO_CHAT)

    @contextlib.asynccontextmanager
    async def ciclo(app: Starlette) -> AsyncIterator[None]:
        async with chat.lifespan(app), explorador.lifespan(app):
            try:
                yield
            finally:
                for rodando in list(contexto.rodando.values()):
                    rodando.cancel()
                await contexto.api.fechar()

    async def saude(_: Request) -> JSONResponse:
        return JSONResponse(
            {"status": "ok", "chat": CAMINHO_DO_CHAT, "explorador": CAMINHO_DO_EXPLORADOR}
        )

    async def disparar(pedido: Request) -> JSONResponse:
        status, corpo = await disparar_exploracao(contexto, pedido.path_params["tarefa_id"])
        return JSONResponse(corpo, status_code=status)

    return Starlette(
        routes=[
            Route("/saude", saude),
            Route("/exploracoes/{tarefa_id:int}", disparar, methods=["POST"]),
            Mount(explorador_caminho, app=explorador),
            Mount("/", app=chat),
        ],
        lifespan=ciclo,
    )


@contextlib.contextmanager
def em_segundo_plano(contexto: Contexto, porta: int = 0) -> Iterator[str]:
    """O app num `uvicorn` em outra thread, em `127.0.0.1`: a URL base enquanto o bloco durar.
    Porta zero escolhe uma livre. É o que a CLI usa quando não há MCP no ar, e o teste também."""
    import socket
    import threading
    import time

    import httpx
    import uvicorn

    if porta == 0:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            porta = int(s.getsockname()[1])
    servidor = uvicorn.Server(
        uvicorn.Config(criar_app(contexto), host="127.0.0.1", port=porta, log_level="warning")
    )
    linha = threading.Thread(target=servidor.run, daemon=True)
    linha.start()
    base = f"http://127.0.0.1:{porta}"
    for _ in range(200):
        try:
            if httpx.get(f"{base}/saude", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    try:
        yield base
    finally:
        servidor.should_exit = True
        linha.join(timeout=10)
