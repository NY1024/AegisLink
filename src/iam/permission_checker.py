from typing import List, Optional
from src.common.config import AGENT_STATIC_CAPABILITIES, USER_PERMISSIONS
from src.audit.audit_logger import audit_logger

class PermissionChecker:
    def check_capability(self, agent_id: str, required_capability: str) -> bool:
        agent_caps = AGENT_STATIC_CAPABILITIES.get(agent_id, [])
        return self._match_capability(required_capability, agent_caps)
    
    def check_delegated_permission(self, delegated_user: str, agent_id: str, required_permission: str) -> bool:
        user_perms = USER_PERMISSIONS.get(delegated_user, [])
        agent_caps = AGENT_STATIC_CAPABILITIES.get(agent_id, [])
        
        user_has_perm = self._match_capability(required_permission, user_perms)
        agent_has_cap = self._match_capability(required_permission, agent_caps)
        
        return user_has_perm and agent_has_cap
    
    def check_agent_call_permission(self, requestor_agent_id: str, target_agent_id: str, action: str) -> bool:
        required_cap = f"agent:call:{target_agent_id}"
        agent_caps = AGENT_STATIC_CAPABILITIES.get(requestor_agent_id, [])
        
        has_perm = self._match_capability(required_cap, agent_caps) or self._match_capability("agent:call:*", agent_caps)
        
        if not has_perm:
            audit_logger.log_event(
                event_type="auth_decision",
                decision="deny",
                requestor_agent_id=requestor_agent_id,
                target_agent_id=target_agent_id,
                action=action,
                resource="none",
                reason=f"Missing capability: {required_cap}"
            )
        return has_perm
    
    def calculate_effective_permissions(self, delegated_user: str, agent_id: str) -> List[str]:
        user_perms = USER_PERMISSIONS.get(delegated_user, [])
        agent_caps = AGENT_STATIC_CAPABILITIES.get(agent_id, [])
        
        effective = []
        for perm in user_perms:
            if self._match_capability(perm, agent_caps):
                effective.append(perm)
        return effective
    
    def _match_capability(self, required: str, existing: List[str]) -> bool:
        for cap in existing:
            if cap == required:
                return True
            if cap.endswith("*"):
                prefix = cap[:-1]
                if required.startswith(prefix):
                    return True
        return False

permission_checker = PermissionChecker()
