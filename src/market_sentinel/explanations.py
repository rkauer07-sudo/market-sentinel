"""Plain-language explanations for technical scenarios.

The scanner remains deterministic and read-only.  These explanations translate
the agent's structured evidence; they never invent a probability or a trade.
"""

from __future__ import annotations

from typing import Any


def _value(item: Any, name: str, default=None):
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def _price(value: float) -> str:
    return f"{float(value):.8g}"


def explain_candidate(candidate: Any) -> dict[str, str]:
    """Translate a potential setup into short, cautious Portuguese."""
    scenario = str(_value(candidate, "scenario", "Cenário técnico em formação"))
    direction = str(_value(candidate, "direction", "LONG"))
    timeframe = str(_value(candidate, "timeframe", ""))
    trigger = float(_value(candidate, "trigger_price", 0))
    invalidation = float(_value(candidate, "invalidation_price", 0))
    target = float(_value(candidate, "target", 0))
    readiness = int(_value(candidate, "readiness", 0))
    lower = scenario.lower()

    if "rompimento" in lower:
        title = "O preço está encostando numa barreira importante."
        summary = (f"Ainda não houve rompimento. O cenário só ganha força se o candle de {timeframe} "
                   f"fechar acima de {_price(trigger)} com participação de volume.")
        watch_for = f"Espere o fechamento acima de {_price(trigger)}; tocar o nível não basta."
    elif "perda" in lower or direction == "SHORT":
        title = "O suporte está sendo pressionado, mas ainda pode segurar."
        summary = (f"A ideia é de queda somente se o candle de {timeframe} perder {_price(trigger)} "
                   "e não recuperar o nível no reteste.")
        watch_for = f"Confirme a perda de {_price(trigger)} antes de considerar o movimento."
    else:
        title = "O preço está perto de uma região onde compradores podem reagir."
        summary = (f"A reação ainda não aconteceu. Ela fica mais clara se o candle de {timeframe} "
                   f"defender a região e fechar acima de {_price(trigger)}.")
        watch_for = f"Procure defesa do nível e fechamento acima de {_price(trigger)}."

    if readiness >= 80:
        stage = "Perto da confirmação, mas ainda não confirmado."
    elif readiness >= 70:
        stage = "Em formação; faltam sinais objetivos."
    else:
        stage = "Inicial; apenas para acompanhamento."

    invalidation_side = "abaixo" if direction == "LONG" else "acima"
    avoid_if = (f"Descarte a leitura se o preço fechar {invalidation_side} de "
                f"{_price(invalidation)}. O alvo de {_price(target)} só vale depois da confirmação.")
    return {
        "title": title,
        "summary": summary,
        "stage": stage,
        "watch_for": watch_for,
        "avoid_if": avoid_if,
    }
