from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from models.dados import carregar
from models.tipos import ConflitoOut, Disponibilidade, ListaDeSalas, Reserva, ReservaOut

FUSO = timezone(timedelta(hours=-3))
ABERTURA = time(8, 0)
FECHAMENTO = time(20, 0)
DURACAO_MAXIMA = timedelta(hours=2)

ERRO_SALA = "Sala inexistente: {sala}"
ERRO_JANELA = "Fora da janela de uso: a politica permite reservas entre 08:00 e 20:00"
ERRO_DURACAO = "Duracao acima do limite: a politica permite no maximo 2 horas"
ERRO_INTERVALO = "Intervalo invalido: fim deve ser posterior a inicio"
ERRO_SEM_ALTERNATIVA = "Sem alternativas disponiveis no intervalo"

_DADOS = carregar()
_RESERVAS: list[Reserva] = list(_DADOS.reservas)
_PROXIMO_ID = 3


def _achar_sala(sala_id: str):
    return next((sala for sala in _DADOS.salas if sala.id == sala_id), None)


def _instante(valor: object) -> datetime | None:
    if not isinstance(valor, str):
        return None
    try:
        instante = datetime.fromisoformat(valor)
    except ValueError:
        return None
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=FUSO)
    return instante.astimezone(FUSO)


def _erro(mensagem: str) -> dict:
    return {"erro": mensagem}


def _validar(sala: str, inicio: str, fim: str) -> dict | None:
    if _achar_sala(sala) is None:
        return _erro(ERRO_SALA.format(sala=sala))

    inicio_dt = _instante(inicio)
    fim_dt = _instante(fim)
    if inicio_dt is None or fim_dt is None or not fim_dt > inicio_dt:
        return _erro(ERRO_INTERVALO)

    dentro_janela = (
        inicio_dt.time() >= ABERTURA
        and fim_dt.time() <= FECHAMENTO
        and inicio_dt.date() == fim_dt.date()
    )
    if not dentro_janela:
        return _erro(ERRO_JANELA)

    if fim_dt - inicio_dt > DURACAO_MAXIMA:
        return _erro(ERRO_DURACAO)

    return None


def _conflitos(sala: str, inicio: str, fim: str) -> list[Reserva]:
    inicio_dt = _instante(inicio)
    fim_dt = _instante(fim)
    if inicio_dt is None or fim_dt is None:
        return []
    return [
        reserva
        for reserva in _RESERVAS
        if reserva.sala == sala
        and inicio_dt < _instante(reserva.fim)
        and fim_dt > _instante(reserva.inicio)
    ]


def alternativas(sala_id: str, inicio: str, fim: str) -> list[str]:
    """Salas livres no intervalo, com capacidade >= a pedida, no maximo tres.

    Ordenadas por capacidade crescente e, em empate, por id alfabetico.
    """
    sala = _achar_sala(sala_id)
    if sala is None:
        return []
    candidatas = [
        candidata
        for candidata in _DADOS.salas
        if candidata.id != sala_id
        and candidata.capacidade >= sala.capacidade
        and not _conflitos(candidata.id, inicio, fim)
    ]
    candidatas.sort(key=lambda c: (c.capacidade, c.id))
    return [c.id for c in candidatas[:3]]


def listar_salas() -> dict:
    return ListaDeSalas(salas=_DADOS.salas).model_dump()


def consultar(sala: str, inicio: str, fim: str) -> dict:
    falha = _validar(sala, inicio, fim)
    if falha is not None:
        return falha
    conflitos = _conflitos(sala, inicio, fim)
    return Disponibilidade(
        sala=sala,
        livre=not conflitos,
        conflitos=[
            ConflitoOut(
                id=reserva.id,
                inicio=reserva.inicio,
                fim=reserva.fim,
                responsavel=reserva.responsavel,
            )
            for reserva in conflitos
        ],
    ).model_dump()


def reservar(sala: str, inicio: str, fim: str, responsavel: str) -> dict:
    global _PROXIMO_ID

    falha = _validar(sala, inicio, fim)
    if falha is not None:
        return falha

    if _conflitos(sala, inicio, fim):
        opcoes = alternativas(sala, inicio, fim)
        if not opcoes:
            return _erro(ERRO_SEM_ALTERNATIVA)
        return {"alternativas": opcoes}

    reserva = Reserva(
        id=f"res-{_PROXIMO_ID:04d}",
        sala=sala,
        inicio=inicio,
        fim=fim,
        responsavel=responsavel,
    )
    _PROXIMO_ID += 1
    _RESERVAS.append(reserva)

    return ReservaOut(
        reserva=reserva.id,
        reservado=True,
        sala=reserva.sala,
        inicio=reserva.inicio,
        fim=reserva.fim,
        responsavel=reserva.responsavel,
        politica=_DADOS.politica_versao,
        motivo=None,
    ).model_dump()
