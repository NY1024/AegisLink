import requests
from typing import Dict, Optional, Any
from src.common.config import IAM_SERVICE_HOST, IAM_SERVICE_PORT

class BaseAgent:
    def __init__(self, agent_id: str, agent_role: str, auto_register: bool = False, delegated_user: str = None):
        self.agent_id = agent_id
        self.agent_role = agent_role
        self.delegated_user = delegated_user
        self.access_token: Optional[str] = None
        self.iam_base_url = f"http://{IAM_SERVICE_HOST}:{IAM_SERVICE_PORT}"
        if auto_register:
            self.register(delegated_user)

    def _ensure_registered(self):
        if not self.access_token:
            self.register(self.delegated_user)

    def register(self, delegated_user: Optional[str] = None) -> str:
        du = delegated_user or self.delegated_user
        response = requests.post(
            f"{self.iam_base_url}/token/issue",
            json={
                "agent_id": self.agent_id,
                "agent_role": self.agent_role,
                "delegated_user": du
            }
        )
        if response.status_code == 200:
            self.access_token = response.json()["access_token"]
            return self.access_token
        raise Exception(f"Token issuance failed: {response.text}")

    def verify_token(self) -> Dict:
        self._ensure_registered()
        response = requests.post(
            f"{self.iam_base_url}/token/verify",
            json={"token": self.access_token}
        )
        if response.status_code == 200:
            return response.json()["payload"]
        raise Exception(f"Token verification failed: {response.text}")

    def request_call_auth(self, target_agent_id: str, action: str, resource: str) -> str:
        self._ensure_registered()
        response = requests.post(
            f"{self.iam_base_url}/auth/call",
            params={"token": self.access_token},
            json={
                "target_agent_id": target_agent_id,
                "action": action,
                "resource": resource
            }
        )
        if response.status_code == 200:
            return response.json()["call_token"]
        raise Exception(f"Call authorization failed: {response.status_code} - {response.text}")

    def call_agent(self, target_agent_id: str, action: str, resource: str, call_token: str, method: str = "GET", data: Optional[Dict] = None) -> Dict:
        port_map = {
            "data-agent": 8002,
            "search-agent": 8003,
            "doc-assistant": 8001
        }

        endpoint_map = {
            "data:read:spreadsheet": "read-spreadsheet",
            "data:read:contact": "read-contact",
            "data:read:calendar": "read-calendar",
            "web:search": "search"
        }

        params = {"token": call_token}

        if "spreadsheet" in action:
            params["spreadsheet_id"] = resource
        elif "contact" in action:
            params["contact_id"] = resource
        elif "calendar" in action:
            params["calendar_id"] = resource
        elif resource.startswith("web:"):
            params["query"] = resource.split(":")[-1]

        endpoint = endpoint_map.get(action, action.replace(":", "/"))
        port = port_map.get(target_agent_id, 8000)

        print(f"[DEBUG] call_agent: action={action}, resource={resource}, params={params}")

        response = requests.request(
            method=method,
            url=f"http://{IAM_SERVICE_HOST}:{port}/{endpoint}",
            params=params,
            json=data or {}
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 403:
            result = response.json()
            raise PermissionError(f"Access denied: {result.get('detail', {}).get('error_description', 'Unknown')}")
        else:
            raise Exception(f"Agent call failed: {response.status_code} - {response.text}")

    def get_capabilities(self) -> list:
        self._ensure_registered()
        response = requests.get(f"{self.iam_base_url}/agent/capabilities/{self.agent_id}")
        if response.status_code == 200:
            return response.json()["capabilities"]
        raise Exception(f"Failed to get capabilities: {response.text}")
