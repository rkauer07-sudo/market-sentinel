from __future__ import annotations
from statistics import fmean
from .models import Candle, Market, Opportunity, PotentialOpportunity


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
    if resistance and previous.close <= resistance < last.close and volume_ratio >= 1.5:
        setup, direction, entry, stop = "rompimento com volume", "LONG", last.close, resistance - current_atr
        target1 = entry + 2.2 * (entry - stop)
    elif support and abs(last.low - support) <= tolerance and last.close > support and last.close > last.open and volume_ratio >= 0.8:
        setup, direction, entry, stop = "reteste de suporte", "LONG", last.close, support - 0.8 * current_atr
        target1 = resistance or entry + 2.2 * (entry - stop)
    elif support and previous.close < support < last.close and volume_ratio >= 1.2:
        setup, direction, entry, stop = "recuperação de suporte", "LONG", last.close, min(last.low, support - 0.5 * current_atr)
        target1 = resistance or entry + 2.2 * (entry - stop)
    elif support and previous.close >= support > last.close and volume_ratio >= 1.5:
        setup, direction, entry, stop = "perda de suporte com volume", "SHORT", last.close, support + current_atr
        target1 = entry - 2.2 * (stop - entry)
    else:
        return None
    risk = abs(entry - stop); reward = abs(target1 - entry)
    if risk <= 0: return None
    rr = reward / risk
    reasons, risks = [f"Estrutura confirmada: {setup}"], []
    aligned = trend_up if direction == "LONG" else trend_down
    btc_aligned = (btc_bullish and direction == "LONG") or (not btc_bullish and direction == "SHORT")
    breakdown = {
        "Estrutura": 20,
        "Tendência": 20 if aligned else 0,
        "Volume": 15 if volume_ratio >= 2 else 12 if volume_ratio >= 1.5 else 8 if volume_ratio >= 1.2 else 4 if volume_ratio >= 1 else 0,
        "Contexto BTC": 15 if btc_aligned else 0,
        "Risco/retorno": 15 if rr >= 3 else 12 if rr >= 2.5 else 9 if rr >= float(cfg["min_risk_reward"]) else 0,
        "Liquidez": 10 if market.daily_quote_volume >= 5_000_000 else 8 if market.daily_quote_volume >= 1_000_000 else 6 if market.daily_quote_volume >= float(cfg["min_daily_quote_volume"]) else 0,
        "Precisão da entrada": 5 if abs(entry - ma20) <= 1.5 * current_atr else 2 if abs(entry - ma20) <= 2.5 * current_atr else 0,
    }
    score = min(sum(breakdown.values()), 100)
    confirmations = 1 + int(aligned) + int(btc_aligned) + int(volume_ratio >= 1.2) + int(rr >= float(cfg["min_risk_reward"])) + int(breakdown["Liquidez"] > 0) + int(breakdown["Precisão da entrada"] > 0)
    if aligned: reasons.append("Tendência alinhada em 20/50/200 períodos")
    else: risks.append("Sinal não está plenamente alinhado à tendência principal")
    if btc_aligned:
        reasons.append("Contexto do BTC alinhado")
    else: risks.append("Contexto do BTC contrário ao sinal")
    if volume_ratio >= 1.2: reasons.append(f"Volume relativo {volume_ratio:.1f}x")
    else: risks.append(f"Volume relativo ainda modesto: {volume_ratio:.1f}x")
    if market.daily_quote_volume < float(cfg["min_daily_quote_volume"]): risks.append("Liquidez diária abaixo do filtro preferencial")
    if rr < float(cfg["min_risk_reward"]) or score < int(cfg["min_score"]) or confirmations < int(cfg.get("min_confirmations", 5)): return None
    if score >= int(cfg.get("strong_score", 85)) and (not aligned or volume_ratio < 1.5): return None
    target2 = entry + (3.5 * risk if direction == "LONG" else -3.5 * risk)
    return Opportunity(market, timeframe, direction, setup, entry, stop, target1, target2, rr, score,
        reasons, risks, last.timestamp, breakdown, confirmations)


def analyze_potential(market: Market, timeframe: str, candles: list[Candle], btc_bullish: bool, cfg: dict) -> PotentialOpportunity | None:
    if len(candles) < int(cfg["min_candles"]): return None
    closed = candles[:-1]; closes = [c.close for c in closed]; last = closed[-1]
    current_atr = atr(closed); ma20, ma50, ma200 = sma(closes, 20), sma(closes, 50), sma(closes, 200)
    if not current_atr or not all((ma20, ma50, ma200)): return None
    lows, highs = pivots(closed, int(cfg["pivot_window"]))
    support, resistance = nearest(lows, last.close, True), nearest(highs, last.close, False)
    zone = current_atr * float(cfg.get("potential_zone_atr", .65))
    trend_up, trend_down = last.close > ma20 > ma50 and last.close > ma200, last.close < ma20 < ma50 and last.close < ma200
    volume_ratio = last.volume / max(fmean([c.volume for c in closed[-21:-1]]), 1e-12)
    def ready(distance, trend, btc):
        return min(90, round(35 + max(0, 25 * (1 - distance / zone)) + 15 * trend + 10 * btc + min(5, volume_ratio * 3)))
    if resistance and 0 <= resistance - last.close <= zone:
        r = ready(resistance-last.close, trend_up, btc_bullish)
        return PotentialOpportunity(market,timeframe,"LONG","Possível rompimento de resistência",resistance,
            resistance-current_atr,resistance+2*current_atr,r,
            [f"Fechamento acima de {resistance:.8g}","Volume do candle de confirmação ≥ 1,5x da média","Sustentar o nível rompido no reteste"],
            ["Rejeição na resistência","Rompimento sem volume pode ser falso","BTC enfraquecer antes da confirmação"],last.timestamp)
    if support and 0 <= last.close - support <= zone:
        direction = "LONG" if not trend_down else "SHORT"
        scenario = "Possível reação no suporte" if direction == "LONG" else "Possível perda de suporte"
        trigger = support + .25*current_atr if direction == "LONG" else support
        invalid = support-.8*current_atr if direction == "LONG" else support+current_atr
        target = resistance or (support + 2*current_atr if direction == "LONG" else support-2*current_atr)
        r = ready(last.close-support, not trend_down if direction == "LONG" else trend_down, btc_bullish if direction == "LONG" else not btc_bullish)
        conditions = ([f"Reação compradora e fechamento acima de {trigger:.8g}","Pavio de rejeição ou candle de força","Volume crescente na defesa"] if direction == "LONG" else [f"Fechamento abaixo de {support:.8g}","Volume ≥ 1,5x da média","Reteste do suporte perdido sem recuperação"])
        return PotentialOpportunity(market,timeframe,direction,scenario,trigger,invalid,target,r,conditions,
            ["O nível pode não confirmar","Movimento antecipado aumenta o risco","Mudança brusca no BTC invalida o contexto"],last.timestamp)
    return None


def btc_regime(candles: list[Candle]) -> bool:
    closed = candles[:-1]; closes = [x.close for x in closed]
    ma50, ma200 = sma(closes, 50), sma(closes, 200)
    return bool(ma50 and ma200 and closes[-1] > ma200 and ma50 > ma200)
