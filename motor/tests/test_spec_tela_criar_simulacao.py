"""As folhas de `Configuracao` em caminho pontuado, para os testes que conferem campo a campo."""

from __future__ import annotations

from types import UnionType
from typing import Union, get_args, get_origin

from pydantic import BaseModel

from arco_motor.tipos import Configuracao


def _modelo_aninhado(anotacao: object) -> tuple[type[BaseModel], bool] | None:
    """(modelo, é lista) quando a anotação embrulha um modelo; None quando a folha é o campo."""
    origem = get_origin(anotacao)
    if origem is Union or origem is UnionType:
        for argumento in get_args(anotacao):
            if argumento is not type(None):
                achado = _modelo_aninhado(argumento)
                if achado is not None:
                    return achado
        return None
    if origem is list:
        (argumento,) = get_args(anotacao)
        e_modelo = isinstance(argumento, type) and issubclass(argumento, BaseModel)
        return (argumento, True) if e_modelo else None
    if isinstance(anotacao, type) and issubclass(anotacao, BaseModel):
        return anotacao, False
    return None


def campos(modelo: type[BaseModel] = Configuracao, prefixo: str = "") -> list[str]:
    """Folhas de `Configuracao` em caminho pontuado: bateria.potencia_mw, f.reposicoes[].ano."""
    achados: list[str] = []
    for nome, campo in modelo.model_fields.items():
        caminho = prefixo + nome
        aninhado = _modelo_aninhado(campo.annotation)
        if aninhado is None:
            achados.append(caminho)
        else:
            interno, lista = aninhado
            achados += campos(interno, f"{caminho}[]." if lista else f"{caminho}.")
    return achados
