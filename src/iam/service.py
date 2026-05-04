from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from src.iam.token_manager import token_manager
from src.iam.permission_checker import permission_checker
from src.audit.audit_logger import audit_logger
from src.audit.monitoring import monitoring_service, AlertLevel
from src.common.config import AGENT_STATIC_CAPABILITIES, AGENT_RUNTIME_CAPABILITIES, USER_STATIC_CAPABILITIES, AGENT_CONFIG, AGENT_PORTS

BEIJING_TZ = timezone(timedelta(hours=8))

app = FastAPI(title="AegisLink IAM Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    monitoring_service.trigger_alert(
        AlertLevel.INFO,
        "AegisLink IAM服务启动",
        "system",
        {"service": "iam", "port": 8000}
    )

class TokenRequest(BaseModel):
    agent_id: str
    agent_role: str
    delegated_user: Optional[str] = None
    capabilities: Optional[List[str]] = None

class UserTokenRequest(BaseModel):
    user_id: str

class CallRequest(BaseModel):
    target_agent_id: str
    action: str
    resource: str

class VerifyRequest(BaseModel):
    token: str

@app.post("/token/issue")
def issue_token(req: TokenRequest):
    caps = req.capabilities or AGENT_STATIC_CAPABILITIES.get(req.agent_id, [])
    token = token_manager.generate_token(
        agent_id=req.agent_id,
        agent_role=req.agent_role,
        delegated_user=req.delegated_user,
        capabilities=caps
    )

    audit_logger.log_event(
        event_type="token_issued",
        decision="allow",
        requestor_agent_id=req.agent_id,
        target_agent_id="none",
        action="token_issuance",
        resource="none",
        reason="Token issued successfully",
        delegated_user=req.delegated_user
    )
    
    monitoring_service.record_token_issued()
    monitoring_service.record_request(req.agent_id, "token:issue")

    return {"access_token": token, "token_type": "Bearer"}

@app.post("/token/issue-user")
def issue_user_token(req: UserTokenRequest):
    caps = USER_STATIC_CAPABILITIES.get(req.user_id, [])
    token = token_manager.generate_token(
        agent_id=req.user_id,
        agent_role="user",
        delegated_user=None,
        capabilities=caps
    )

    audit_logger.log_event(
        event_type="token_issued",
        decision="allow",
        requestor_agent_id=req.user_id,
        target_agent_id="none",
        action="user_token_issuance",
        resource="none",
        reason="User token issued successfully",
        delegated_user=req.user_id
    )

    return {"access_token": token, "token_type": "Bearer"}

@app.post("/token/verify")
def verify_token(req: VerifyRequest):
    payload = token_manager.verify_token(req.token)
    if not payload:
        raise HTTPException(status_code=401, detail={
            "error": "invalid_token",
            "error_description": "Token is invalid or expired"
        })
    
    audit_logger.log_event(
        event_type="token_verified",
        decision="allow",
        requestor_agent_id=payload.get("agent_id", "unknown"),
        target_agent_id="none",
        action="token_verification",
        resource="none",
        reason="Token verified successfully"
    )
    
    return {"valid": True, "payload": payload}

@app.post("/token/revoke")
def revoke_token(req: VerifyRequest):
    success = token_manager.revoke_token(req.token)
    if not success:
        raise HTTPException(status_code=400, detail={
            "error": "revocation_failed",
            "error_description": "Token revocation failed"
        })
    monitoring_service.record_token_revoked()
    return {"revoked": True}

@app.post("/auth/call")
def authorize_call(token: str, req: CallRequest):
    payload = token_manager.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail={
            "error": "invalid_token",
            "error_description": "Token is invalid or expired"
        })
    
    requestor_id = payload["agent_id"]
    
    if not permission_checker.check_agent_call_permission(requestor_id, req.target_agent_id, req.action):
        audit_logger.log_event(
            event_type="auth_decision",
            decision="deny",
            requestor_agent_id=requestor_id,
            target_agent_id=req.target_agent_id,
            action=req.action,
            resource=req.resource,
            reason="Missing agent:call capability",
            delegated_user=payload.get("delegated_user"),
            token_id=payload.get("jti")
        )
        monitoring_service.record_auth_decision("deny", requestor_id, req.target_agent_id)
        monitoring_service.record_request(requestor_id, f"auth:call:{req.target_agent_id}")
        raise HTTPException(status_code=403, detail={
            "error": "insufficient_capability",
            "error_description": f"Agent {requestor_id} lacks capability to call {req.target_agent_id}"
        })
    
    call_token = token_manager.generate_temp_call_token(
        original_token=token,
        target_agent_id=req.target_agent_id,
        action=req.action,
        resource=req.resource
    )
    
    audit_logger.log_event(
        event_type="auth_decision",
        decision="allow",
        requestor_agent_id=requestor_id,
        target_agent_id=req.target_agent_id,
        action=req.action,
        resource=req.resource,
        reason="Authorization granted",
        delegated_user=payload.get("delegated_user"),
        token_id=payload.get("jti")
    )
    monitoring_service.record_auth_decision("allow", requestor_id, req.target_agent_id)
    monitoring_service.record_request(requestor_id, f"auth:call:{req.target_agent_id}")

    return {"call_token": call_token, "status": "authorized"}

@app.post("/auth/verify-call")
def verify_call(req: VerifyRequest):
    payload = token_manager.verify_token(req.token)
    if not payload:
        raise HTTPException(status_code=401, detail={
            "error": "invalid_token",
            "error_description": "Call token is invalid or expired"
        })
    
    target_agent = payload.get("target_agent_id")
    action = payload.get("action")
    resource = payload.get("resource")
    requestor_id = payload.get("agent_id")
    
    if target_agent and action:
        if not permission_checker.check_capability(target_agent, action):
            audit_logger.log_event(
                event_type="auth_decision",
                decision="deny",
                requestor_agent_id=requestor_id,
                target_agent_id=target_agent,
                action=action,
                resource=resource or "none",
                reason=f"Target agent lacks required capability: {action}",
                delegated_user=payload.get("delegated_user"),
                token_id=payload.get("jti")
            )
            raise HTTPException(status_code=403, detail={
                "error": "target_capability insufficient",
                "error_description": f"Target agent {target_agent} lacks capability: {action}"
            })
    
    audit_logger.log_event(
        event_type="auth_decision",
        decision="allow",
        requestor_agent_id=requestor_id,
        target_agent_id=target_agent or "none",
        action=action or "none",
        resource=resource or "none",
        reason="Call verification successful",
        delegated_user=payload.get("delegated_user"),
        token_id=payload.get("jti")
    )
    
    return {"valid": True, "payload": payload}

@app.get("/agent/capabilities/{agent_id}")
def get_agent_capabilities(agent_id: str):
    caps = AGENT_STATIC_CAPABILITIES.get(agent_id)
    if not caps:
        raise HTTPException(status_code=404, detail={
            "error": "agent_not_found",
            "error_description": f"Agent {agent_id} not found"
        })
    return {"agent_id": agent_id, "capabilities": caps}

@app.get("/capabilities/all")
def get_all_capabilities():
    return {
        "capability_statements": {
            "agents": {
                agent_id: {
                    "capabilities": caps,
                    "description": get_agent_description(agent_id),
                    "type": "agent"
                }
                for agent_id, caps in AGENT_STATIC_CAPABILITIES.items()
            },
            "users": {
                user_id: {
                    "capabilities": caps,
                    "description": f"User {user_id} with full data access",
                    "type": "user"
                }
                for user_id, caps in USER_STATIC_CAPABILITIES.items()
            }
        }
    }

def get_agent_description(agent_id: str) -> str:
    descriptions = {
        "doc-assistant": "文档助手 - 任务协调中枢，可代表用户调用其他Agent",
        "data-agent": "企业数据Agent - 提供内部数据查询服务",
        "search-agent": "外部检索Agent - 提供互联网搜索服务"
    }
    return descriptions.get(agent_id, "Unknown Agent")

@app.get("/delegation/intersect")
def get_delegation_intersection(user_id: str, agent_id: str):
    user_caps = set(USER_STATIC_CAPABILITIES.get(user_id, []))
    agent_caps = set(AGENT_STATIC_CAPABILITIES.get(agent_id, []))

    intersection = user_caps & agent_caps
    union = user_caps | agent_caps

    return {
        "user_id": user_id,
        "agent_id": agent_id,
        "user_capabilities": sorted(list(user_caps)),
        "agent_capabilities": sorted(list(agent_caps)),
        "effective_capabilities": sorted(list(intersection)),
        "union_capabilities": sorted(list(union)),
        "intersection_count": len(intersection),
        "calculation": f"{user_id}权限 ∩ {agent_id}能力 = {sorted(list(intersection))}"
    }

@app.post("/delegation/authorize")
def authorize_delegated_action(user_id: str, agent_id: str, action: str):
    user_caps = set(USER_STATIC_CAPABILITIES.get(user_id, []))
    agent_caps = set(AGENT_RUNTIME_CAPABILITIES.get(agent_id, []))

    intersection = user_caps & agent_caps

    if action in intersection:
        return {
            "authorized": True,
            "action": action,
            "user_id": user_id,
            "agent_id": agent_id,
            "reason": f"Action '{action}' is in effective permissions (user ∩ agent)",
            "effective_permissions": sorted(list(intersection))
        }
    else:
        return {
            "authorized": False,
            "action": action,
            "user_id": user_id,
            "agent_id": agent_id,
            "reason": f"Action '{action}' not in effective permissions. User has {sorted(list(user_caps))}, agent has {sorted(list(agent_caps))}",
            "effective_permissions": sorted(list(intersection))
        }

@app.post("/capabilities/dynamic/update")
def update_agent_capabilities(agent_id: str, capabilities: List[str]):
    if agent_id not in AGENT_RUNTIME_CAPABILITIES:
        raise HTTPException(status_code=404, detail="Agent not found")

    old_caps = AGENT_RUNTIME_CAPABILITIES[agent_id].copy()
    AGENT_RUNTIME_CAPABILITIES[agent_id] = capabilities

    audit_logger.log_event(
        event_type="capability_update",
        decision="update",
        requestor_agent_id="system:admin",
        target_agent_id=agent_id,
        action="capability:update",
        resource="runtime_capabilities",
        reason=f"动态权限更新: {old_caps} → {capabilities}"
    )

    return {
        "agent_id": agent_id,
        "old_capabilities": old_caps,
        "new_capabilities": capabilities,
        "updated_at": datetime.now(BEIJING_TZ).isoformat()
    }

@app.post("/capabilities/dynamic/revoke-capability")
def revoke_agent_capability(agent_id: str, capability: str):
    if agent_id not in AGENT_RUNTIME_CAPABILITIES:
        raise HTTPException(status_code=404, detail="Agent not found")

    if capability not in AGENT_RUNTIME_CAPABILITIES[agent_id]:
        return {
            "success": False,
            "message": f"Capability '{capability}' not found in agent capabilities"
        }

    old_caps = AGENT_RUNTIME_CAPABILITIES[agent_id].copy()
    AGENT_RUNTIME_CAPABILITIES[agent_id].remove(capability)

    audit_logger.log_event(
        event_type="capability_revoke",
        decision="revoked",
        requestor_agent_id="system:admin",
        target_agent_id=agent_id,
        action="capability:revoke",
        resource=capability,
        reason=f"动态撤销权限: {capability} from {agent_id}"
    )

    return {
        "success": True,
        "agent_id": agent_id,
        "revoked_capability": capability,
        "remaining_capabilities": AGENT_RUNTIME_CAPABILITIES[agent_id]
    }

@app.post("/capabilities/dynamic/grant-capability")
def grant_agent_capability(agent_id: str, capability: str):
    if agent_id not in AGENT_RUNTIME_CAPABILITIES:
        raise HTTPException(status_code=404, detail="Agent not found")

    if capability in AGENT_RUNTIME_CAPABILITIES[agent_id]:
        return {
            "success": False,
            "message": f"Capability '{capability}' already exists"
        }

    old_caps = AGENT_RUNTIME_CAPABILITIES[agent_id].copy()
    AGENT_RUNTIME_CAPABILITIES[agent_id].append(capability)

    audit_logger.log_event(
        event_type="capability_grant",
        decision="granted",
        requestor_agent_id="system:admin",
        target_agent_id=agent_id,
        action="capability:grant",
        resource=capability,
        reason=f"动态授予权限: {capability} to {agent_id}"
    )

    return {
        "success": True,
        "agent_id": agent_id,
        "granted_capability": capability,
        "all_capabilities": AGENT_RUNTIME_CAPABILITIES[agent_id]
    }

@app.get("/agent/info/{agent_id}")
def get_agent_info(agent_id: str):
    config = AGENT_CONFIG.get(agent_id)
    if not config:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {
        "agent_id": agent_id,
        "static_capabilities": AGENT_STATIC_CAPABILITIES.get(agent_id, []),
        "runtime_capabilities": AGENT_RUNTIME_CAPABILITIES.get(agent_id, []),
        "config": config
    }

@app.get("/agents/heterogeneous")
def get_heterogeneous_agents():
    agents = []
    for agent_id, config in AGENT_CONFIG.items():
        agents.append({
            "agent_id": agent_id,
            "name": config.get("name"),
            "model": config.get("model"),
            "engine": config.get("engine"),
            "tools": config.get("tools"),
            "description": config.get("description"),
            "capabilities": AGENT_RUNTIME_CAPABILITIES.get(agent_id, []),
            "port": AGENT_PORTS.get(agent_id)
        })
    return {"agents": agents}

@app.post("/token/reissue")
def reissue_token_with_new_caps(token: str, new_capabilities: List[str]):
    verify_resp = verify_token(token)
    if not verify_resp.get("valid"):
        raise HTTPException(status_code=401, detail="Invalid token")

    payload = verify_resp.get("payload", {})
    agent_id = payload.get("agent_id")

    token_manager.revoke_token(token)

    new_token = token_manager.generate_token(
        agent_id=agent_id,
        agent_role=payload.get("role"),
        capabilities=new_capabilities
    )

    return {
        "reissued": True,
        "old_token_revoked": True,
        "new_token": new_token,
        "new_capabilities": new_capabilities,
        "agent_id": agent_id
    }

@app.post("/token/validate-security")
def validate_token_security(token: str, client_ip: Optional[str] = None):
    verify_resp = verify_token(token)
    if not verify_resp.get("valid"):
        return {
            "valid": False,
            "error": "Token已过期或无效",
            "security_status": "compromised_or_expired"
        }

    payload = verify_resp.get("payload", {})
    issues = []

    if payload.get("type") == "access" and payload.get("agent_id"):
        pass

    if issues:
        return {
            "valid": True,
            "security_status": "warning",
            "warnings": issues
        }
    else:
        return {
            "valid": True,
            "security_status": "secure",
            "token_info": {
                "agent_id": payload.get("agent_id"),
                "type": payload.get("type"),
                "issued_at": payload.get("iat"),
                "expires_at": payload.get("exp")
            }
        }

@app.get("/audit/logs")
def get_audit_logs(limit: int = 100, decision: Optional[str] = None, 
                   requestor_agent_id: Optional[str] = None):
    filter_criteria = {}
    if decision:
        filter_criteria["decision"] = decision
    if requestor_agent_id:
        filter_criteria["requestor_agent_id"] = requestor_agent_id
    
    logs = audit_logger.query_logs(filter_criteria if filter_criteria else None, limit=limit)
    return {"logs": logs, "count": len(logs)}

@app.get("/health")
def health_check():
    health = monitoring_service.check_system_health()
    status_code = 200 if health["healthy"] else 503
    return {"status": "healthy" if health["healthy"] else "degraded", "service": "aegislink-iam", "details": health}

@app.get("/monitoring/metrics")
def get_metrics():
    return monitoring_service.get_metrics()

@app.get("/monitoring/alerts")
def get_alerts(level: Optional[str] = None, limit: int = 100):
    return {"alerts": monitoring_service.get_alerts(level, limit), "count": len(monitoring_service.get_alerts(level, limit))}

@app.post("/monitoring/alert")
def create_alert(level: str, message: str, source: str):
    return {"alert": monitoring_service.trigger_alert(level, message, source).to_dict()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
