"""Quota management with multi-period support."""

import json
import logging
from datetime import date, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def _period_expired(period: str, period_start: str) -> bool:
    """Check if a quota period has expired and needs reset."""
    if period == "total":
        return False
    try:
        start = date.fromisoformat(period_start)
    except (ValueError, TypeError):
        return True

    today = date.today()
    if period == "daily":
        return today > start
    elif period == "weekly":
        return today >= start + timedelta(days=7)
    elif period == "monthly":
        # Next month's same day (or 1st of next month)
        if start.month == 12:
            next_reset = start.replace(year=start.year + 1, month=1, day=1)
        else:
            next_reset = start.replace(month=start.month + 1, day=1)
        return today >= next_reset
    return False


class QuotaManager:
    """Manages per-model token quotas with multi-period support."""

    def __init__(self, data_dir: Path):
        self.data_file = data_dir / "quotas.json"
        self.data_dir = data_dir
        self.data: dict = self._load()

    def _load(self) -> dict:
        if self.data_file.exists():
            try:
                raw = json.loads(self.data_file.read_text())
                if isinstance(raw, dict) and "models" in raw:
                    return raw
            except Exception as e:
                logger.warning("Failed to load quotas.json: %s", e)
        return {"models": {}}

    def _save(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))

    def _reset_expired(self):
        """Reset any expired quota periods."""
        for model_cfg in self.data["models"].values():
            for q in model_cfg.get("quotas", []):
                if _period_expired(q["period"], q.get("period_start", "")):
                    q["used_tokens"] = 0
                    q["period_start"] = date.today().isoformat()

    def has_any_quota(self) -> bool:
        """Return True if any model has quota configured."""
        return bool(self.data["models"])

    def is_exhausted(self, model: str) -> bool:
        """Check if any quota for this model is exceeded."""
        self._reset_expired()
        cfg = self.data["models"].get(model)
        if not cfg:
            return False
        for q in cfg.get("quotas", []):
            if q.get("used_tokens", 0) >= q.get("max_tokens", 0):
                return True
        return False

    def record_usage(self, model: str, tokens: int):
        """Record token usage for a model."""
        cfg = self.data["models"].get(model)
        if not cfg:
            return
        for q in cfg.get("quotas", []):
            q["used_tokens"] = q.get("used_tokens", 0) + tokens
        self._save()

    def get_fallback(self, model: str) -> str:
        """Get fallback model, following the chain until a non-exhausted one is found."""
        visited = set()
        current = model
        while current in self.data["models"]:
            if current in visited:
                return ""  # circular
            visited.add(current)
            if not self.is_exhausted(current):
                return current if current != model else ""
            fb = self.data["models"][current].get("fallback", "")
            if not fb:
                return ""
            current = fb
        # current is not in our quota system — it's usable (no limit configured)
        return current if current != model else ""

    def set_quota(self, model: str, period: str, max_tokens: int, fallback: str = ""):
        """Set or update a quota for a model."""
        if model not in self.data["models"]:
            self.data["models"][model] = {"quotas": [], "fallback": ""}

        cfg = self.data["models"][model]
        if fallback:
            cfg["fallback"] = fallback

        # Update existing period or add new
        for q in cfg["quotas"]:
            if q["period"] == period:
                q["max_tokens"] = max_tokens
                self._save()
                return

        cfg["quotas"].append({
            "period": period,
            "max_tokens": max_tokens,
            "used_tokens": 0,
            "period_start": date.today().isoformat(),
        })
        self._save()

    def reset_usage(self, model: str):
        """Reset all usage counters for a model."""
        cfg = self.data["models"].get(model)
        if cfg:
            for q in cfg["quotas"]:
                q["used_tokens"] = 0
                q["period_start"] = date.today().isoformat()
            self._save()

    def get_status(self) -> dict:
        """Get full status of all quotas."""
        self._reset_expired()
        return dict(self.data["models"])
