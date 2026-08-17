"""Technical confirmation adapted from HKUDS/Vibe-Trading (MIT License).

Source: https://github.com/HKUDS/Vibe-Trading
Copyright (c) 2026 Vibe-Trading Contributors.
"""

from __future__ import annotations
from dataclasses import dataclass
from math import sqrt


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    alpha = 2 / (period + 1)
    current = values[0]
    for value in values[1:]:
        current = alpha * value + (1 - alpha) * current
    return current


def wilder_rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    changes = [current - previous for previous, current in zip(values, values[1:])]
    gains = [max(change, 0) for change in changes]
    losses = [max(-change, 0) for change in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0
    return 100 - 100 / (1 + avg_gain / avg_loss)


def macd(values: list[float], fast: int = 12, slow: int = 26,
         signal_period: int = 9) -> tuple[float, float, float] | None:
    if len(values) < slow + signal_period:
        return None
    fast_alpha, slow_alpha = 2 / (fast + 1), 2 / (slow + 1)
    fast_value = slow_value = values[0]
    line = []
    for value in values:
        fast_value = fast_alpha * value + (1 - fast_alpha) * fast_value
        slow_value = slow_alpha * value + (1 - slow_alpha) * slow_value
        line.append(fast_value - slow_value)
    signal_value = ema(line, signal_period)
    return (line[-1], signal_value, line[-1] - signal_value) if signal_value is not None else None


def bollinger(values: list[float], period: int = 20,
              deviations: float = 2) -> tuple[float, float, float] | None:
    if len(values) < period:
        return None
    window = values[-period:]
    middle = sum(window) / period
    std = sqrt(sum((value - middle) ** 2 for value in window) / max(period - 1, 1))
    return middle + deviations * std, middle, middle - deviations * std


@dataclass(frozen=True, slots=True)
class VibeSnapshot:
    rsi: float
    ema20: float
    macd_line: float
    macd_signal: float
    macd_histogram: float
    bollinger_upper: float
    bollinger_middle: float
    bollinger_lower: float
    ema20_previous: float

    def confirms(self, direction: str, close: float) -> bool:
        if direction == "LONG":
            return 50 <= self.rsi <= 65 and self.macd_histogram > 0 and \
                self.macd_line > self.macd_signal and self.ema20 > self.ema20_previous and \
                close > self.ema20 and close < self.bollinger_upper
        return 35 <= self.rsi <= 50 and self.macd_histogram < 0 and \
            self.macd_line < self.macd_signal and self.ema20 < self.ema20_previous and \
            close < self.ema20 and close > self.bollinger_lower


def technical_snapshot(values: list[float]) -> VibeSnapshot | None:
    rsi_value, ema20 = wilder_rsi(values), ema(values, 20)
    macd_values, bands = macd(values), bollinger(values)
    if rsi_value is None or ema20 is None or macd_values is None or bands is None:
        return None
    ema20_previous = ema(values[:-1], 20)
    if ema20_previous is None:
        return None
    return VibeSnapshot(rsi_value, ema20, *macd_values, *bands, ema20_previous)
