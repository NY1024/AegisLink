import time
import threading
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Dict, List, Optional
from pathlib import Path

BEIJING_TZ = timezone(timedelta(hours=8))

class AlertLevel:
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class Alert:
    def __init__(self, level: str, message: str, source: str, metadata: Optional[Dict] = None):
        self.level = level
        self.message = message
        self.source = source
        self.metadata = metadata or {}
        self.timestamp = datetime.now(BEIJING_TZ)
        self.alert_id = f"alert-{int(self.timestamp.timestamp() * 1000)}"

    def to_dict(self) -> Dict:
        return {
            "alert_id": self.alert_id,
            "level": self.level,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

class MonitoringService:
    def __init__(self, log_file: str = "logs/alerts.log"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.alerts: List[Alert] = []
        self.alert_history: List[Alert] = []
        self.max_history = 1000
        self._lock = threading.Lock()
        self._start_time = time.time()

        self.metrics = {
            "total_requests": 0,
            "auth_decisions": {"allow": 0, "deny": 0},
            "token_issued": 0,
            "token_revoked": 0,
            "errors": 0,
            "by_agent": defaultdict(int),
            "by_action": defaultdict(int)
        }

    def record_request(self, agent_id: str, action: str):
        with self._lock:
            self.metrics["total_requests"] += 1
            self.metrics["by_agent"][agent_id] += 1
            self.metrics["by_action"][action] += 1

    def record_auth_decision(self, decision: str, requestor: str, target: str):
        with self._lock:
            self.metrics["auth_decisions"][decision] += 1
            if decision == "deny":
                self._check_deny_threshold(requestor)

    def record_token_issued(self):
        with self._lock:
            self.metrics["token_issued"] += 1

    def record_token_revoked(self):
        with self._lock:
            self.metrics["token_revoked"] += 1

    def record_error(self):
        with self._lock:
            self.metrics["errors"] += 1

    def _check_deny_threshold(self, requestor: str):
        recent_denies = sum(
            1 for a in self.alert_history[-100:]
            if a.level == AlertLevel.WARNING and a.source == requestor
        )
        if recent_denies > 10:
            alert = Alert(
                level=AlertLevel.WARNING,
                message=f"高频拒绝: Agent {requestor} 在短时间内被拒绝超过{recent_denies}次",
                source="monitoring",
                metadata={"agent_id": requestor, "deny_count": recent_denies}
            )
            self._add_alert(alert)

    def _add_alert(self, alert: Alert):
        self.alerts.append(alert)
        self.alert_history.append(alert)
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]
        self._persist_alert(alert)
        print(f"[ALERT:{alert.level.upper()}] {alert.message}")

    def _persist_alert(self, alert: Alert):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(alert.to_dict().__str__() + "\n")

    def trigger_alert(self, level: str, message: str, source: str, metadata: Optional[Dict] = None):
        alert = Alert(level, message, source, metadata)
        with self._lock:
            self._add_alert(alert)
        return alert

    def get_metrics(self) -> Dict:
        with self._lock:
            uptime = time.time() - self._start_time
            return {
                "uptime_seconds": uptime,
                "metrics": {
                    **self.metrics,
                    "by_agent": dict(self.metrics["by_agent"]),
                    "by_action": dict(self.metrics["by_action"])
                },
                "active_alerts": len(self.alerts),
                "recent_alerts": [a.to_dict() for a in self.alert_history[-10:]]
            }

    def get_alerts(self, level: Optional[str] = None, limit: int = 100) -> List[Dict]:
        with self._lock:
            alerts = self.alert_history
            if level:
                alerts = [a for a in alerts if a.level == level]
            return [a.to_dict() for a in alerts[-limit:]]

    def check_system_health(self) -> Dict:
        with self._lock:
            issues = []
            error_rate = self.metrics["errors"] / max(1, self.metrics["total_requests"])
            deny_rate = self.metrics["auth_decisions"]["deny"] / max(1, sum(self.metrics["auth_decisions"].values()))

            if error_rate > 0.1:
                issues.append(f"错误率过高: {error_rate:.2%}")

            if deny_rate > 0.5:
                issues.append(f"拒绝率过高: {deny_rate:.2%}")

            if self.metrics["errors"] > 100:
                issues.append("错误数量超过100，系统可能存在异常")

            return {
                "healthy": len(issues) == 0,
                "issues": issues,
                "error_rate": f"{error_rate:.2%}",
                "deny_rate": f"{deny_rate:.2%}",
                "total_requests": self.metrics["total_requests"]
            }

monitoring_service = MonitoringService()
