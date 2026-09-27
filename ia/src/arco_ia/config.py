"""Modelo e parâmetros num lugar só, por papel, com a versão registrada em cada chamada.

Trocar de modelo é mudar aqui e reprocessar só o que veio do antigo. Por isso cada chamada
grava modelo e versão do prompt: sem isso não há como saber o que reprocessar
([ADR 0013](../../../docs/adr/0013-pilha-dos-agentes.md), item 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV = Path(__file__).resolve().parents[3] / ".env"
"""O `.env` da raiz, por caminho absoluto, como em `api/config.py`. Sem isso a chave só
funcionaria exportada no shell, e quem a põe no `.env` não entenderia por que não pegou."""

MODELO = "gemini-3.8-flash"
"""Um modelo só, por decisão. O que separa resposta certa de errada é a conferência por código,
que é determinística e pega erro com certeza — não concordância entre modelos, que parece
evidência e não é: modelos treinados em dado parecido erram junto."""

VERSAO_PROMPT = "1"
"""Versão do prompt do extrator. Sobe quando o prompt muda; junto com `MODELO`, diz o que
precisa ser reprocessado."""

ESFORCO = "low"
"""`thinking_level` do extrator. A tarefa é leitura de formato regular, não raciocínio longo."""

VARIAVEL_DA_CHAVE = "GEMINI_API_KEY"

TEMPO_LIMITE_S = 60
"""Quanto uma chamada ao modelo espera antes de desistir e contar como erro de rede. Sem limite,
uma requisição pendurada seguraria o relatório em `gerando` além do corte da API."""

NomeDoPapel = Literal["extrator", "analista", "explorador"]


@dataclass(frozen=True)
class Papel:
    """O que muda de um uso do modelo para outro: modelo, esforço e versão do prompt."""

    modelo: str
    esforco: str
    """`thinking_level` da Interactions API."""
    versao_prompt: str
    sem_chave: str
    """O que deixa de existir sem a chave, dito a quem chamou. Falhar calado não é opção."""


PAPEIS: dict[NomeDoPapel, Papel] = {
    "extrator": Papel(
        modelo=MODELO,
        esforco=ESFORCO,
        versao_prompt=VERSAO_PROMPT,
        sem_chave="o preparo da base fica incompleto, e restrição sem vínculo não entra no ranking",
    ),
    "analista": Papel(
        modelo=MODELO,
        # Escrever leitura sobre números prontos pede mais que ler um formato regular, e menos
        # que raciocínio longo. O conjunto de avaliação da task 17.5 é quem confirma ou troca.
        esforco="medium",
        versao_prompt="1",
        sem_chave="o relatório da simulação não é gerado",
    ),
    "explorador": Papel(
        modelo=MODELO,
        # Decidir a rodada é ler números prontos e escolher o que testar: mais que ler formato,
        # menos que raciocínio longo. O conjunto de avaliação da 17.16 confirma ou troca.
        esforco="medium",
        versao_prompt="1",
        sem_chave="a exploração por agente não roda; a árvore de referência roda sem modelo",
    ),
}
"""Modelo por papel. O analista e o explorador usam o mesmo modelo do extrator até o conjunto de
avaliação dizer outra coisa (tasks 17.5 e 17.16). O explorador chama o modelo pelo Strands, e
não por `chamada.chamar` (ADR 0013): o papel dele aqui diz modelo, esforço e versão do prompt,
e `cliente("explorador")` entrega o cliente."""


class Configuracao(BaseSettings):
    """Chaves lidas do ambiente ou do `.env` da raiz — nessa ordem, como manda o pydantic."""

    model_config = SettingsConfigDict(env_file=ENV, env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"


def chave() -> str:
    """A chave em uso, ou string vazia. Isolada para o teste não depender do `.env` da máquina."""
    return Configuracao().gemini_api_key.strip()


def cliente(papel: NomeDoPapel = "extrator") -> Any:
    """O cliente do SDK, ou `IndisponivelSemChave` dizendo o que o papel deixa de fazer.

    A retentativa própria do SDK sai: quem retenta é `chamada.chamar`, que sabe distinguir erro
    de rede de erro de conteúdo. As duas juntas multiplicariam as tentativas sem ninguém ver.
    """
    from arco_ia import IndisponivelSemChave

    achada = chave()
    if not achada:
        raise IndisponivelSemChave(
            f"{VARIAVEL_DA_CHAVE} não está no ambiente nem em {ENV}: sem ela "
            f"{PAPEIS[papel].sem_chave}"
        )
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=achada,
        http_options=types.HttpOptions(
            timeout=TEMPO_LIMITE_S * 1000,  # o SDK recebe milissegundos
            retry_options=types.HttpRetryOptions(attempts=0),
        ),
    )
