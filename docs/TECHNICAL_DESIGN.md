# AegisLink 技术方案设计文档

## 目录

1. [系统概述](#1-系统概述)
2. [系统架构](#2-系统架构)
3. [Access Token设计](#3-access-token设计)
4. [A2A认证流程](#4-a2a认证流程)
5. [API接口定义](#5-api接口定义)
6. [审计日志设计](#6-审计日志设计)
7. [Agent角色与权限](#7-agent角色与权限)

---

## 1. 系统概述

### 1.1 项目背景

传统的身份认证与权限体系(IAM)是围绕"人"建立的，其基本模型是 `User → Application`。但在AI时代，工作流正在演变为一条更长、更复杂的调用链：

```
User → Agent A → Agent B → Service C
```

在这条新范式下，原有的安全假设被打破：
- **身份混淆与权限滥用**：Agent B收到Agent A的请求时，无法确定请求来源
- **信任链的缺失**：信任无法通过网络边界或简单的API Key来传递
- **审计与追溯的黑洞**：无法追溯决策由哪个Agent、在哪条调用链的哪个环节做出

### 1.2 项目目标

构建一个面向AI Agent的通用身份与权限系统(AegisLink)，实现：
- Agent身份认证与Token管理
- 细粒度权限管控(Capability-Based Authorization)
- 委托授权与动态权限计算
- 实时越权行为拦截
- 完整的审计追溯能力

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AegisLink 系统架构                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    │
│  │ 文档助手Agent│    │企业数据Agent│    │外部检索Agent│                    │
│  │ doc-assistant│    │ data-agent  │    │search-agent │                    │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                    │
│         │                    │                    │                          │
│         └────────────────────┼────────────────────┘                          │
│                              │ IAM Service (Port 8000)                       │
│  ┌───────────────────────────┼───────────────────────────────────────────┐  │
│  │                    ┌──────┴──────┐                                      │  │
│  │  ┌─────────────────┤              ├────────────────────┐               │  │
│  │  │   Token Manager │              │ Permission Checker │               │  │
│  │  │  - Token签发    │              │  - 静态权限检查    │               │  │
│  │  │  - Token验证    │              │  - 动态权限计算    │               │  │
│  │  │  - Token撤销    │              │  - 委托授权        │               │  │
│  │  └─────────────────┘              └────────────────────┘               │  │
│  │                                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────┐     │  │
│  │  │                    Audit Logger                               │     │  │
│  │  │  - 记录所有授权决策  - 支持查询/导出  - 完整调用链追踪       │     │  │
│  │  └──────────────────────────────────────────────────────────────┘     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责

| 模块 | 职责 | 文件 |
|-----|------|------|
| Token Manager | JWT Token的生成、验证、撤销 | `src/iam/token_manager.py` |
| Permission Checker | 能力匹配、权限交集计算 | `src/iam/permission_checker.py` |
| Audit Logger | 审计日志记录与查询 | `src/audit/audit_logger.py` |
| Base Agent | Agent抽象基类 | `src/agents/base_agent.py` |
| Doc Assistant | 文档助手Agent | `src/agents/doc_assistant.py` |
| Data Agent | 企业数据Agent | `src/agents/data_agent.py` |
| Search Agent | 外部检索Agent | `src/agents/search_agent.py` |

---

## 3. Access Token设计

### 3.1 Token结构

采用JWT(JSON Web Token)标准格式，包含以下字段：

```json
{
  "iss": "aegislink-iam",           // 签发者，固定为系统标识
  "sub": "agent:doc-assistant",       // 主体，格式: agent:{agent_id}
  "agent_id": "doc-assistant",        // Agent唯一标识
  "agent_role": "doc_writer",        // Agent角色
  "iat": 1777000000.0,               // 签发时间(Unix时间戳)
  "exp": 1777003600.0,               // 过期时间(默认1小时)
  "jti": "unique-token-id-uuid",    // Token唯一ID，用于撤销追踪
  "delegated_user": "user:1001",    // 委托的用户ID(可选)
  "capabilities": [                   // 能力声明数组
    "doc:read",
    "doc:write",
    "agent:call:data-agent",
    "agent:call:search-agent"
  ],
  "trust_chain": [                   // 信任链，记录完整调用路径
    {
      "agent_id": "doc-assistant",
      "timestamp": 1777000000.0,
      "action": "data:read:spreadsheet",
      "resource": "spreadsheet:weekly-sales"
    }
  ]
}
```

### 3.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| iss | string | 是 | 签发者标识，固定为"aegislink-iam" |
| sub | string | 是 | 主体，格式"agent:{agent_id}" |
| agent_id | string | 是 | Agent唯一标识 |
| agent_role | string | 是 | Agent角色名称 |
| iat | number | 是 | 签发时间戳 |
| exp | number | 是 | 过期时间戳 |
| jti | string | 是 | Token唯一ID(UUID) |
| delegated_user | string | 否 | 委托的用户ID |
| capabilities | array | 是 | 能力声明列表 |
| trust_chain | array | 否 | 调用链记录 |

### 3.3 Token类型

| 类型 | 有效期 | 用途 |
|-----|-------|------|
| Access Token | 1小时 | Agent注册后获取，长期有效 |
| Call Token | 10分钟 | Agent间调用的临时Token |

---

## 4. A2A认证流程

### 4.1 正常委托流程

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│   User   │     │ Doc-     │     │   IAM    │     │  Data-   │
│          │     │ Assistant│     │ Service  │     │  Agent   │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │
     │ Create Report  │                │                │
     │───────────────>│                │                │
     │                │                │                │
     │                │ POST /auth/call                │
     │                │───────────────>│                │
     │                │                │                │
     │                │  Verify Token  │                │
     │                │  Check Caps    │                │
     │                │<──────────────>│                │
     │                │                │                │
     │                │ Return Call Token               │
     │                │<───────────────│                │
     │                │                │                │
     │                │ GET /read-spreadsheet?token=xxx │
     │                │────────────────────────────────>│
     │                │                │                │
     │                │  Verify Call   │                │
     │                │  Token         │                │
     │                │<────────────────────────────────│
     │                │                │                │
     │                │   Return Data │                │
     │                │<────────────────────────────────│
     │                │                │                │
     │   Report       │                │                │
     │<───────────────│                │                │
     │                │                │                │
```

### 4.2 越权拦截流程

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Search- │     │   IAM    │     │  Data-   │
│  Agent   │     │ Service  │     │  Agent   │
└────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │
     │ POST /auth/call│                │
     │ (try to call   │                │
     │  data-agent)   │                │
     │───────────────>│                │
     │                │                │
     │ Verify Token   │                │
     │ Check Caps     │                │
     │<──────────────>│                │
     │                │                │
     │ ❌ DENY: missing│                │
     │    agent:call  │                │
     │    :data-agent │                │
     │<───────────────│                │
     │                │                │
     │ 403 Forbidden  │                │
     │ insufficient_  │                │
     │ capability     │                │
     │                │                │
```

### 4.3 信任链机制

每次Agent间调用都会在trust_chain中记录：

```json
"trust_chain": [
  {
    "agent_id": "doc-assistant",
    "timestamp": 1777000000.0,
    "action": "data:read:spreadsheet",
    "resource": "spreadsheet:weekly-sales"
  }
]
```

---

## 5. API接口定义

### 5.1 IAM服务API (端口 8000)

#### 5.1.1 Token签发
```
POST /token/issue
Content-Type: application/json

Request:
{
  "agent_id": "doc-assistant",
  "agent_role": "doc_writer",
  "delegated_user": "user:1001"  // 可选
}

Response (200):
{
  "access_token": "eyJhbGci...",
  "token_type": "Bearer"
}
```

#### 5.1.2 Token验证
```
POST /token/verify
Content-Type: application/json

Request:
{
  "token": "eyJhbGci..."
}

Response (200):
{
  "valid": true,
  "payload": { ... }
}

Response (401):
{
  "detail": {
    "error": "invalid_token",
    "error_description": "Token is invalid or expired"
  }
}
```

#### 5.1.3 授权调用请求
```
POST /auth/call?token={access_token}
Content-Type: application/json

Request:
{
  "target_agent_id": "data-agent",
  "action": "data:read:spreadsheet",
  "resource": "spreadsheet:weekly-sales"
}

Response (200):
{
  "call_token": "eyJhbGci...",
  "status": "authorized"
}

Response (403):
{
  "detail": {
    "error": "insufficient_capability",
    "error_description": "Agent search-agent lacks capability to call data-agent"
  }
}
```

#### 5.1.4 验证调用Token
```
POST /auth/verify-call
Content-Type: application/json

Request:
{
  "token": "call_token_from_auth_call"
}

Response (200):
{
  "valid": true,
  "payload": { ... }
}
```

#### 5.1.5 获取Agent能力
```
GET /agent/capabilities/{agent_id}

Response (200):
{
  "agent_id": "doc-assistant",
  "capabilities": ["doc:read", "doc:write", ...]
}
```

#### 5.1.6 查询审计日志
```
GET /audit/logs?limit=100&decision=allow&requestor_agent_id=doc-assistant

Response (200):
{
  "logs": [...],
  "count": 100
}
```

#### 5.1.7 健康检查
```
GET /health

Response (200):
{
  "status": "healthy",
  "service": "aegislink-iam"
}
```

### 5.2 Agent服务API

#### 5.2.1 文档助手 - 创建任务
```
POST /task
Content-Type: application/json

Request:
{
  "task": "生成周报",
  "user_id": "user:1001"
}

Response (200):
{
  "status": "success",
  "report": "...",
  "data_source": "data-agent",
  "search_source": "search-agent",
  "delegated_user": "user:1001"
}
```

#### 5.2.2 企业数据 - 读取表格
```
GET /read-spreadsheet?token={call_token}&spreadsheet_id={id}

Response (200):
{
  "status": "success",
  "data": { ... }
}
```

#### 5.2.3 外部检索 - 搜索
```
GET /search?token={call_token}&query={query}

Response (200):
{
  "status": "success",
  "query": "market trends 2026",
  "results": [...]
}
```

---

## 6. 审计日志设计

### 6.1 日志字段

每条审计日志包含：

```json
{
  "log_id": "67950317-f1c8-475b-9179-33d352326fac",
  "timestamp": "2026-04-24T04:07:51.653278",
  "event_type": "auth_decision",
  "decision": "allow",
  "requestor_agent_id": "doc-assistant",
  "target_agent_id": "data-agent",
  "action": "data:read:spreadsheet",
  "resource": "spreadsheet:weekly-sales",
  "delegated_user": "user:1001",
  "token_id": "call-token-uuid",
  "reason": "Authorization granted",
  "request_id": "req-uuid"
}
```

### 6.2 字段说明

| 字段 | 类型 | 说明 |
|-----|------|------|
| log_id | string | 日志唯一ID(UUID) |
| timestamp | string | ISO格式时间戳 |
| event_type | string | 事件类型 |
| decision | string | allow/deny |
| requestor_agent_id | string | 请求方Agent |
| target_agent_id | string | 目标Agent |
| action | string | 操作类型 |
| resource | string | 资源标识 |
| delegated_user | string | 委托用户 |
| token_id | string | Token ID |
| reason | string | 决策原因 |
| request_id | string | 请求ID |

### 6.3 事件类型

| event_type | 说明 |
|------------|------|
| token_issued | Token签发 |
| token_verified | Token验证 |
| token_expired | Token过期 |
| token_invalid | Token无效 |
| token_revoked | Token撤销 |
| auth_decision | 授权决策 |
| auth_call_verified | 调用验证 |

---

## 7. Agent角色与权限

### 7.1 角色定义

| Agent | 角色 | 描述 |
|-------|------|------|
| doc-assistant | doc_writer | 文档助手，负责协调其他Agent生成报告 |
| data-agent | data_provider | 企业数据Agent，唯一有权访问企业内部数据 |
| search-agent | web_searcher | 外部检索Agent，只能搜索公开信息 |

### 7.2 权限配置

| Agent | 静态权限(Capabilities) |
|-------|----------------------|
| doc-assistant | doc:read, doc:write, agent:call:data-agent, agent:call:search-agent |
| data-agent | data:read:spreadsheet, data:read:contact, data:read:calendar |
| search-agent | web:search |

### 7.3 权限模型

- **静态授权**：Agent注册时由管理员预分配的权限集合
- **动态授权**：运行时根据上下文计算的临时权限
- **权限交集**：委托授权时，有效权限 = 用户权限 ∩ Agent能力

---

## 8. 安全特性

### 8.1 Token安全

- **签名算法**：HS256 (HMAC with SHA-256)
- **有效期**：Access Token 1小时，Call Token 10分钟
- **撤销机制**：支持Token实时撤销

### 8.2 防御措施

- **身份混淆**：通过JWT签名验证确保Token不可伪造
- **越权拦截**：每次调用前强制权限校验
- **审计追溯**：完整记录所有授权决策

---

## 9. 扩展性说明

### 9.1 接入新Agent

1. 继承BaseAgent类
2. 定义Agent ID和角色
3. 配置静态权限
4. 实现业务逻辑

### 9.2 扩展权限模型

可在PermissionChecker中新增权限校验逻辑：

```python
def check_custom_permission(self, agent_id: str, permission: str) -> bool:
    # 自定义权限校验逻辑
    pass
```

---

## 10. 动态授权与Token安全

### 10.1 动态权限管理

系统支持运行时动态修改Agent权限：

```
POST /capabilities/dynamic/grant-capability
POST /capabilities/dynamic/revoke-capability
```

权限变更立即生效，所有变更记录审计日志。

### 10.2 委托授权 - 权限交集计算

当Agent代表用户执行操作时，有效权限 = 用户权限 ∩ Agent能力：

```
GET /delegation/intersect?user_id=user:1001&agent_id=doc-assistant
```

返回：
- user_capabilities: 用户权限列表
- agent_capabilities: Agent能力列表
- effective_capabilities: 交集（有效权限）
- calculation: 计算公式

### 10.3 Token安全机制

| API | 功能 |
|-----|------|
| `/token/revoke` | 实时撤销Token，撤销后立即失效 |
| `/token/validate-security` | Token安全验证，检测异常 |
| `/token/reissue` | 重新签发Token，带新权限集 |

### 10.4 异构Agent接入

系统支持不同模型、不同引擎、不同工具集的Agent统一接入：

```
GET /agents/heterogeneous
```

返回每个Agent的：
- agent_id: Agent标识
- name: Agent名称
- model: 使用的模型
- engine: 推理引擎
- tools: 工具集
- capabilities: 当前能力列表
- port: 服务端口

---

## 11. 系统配置

### 11.1 支持的LLM供应商

| 供应商 | Base URL | 模型示例 |
|-------|----------|---------|
| 360 AI | https://api.360.cn/v1 | deepseek-v3.2 |
| OpenRouter | https://openrouter.ai/api/v1 | anthropic/claude-3.5-sonnet |
| Azure OpenAI | https://{resource}.openai.azure.com | gpt-4o |
| OpenAI | https://api.openai.com/v1 | gpt-4o |
| Anthropic | https://api.anthropic.com | claude-3-5-sonnet |

### 11.2 支持的搜索API供应商

| 供应商 | 说明 |
|-------|------|
| Tavily | 深度搜索API |
| SerpAPI | Google搜索 |
| Google Search | Google搜索API |
| Bing | Bing搜索 |
| DuckDuckGo |  DuckDuckGo搜索 |

---

本文档为AegisLink系统的完整技术方案设计，涵盖架构、协议、API、安全等全部核心内容。
