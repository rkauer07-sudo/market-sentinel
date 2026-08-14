from __future__ import annotations
import html
import httpx
from .models import Opportunity


class TelegramNotifier:
    def __init__(self, client: httpx.AsyncClient, token: str | None, chat_id: str | None):
        self.client, self.token, self.chat_id = client, token, chat_id

    @property
    def configured(self): return bool(self.token and self.chat_id)

    async def send(self, opportunity: Opportunity):
        if not self.configured: return
        response = await self.client.post(f"https://api.telegram.org/bot{self.token}/sendMessage", json={
            "chat_id": self.chat_id, "parse_mode": "HTML", "disable_web_page_preview": True,
            "text": format_alert(opportunity)})
        response.raise_for_status()

    async def send_resolution(self, signal: dict):
        if not self.configured: return
        response = await self.client.post(f"https://api.telegram.org/bot{self.token}/sendMessage", json={
            "chat_id": self.chat_id, "parse_mode": "HTML", "disable_web_page_preview": True,
            "text": format_resolution(signal)})
        response.raise_for_status()


def format_alert(op: Opportunity) -> str:
    icon = "🟢" if op.direction == "LONG" else "🔴"
    strength = "FORTE" if op.score >= 80 else "MODERADA"
    reasons = "\n".join(f"• {html.escape(x)}" for x in op.reasons)
    risks = "\n".join(f"• {html.escape(x)}" for x in op.risks) or "• Nenhum risco técnico adicional detectado"
    targets = "".join(f"Alvo {index} (Fib): <code>{target:.8g}</code>\n"
                      for index, target in enumerate(op.targets, 1))
    return (f"{icon} <b>OPORTUNIDADE {strength}</b>\n\n"
        f"<b>{html.escape(op.market.symbol)} · {op.timeframe} · {op.direction}</b>\n"
        f"Venue: {op.market.venue} | Tipo: {op.market.market_type}\n"
        f"Classe: {op.market.asset_class.value}\n"
        f"Score: <b>{op.score}/100</b> | R:R: <b>{op.risk_reward:.2f}</b>\n\n"
        f"Entrada técnica: <code>{op.entry:.8g}</code>\nStop/invalidação: <code>{op.stop:.8g}</code>\n"
        f"{targets}\n"
        f"<b>Confirmações</b>\n{reasons}\n\n<b>Riscos</b>\n{risks}\n\n"
        "⚠️ Alerta técnico informativo; não é ordem nem recomendação financeira.")


def format_resolution(signal: dict) -> str:
    success = str(signal["status"]).startswith("SUCCESS")
    icon = "✅" if success else "⏱️" if signal["status"] == "EXPIRED" else "❌"
    return (f"{icon} <b>OPORTUNIDADE ENCERRADA</b>\n\n"
        f"<b>{html.escape(signal['symbol'])} · {signal['timeframe']} · {signal['direction']}</b>\n"
        f"Venue: {signal['venue']}\nStatus: <b>{signal['status']}</b>\n"
        f"Motivo: {html.escape(signal['resolution_reason'])}\n\n"
        f"Movimento favorável máximo: {signal['max_favorable_pct']:.2f}%\n"
        f"Movimento adverso máximo: {signal['max_adverse_pct']:.2f}%")
