import os
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "***")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_SECONDS = 3600
TEMP_TOKEN_EXPIRE_SECONDS = 600

IAM_SERVICE_HOST = "0.0.0.0"
IAM_SERVICE_PORT = 8000

AGENT_PORTS = {
    "doc-assistant": 8001,
    "data-agent": 8002,
    "search-agent": 8003
}

AGENT_STATIC_CAPABILITIES = {
    "doc-assistant": [
        "doc:read",
        "doc:write",
        "agent:call:data-agent",
        "agent:call:search-agent"
    ],
    "data-agent": [
        "data:read:spreadsheet",
        "data:read:contact",
        "data:read:calendar"
    ],
    "search-agent": [
        "web:search"
    ]
}

AGENT_RUNTIME_CAPABILITIES = {
    "doc-assistant": [
        "doc:read",
        "doc:write",
        "agent:call:data-agent",
        "agent:call:search-agent"
    ],
    "data-agent": [
        "data:read:spreadsheet",
        "data:read:contact",
        "data:read:calendar"
    ],
    "search-agent": [
        "web:search"
    ]
}

AGENT_CONFIG = {
    "doc-assistant": {
        "name": "文档助手",
        "model": "deepseek-v3.2",
        "engine": "360 AI",
        "tools": ["llm", "data-agent", "search-agent"],
        "description": "基于大模型的协调Agent，可代表用户调用其他Agent"
    },
    "data-agent": {
        "name": "企业数据Agent",
        "model": "deepseek-v3.2",
        "engine": "360 AI",
        "tools": ["internal_data"],
        "description": "提供企业内部数据查询服务"
    },
    "search-agent": {
        "name": "外部检索Agent",
        "model": "deepseek-v3.2",
        "engine": "360 AI",
        "tools": ["tavily_search", "llm"],
        "description": "提供互联网搜索服务"
    }
}

USER_PERMISSIONS = {
    "user:1001": [
        "data:read:spreadsheet",
        "data:read:contact",
        "data:read:calendar",
        "doc:read",
        "doc:write",
        "web:search"
    ]
}

USER_STATIC_CAPABILITIES = {
    "user:1001": [
        "data:read:spreadsheet",
        "data:read:contact",
        "data:read:calendar",
        "doc:read",
        "doc:write",
        "web:search"
    ]
}
