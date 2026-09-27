from arco_ia import IndisponivelSemChave


def test_pacote_importa() -> None:
    assert issubclass(IndisponivelSemChave, RuntimeError)
