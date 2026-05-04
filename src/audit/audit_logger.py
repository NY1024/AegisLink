import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
from pathlib import Path

BEIJING_TZ = timezone(timedelta(hours=8))

class AuditLogger:
    def __init__(self, log_file: str = "audit_logs.jsonl"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_event(self, event_type: str, decision: str, requestor_agent_id: str,
                 target_agent_id: str, action: str, resource: str, reason: str,
                 delegated_user: Optional[str] = None, token_id: Optional[str] = None) -> Dict:
        log_entry = {
            "log_id": str(uuid.uuid4()),
            "timestamp": datetime.now(BEIJING_TZ).isoformat(),
            "event_type": event_type,
            "decision": decision,
            "requestor_agent_id": requestor_agent_id,
            "target_agent_id": target_agent_id,
            "action": action,
            "resource": resource,
            "reason": reason,
            "delegated_user": delegated_user,
            "token_id": token_id,
            "request_id": str(uuid.uuid4())
        }

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        return log_entry
    
    def query_logs(self, filter_criteria: Optional[Dict] = None, limit: int = 100) -> List[Dict]:
        logs = []
        if not self.log_file.exists():
            return logs
        
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in reversed(list(f)):
                if len(logs) >= limit:
                    break
                try:
                    log = json.loads(line.strip())
                    if self._match_filter(log, filter_criteria):
                        logs.append(log)
                except json.JSONDecodeError:
                    continue
        
        return logs
    
    def export_logs(self, output_file: str, filter_criteria: Optional[Dict] = None) -> int:
        logs = self.query_logs(filter_criteria, limit=10000)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        return len(logs)
    
    def _match_filter(self, log: Dict, filter_criteria: Optional[Dict]) -> bool:
        if not filter_criteria:
            return True
        
        for key, value in filter_criteria.items():
            if log.get(key) != value:
                return False
        return True

audit_logger = AuditLogger()
