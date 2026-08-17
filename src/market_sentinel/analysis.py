from __future__ import annotations
from statistics import fmean
from .models import Candle, Market, Opportunity, PotentialOpportunity
from .vibe_indicators import technical_snapshot


def sma(values, period):
    return fmean(values[-period:]) if len(values) >= period else None


def atr(candles: list[Candle], period=14):
    if len(candles) < period + 1: return None
    trs = [max(c.high - c.low, abs(c.high - p.close), abs(c.low - p.close)) for p, c in zip(candles[-period-1:-1], candles[-period:])]
    return fmean(trs)


def pivots(candles: list[Candle], window=3):
    lows, highs = [], []
    for i in range(window, len(candles) - window):
        chunk = candles[i-window:i+window+1]; candle = candles[i]
        if candle.low == min(x.low for x in chunk): lows.append(candle.low)
        if candle.high == max(x.high for x in chunk): highs.append(candle.high)
    return lows, highs


def nearest(values, price, below=True):
    eligible = [x for x in values if x < price] if below else [x for x in values if x > price]
    return (max(eligible) if below else min(eligible)) if eligible else None


def rsi(values, period=14):
    if len(values) < period + 1: return None
    changes = [b-a for a, b in zip(values[-period-1:-1], values[-period:])]
    gains = fmean(max(x, 0) for x in changes); losses = fmean(max(-x, 0) for x in changes)
    if losses == 0: return 100.0
    return 100 - 100 / (1 + gains / losses)


def fibonacci_targets(entry: float, stop: float, direction: str) -> tuple[float, ...]:
    """Five Fibonacci extensions measured from entry using the stop distance as 1R."""
    risk = abs(entry - stop)
    sign = 1 if direction == "LONG" else -1
    return tuple(entry + sign * ratio * risk for ratio in (1.0, 1.272, 1.618, 2.0, 2.618))


def confirmed_breakout_retest(candles: list[Candle], levels: list[float], direction: str,
                              current_atr: float, min_bars: int = 2,
                              max_bars: int = 3, min_breakout_volume: float = 1.5,
                              min_retest_volume: float = 1.2) -> float | None:
    """Find a breakout retested and rejected 2-3 closed candles later."""
    if len(candles) < 3 or not levels:
        return None
    confirmation = candles[-1]
    tolerance = current_atr * .35
    matches: list[tuple[int, float]] = []
    confirmation_index = len(candles) - 1
    first_breakout = max(1, confirmation_index - max_bars)
    last_breakout = confirmation_index - min_bars
    if last_breakout < first_breakout:
        return None
    for index in range(first_breakout, last_breakout + 1):
        breakout, previous = candles[index], candles[index - 1]
        history = candles[max(0, index - 20):index]
        avg_volume = fmean(c.volume for c in history) if history else 0
        volume_ok = bool(avg_volume and breakout.volume / avg_volume >= min_breakout_volume
                         and confirmation.volume / avg_volume >= min_retest_volume)
        candle_range = max(confirmation.high - confirmation.low, 1e-12)
        body_ratio = abs(confirmation.close - confirmation.open) / candle_range
        for level in levels:
            if direction == "LONG":
                broke = previous.close <= level < breakout.close
                retested = confirmation.low <= level + tolerance and confirmation.close > level
                rejected = confirmation.close > confirmation.open and body_ratio >= .35 and \
                    confirmation.close >= confirmation.low + .65 * candle_range
            else:
                broke = previous.close >= level > breakout.close
                retested = confirmation.high >= level - tolerance and confirmation.close < level
                rejected = confirmation.close < confirmation.open and body_ratio >= .35 and \
                    confirmation.close <= confirmation.low + .35 * candle_range
            if broke and volume_ok and retested and rejected:
                matches.append((index, level))
    return max(matches, key=lambda item: item[0])[1] if matches else None


def analyze(market: Market, timeframe: str, candles: list[Candle], btc_bullish: bool, cfg: dict) -> Opportunity | None:
    minimum = int(cfg["min_candles"])
    if len(candles) < minimum: return None
    closed = candles[:-1]  # Never act on a still-forming candle.
    closes = [x.close for x in closed]; volumes = [x.volume for x in closed]
    last, previous = closed[-1], closed[-2]
    current_atr = atr(closed)
    ma20, ma50, ma200 = sma(closes, 20), sma(closes, 50), sma(closes, 200)
    if not current_atr or not all((ma20, ma50, ma200)): return None
    lows, highs = pivots(closed, int(cfg["pivot_window"]))
    support, resistance = nearest(lows, last.close, True), nearest(highs, last.close, False)
    volume_ratio = last.volume / max(fmean(volumes[-21:-1]), 1e-12)
    trend_up = last.close > ma20 > ma50 and last.close > ma200
    trend_down = last.close < ma20 < ma50 and last.close < ma200
    tolerance = current_atr * float(cfg["zone_tolerance_atr"])
    setup = direction = None
    retest_min_bars = int(cfg.get("retest_min_bars", 2))
    retest_max_bars = int(cfg.get("retest_max_bars", 3))
    breakout_volume = float(cfg.get("min_breakout_volume_ratio", 1.5))
    retest_volume = float(cfg.get("min_retest_volume_ratio", 1.2))
    long_retest = confirmed_breakout_retest(
        closed, highs, "LONG", current_atr, retest_min_bars, retest_max_bars,
        breakout_volume, retest_volume)
    short_retest = confirmed_breakout_retest(
        closed, lows, "SHORT", current_atr, retest_min_bars, retest_max_bars,
        breakout_volume, retest_volume)
    if long_retest is not None:
        setup, direction, entry, stop = "rompimento + reteste confirmado", "LONG", last.close, long_retest - current_atr
    elif short_retest is not None:
        setup, direction, entry, stop = "perda + reteste confirmado", "SHORT", last.close, short_retest + current_atr
    else:
        return None
    risk = abs(entry - stop)
    if risk <= 0: return None
    vibe = technical_snapshot(closes)
    if vibe is None or not vibe.confirms(direction, entry):
        return None
    target1, target2, target3, target4, target5 = fibonacci_targets(entry, stop, direction)
    rr = 2.618
    reasons, risks = [f"Estrutura confirmada: {setup}",
        (f"Vibe-Trading confirmado: RSI {vibe.rsi:.1f}, MACD histograma "
         f"{vibe.macd_histogram:.6g}, EMA20 {vibe.ema20:.8g}")], []
    aligned = trend_up if direction == "LONG" else trend_down
    btc_aligned = (btc_bullish and direction == "LONG") or (not btc_bullish and direction == "SHORT")
    # Precision-first gate: score cannot compensate for a counter-trend,
    # counter-regime, or weak-volume signal.
    if not aligned or not btc_aligned or volume_ratio < retest_volume:
        return None
    breakdown = {
        "Estrutura": 15,
        "Tendência": 15 if aligned else 0,
        "Volume": 15 if volume_ratio >= 2 else 12 if volume_ratio >= 1.5 else 8 if volume_ratio >= 1.2 else 4 if volume_ratio >= 1 else 0,
        "Contexto BTC": 15 if btc_aligned else 0,
        "Risco/retorno": 15 if rr >= 3 else 12 if rr >= 2.5 else 9 if rr >= float(cfg["min_risk_reward"]) else 0,
        "Liquidez": 10 if market.daily_quote_volume >= 5_000_000 else 8 if market.daily_quote_volume >= 1_000_000 else 6 if market.daily_quote_volume >= float(cfg["min_daily_quote_volume"]) else 0,
        "Precisão da entrada": 5 if abs(entry - ma20) <= 1.5 * current_atr else 2 if abs(entry - ma20) <= 2.5 * current_atr else 0,
        "Vibe-Trading": 10,
    }
    score = min(sum(breakdown.values()), 100)
    confirmations = 2 + int(aligned) + int(btc_aligned) + int(volume_ratio >= 1.2) + int(rr >= float(cfg["min_risk_reward"])) + int(breakdown["Liquidez"] > 0) + int(breakdown["Precisão da entrada"] > 0)
    if aligned: reasons.append("Tendência alinhada em 20/50/200 períodos")
    else: risks.append("Sinal não está plenamente alinhado à tendência principal")
    if btc_aligned:
        reasons.append("Contexto do BTC alinhado")
    else: risks.append("Contexto do BTC contrário ao sinal")
    if volume_ratio >= 1.2: reasons.append(f"Volume relativo {volume_ratio:.1f}x")
    else: risks.append(f"Volume relativo ainda modesto: {volume_ratio:.1f}x")
    if market.daily_quote_volume < float(cfg["min_daily_quote_volume"]): risks.append("Liquidez diária abaixo do filtro preferencial")
    if rr < float(cfg["min_risk_reward"]) or score < int(cfg["min_score"]) or confirmations < int(cfg.get("min_confirmations", 5)): return None
    if score >= int(cfg.get("strong_score", 85)) and volume_ratio < retest_volume: return None
    return Opportunity(market, timeframe, direction, setup, entry, stop,
        target1, target2, target3, target4, target5, rr, score,
        reasons, risks, last.timestamp, breakdown, confirmations)


def analyze_potential(market: Market, timeframe: str, candles: list[Candle], btc_bullish: bool, cfg: dict,
                      btc_change_30d: float | None = None) -> PotentialOpportunity | None:
    if len(candles) < int(cfg["min_candles"]): return None
    closed = candles[:-1]; closes = [c.close for c in closed]; last = closed[-1]
    current_atr = atr(closed); ma20, ma50, ma200 = sma(closes, 20), sma(closes, 50), sma(closes, 200)
    if not current_atr or not all((ma20, ma50, ma200)): return None
    lows, highs = pivots(closed, int(cfg["pivot_window"]))
    support, resistance = nearest(lows, last.close, True), nearest(highs, last.close, False)
    zone = current_atr * float(cfg.get("potential_zone_atr", .65))
    trend_up, trend_down = last.close > ma20 > ma50 and last.close > ma200, last.close < ma20 < ma50 and last.close < ma200
    volume_ratio = last.volume / max(fmean([c.volume for c in closed[-21:-1]]), 1e-12)
    current_rsi = rsi(closes) or 50
    btc_text = "BTC em regime diário de alta" if btc_bullish else "BTC em regime diário defensivo/baixista"
    if btc_change_30d is not None:
        btc_text += f"; variação nos últimos 30 candles diários: {btc_change_30d:+.1f}%"
    trend_text = ("Preço acima das SMA 20/50/200; tendência compradora alinhada" if trend_up else
                  "Preço abaixo das SMA 20/50/200; tendência vendedora alinhada" if trend_down else
                  "Médias 20/50/200 sem alinhamento completo; mercado em transição")
    indicators = [btc_text, trend_text, f"RSI 14 em {current_rsi:.1f}",
                  f"Volume atual em {volume_ratio:.2f}x a média de 20 candles",
                  f"ATR 14 em {current_atr:.8g} ({current_atr/last.close*100:.2f}% do preço)"]
    if support: indicators.append(f"Suporte técnico mais próximo em {support:.8g}")
    if resistance: indicators.append(f"Resistência técnica mais próxima em {resistance:.8g}")
    def ready(distance, trend, btc):
        return min(90, round(35 + max(0, 25 * (1 - distance / zone)) + 15 * trend + 10 * btc + min(5, volume_ratio * 3)))
    if resistance and 0 <= resistance - last.close <= zone:
        r = ready(resistance-last.close, trend_up, btc_bullish)
        trigger, invalid, target = resistance, resistance-current_atr, resistance+2*current_atr
        rr = abs(target-trigger) / max(abs(trigger-invalid), 1e-12)
        return PotentialOpportunity(market,timeframe,"LONG","Possível rompimento de resistência",trigger,
            invalid,target,r,
            [f"Fechamento acima de {resistance:.8g}","Volume do candle de confirmação ≥ 1,5x da média","Sustentar o nível rompido no reteste"],
            ["Rejeição na resistência","Rompimento sem volume pode ser falso","BTC enfraquecer antes da confirmação"],last.timestamp,
            indicators, rr)
    if support and 0 <= last.close - support <= zone:
        direction = "LONG" if not trend_down else "SHORT"
        scenario = "Possível reação no suporte" if direction == "LONG" else "Possível perda de suporte"
        trigger = support + .25*current_atr if direction == "LONG" else support
        invalid = support-.8*current_atr if direction == "LONG" else support+current_atr
        target = resistance or (support + 2*current_atr if direction == "LONG" else support-2*current_atr)
        r = ready(last.close-support, not trend_down if direction == "LONG" else trend_down, btc_bullish if direction == "LONG" else not btc_bullish)
        conditions = ([f"Reação compradora e fechamento acima de {trigger:.8g}","Pavio de rejeição ou candle de força","Volume crescente na defesa"] if direction == "LONG" else [f"Fechamento abaixo de {support:.8g}","Volume ≥ 1,5x da média","Reteste do suporte perdido sem recuperação"])
        rr = abs(target-trigger) / max(abs(trigger-invalid), 1e-12)
        return PotentialOpportunity(market,timeframe,direction,scenario,trigger,invalid,target,r,conditions,
            ["O nível pode não confirmar","Movimento antecipado aumenta o risco","Mudança brusca no BTC invalida o contexto"],last.timestamp,
            indicators, rr)
    return None


def btc_regime(candles: list[Candle]) -> bool:
    closed = candles[:-1]; closes = [x.close for x in closed]
    ma50, ma200 = sma(closes, 50), sma(closes, 200)
    return bool(ma50 and ma200 and closes[-1] > ma200 and ma50 > ma200)
