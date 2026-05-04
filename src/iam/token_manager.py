import jwt
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from src.common.config import JWT_SECRET_KEY, JWT_ALGORITHM, TOKEN_EXPIRE_SECONDS, TEMP_TOKEN_EXPIRE_SECONDS
from src.audit.audit_logger import audit_logger

class TokenManager:
    def __init__(self):
        self.revoked_tokens = set()

    def generate_token(self, agent_id: str, agent_role: str, delegated_user: Optional[str] = None,
                       capabilities: List[str] = None, expires_in: int = TOKEN_EXPIRE_SECONDS) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "iss": "aegislink-iam",
            "sub": f"agent:{agent_id}",
            "agent_id": agent_id,
            "agent_role": agent_role,
            "iat": now.timestamp(),
            "exp": (now + timedelta(seconds=expires_in)).timestamp(),
            "jti": str(uuid.uuid4()),
            "capabilities": capabilities or [],
            "trust_chain": []
        }

        if delegated_user:
            payload["delegated_user"] = delegated_user

        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return token

    def generate_temp_call_token(self, original_token: str, target_agent_id: str, action: str, resource: str) -> str:
        payload = self.verify_token(original_token)
        if not payload:
            raise ValueError("Invalid original token")

        now = datetime.now(timezone.utc)
        trust_chain = payload.get("trust_chain", [])
        trust_chain.append({
            "agent_id": payload["agent_id"],
            "timestamp": now.timestamp(),
            "action": action,
            "resource": resource
        })

        temp_payload = {
            "iss": "aegislink-iam",
            "sub": f"agent:{payload['agent_id']}",
            "agent_id": payload["agent_id"],
            "agent_role": payload["agent_role"],
            "target_agent_id": target_agent_id,
            "action": action,
            "resource": resource,
            "iat": now.timestamp(),
            "exp": (now + timedelta(seconds=TEMP_TOKEN_EXPIRE_SECONDS)).timestamp(),
            "jti": str(uuid.uuid4()),
            "delegated_user": payload.get("delegated_user"),
            "trust_chain": trust_chain
        }

        token = jwt.encode(temp_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return token

    def verify_token(self, token: str) -> Optional[Dict]:
        try:
            if token in self.revoked_tokens:
                audit_logger.log_event(
                    event_type="token_revoked",
                    decision="deny",
                    requestor_agent_id="unknown",
                    target_agent_id="unknown",
                    action="token_verification",
                    resource="none",
                    reason="Token has been revoked"
                )
                return None

            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            audit_logger.log_event(
                event_type="token_expired",
                decision="deny",
                requestor_agent_id="unknown",
                target_agent_id="unknown",
                action="token_verification",
                resource="none",
                reason="Token has expired"
            )
            return None
        except jwt.InvalidTokenError:
            audit_logger.log_event(
                event_type="token_invalid",
                decision="deny",
                requestor_agent_id="unknown",
                target_agent_id="unknown",
                action="token_verification",
                resource="none",
                reason="Invalid token format or signature"
            )
            return None

    def revoke_token(self, token: str) -> bool:
        payload = self.verify_token(token)
        if not payload:
            return False
        self.revoked_tokens.add(token)
        audit_logger.log_event(
            event_type="token_revoked",
            decision="allow",
            requestor_agent_id=payload["agent_id"],
            target_agent_id="none",
            action="token_revocation",
            resource="none",
            reason="Token revoked by administrator"
        )
        return True

token_manager = TokenManager()
