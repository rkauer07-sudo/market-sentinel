"""Evidence-gated daily learning for signal ranking.

Inspired by HKUDS/Vibe-Trading's trade-journal, Shadow Account and walk-forward
guidance.  The learner never places orders and fails closed when evidence is
small or the chronological holdout disagrees with the training window.
"""

from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo


LOCAL_ZONE = ZoneInfo("America/Sao_Paulo")
DIMENSIONS = ("venue", "timeframe", "direction", "setup")


def _is_win(row: dict) -> bool:
    return str(row.get("status", "")).startswith("SUCCESS_T")


def _smoothed_rate(rows: list[dict]) -> float:
    wins = sum(_is_win(row) for row in rows)
    return (wins + 2) / (len(rows) + 4)


class DailyLearner:
    """Build conservative score modifiers from resolved, point-in-time outcomes."""

    def __init__(self, store, *, min_total: int = 30, min_segment: int = 12):
        self.store = store
        self.min_total = min_total
        self.min_segment = min_segment

    def run_if_due(self, now: datetime | None = None) -> dict | None:
        current = now or datetime.now(LOCAL_ZONE)
        if current.tzinfo is None:
            current = current.replace(tzinfo=LOCAL_ZONE)
        target_day = current.astimezone(LOCAL_ZONE).date() - timedelta(days=1)
        if self.store.learning_run(target_day.isoformat()):
            return None
        return self.run_for_day(target_day)

    def run_for_day(self, target_day: date) -> dict:
        cutoff_local = datetime.combine(target_day + timedelta(days=1), dt_time.min, LOCAL_ZONE)
        cutoff = int(cutoff_local.timestamp())
        rows = self.store.resolved_signals(closed_before=cutoff, lookback_days=180)
        rows.sort(key=lambda row: (int(row["closed_at"]), int(row["id"])))
        report = {
            "day": target_day.isoformat(),
            "cutoff_at": cutoff,
            "sample_size": len(rows),
            "wins": sum(_is_win(row) for row in rows),
            "win_rate": round(sum(_is_win(row) for row in rows) / len(rows) * 100, 1) if rows else None,
            "promoted_profiles": 0,
            "status": "insufficient",
            "profiles": [],
            "method": "chronological_walk_forward_holdout",
        }
        if len(rows) < self.min_total:
            report["note"] = f"Aguardando {self.min_total - len(rows)} resultados para calibrar sem superajuste."
            self.store.replace_learning_profiles([])
            self.store.save_learning_run(report)
            return report

        split = max(1, min(len(rows) - 1, int(len(rows) * .8)))
        train, holdout = rows[:split], rows[split:]
        train_base, holdout_base = _smoothed_rate(train), _smoothed_rate(holdout)
        profiles = []
        for dimension in DIMENSIONS:
            values = sorted({str(row[dimension]) for row in rows})
            for value in values:
                segment_train = [row for row in train if str(row[dimension]) == value]
                segment_holdout = [row for row in holdout if str(row[dimension]) == value]
                sample_size = len(segment_train) + len(segment_holdout)
                if sample_size < self.min_segment or len(segment_train) < 8 or len(segment_holdout) < 3:
                    continue
                train_delta = _smoothed_rate(segment_train) - train_base
                holdout_delta = _smoothed_rate(segment_holdout) - holdout_base
                agrees = train_delta * holdout_delta > 0 and min(abs(train_delta), abs(holdout_delta)) >= .03
                if not agrees:
                    continue
                combined_delta = (train_delta + holdout_delta) / 2
                confidence = min(1.0, sample_size / 40)
                modifier = round(max(-4, min(4, combined_delta * 14 * confidence)))
                if modifier == 0:
                    continue
                segment = segment_train + segment_holdout
                profiles.append({
                    "profile_key": f"{dimension}:{value}",
                    "dimension": dimension,
                    "value": value,
                    "samples": sample_size,
                    "wins": sum(_is_win(row) for row in segment),
                    "win_rate": round(sum(_is_win(row) for row in segment) / sample_size * 100, 1),
                    "modifier": modifier,
                    "confidence": round(confidence, 3),
                    "trained_until": cutoff,
                })
        report.update(status="validated", profiles=profiles, promoted_profiles=len(profiles))
        report["note"] = ("Perfis promovidos somente quando treino e período posterior concordam."
                          if profiles else "Nenhum padrão repetiu no período de validação; modelo mantido.")
        self.store.replace_learning_profiles(profiles)
        self.store.save_learning_run(report)
        return report

    def adjustment(self, opportunity) -> tuple[int, list[str]]:
        profiles = self.store.learning_profiles()
        matches = []
        for dimension in DIMENSIONS:
            value = (opportunity.market.venue if dimension == "venue" else
                     getattr(opportunity, dimension))
            profile = profiles.get(f"{dimension}:{value}")
            if profile:
                matches.append(profile)
        if not matches:
            return 0, []
        modifier = round(sum(int(profile["modifier"]) for profile in matches) / len(matches))
        modifier = max(-4, min(4, modifier))
        evidence = [
            f"{profile['dimension']}={profile['value']}: {profile['win_rate']:.1f}% em {profile['samples']} resultados"
            for profile in matches
        ]
        return modifier, evidence
