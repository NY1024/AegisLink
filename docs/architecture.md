# AegisLink 系统架构设计

## 1. 系统整体架构
AegisLink是面向AI Agent的身份与权限系统，采用分层架构：
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  文档助手Agent  │    │ 企业数据Agent   │    │ 外部检索Agent   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
          │                    │                      │
          └────────────────────┼──────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     AegisLink IAM服务                       │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│ Token管理   │ 权限校验    │ 委托授权    │ 审计日志系统      │
└─────────────┴─────────────┴─────────────┴──────────────────┘
```

## 2. Access Token 设计（基于JWT）
采用JWT标准格式，包含以下字段：
```json
{
  "iss": "aegislink-iam",          // 签发者
  "sub": "agent:doc-assistant",    // 主体，Agent唯一标识
  "agent_id": "doc-assistant",     // Agent ID
  "agent_role": "doc_writer",      // Agent角色
  "iat": 1714000000,               // 签发时间
  "exp": 1714003600,               // 过期时间
  "jti": "token-123456",           // Token唯一ID
  "delegated_user": "user:1001",   // 委托的用户ID（可选）
  "capabilities": [                // 能力声明
    "doc:read",
    "doc:write",
    "agent:call:data-agent"
  ],
  "trust_chain": [                 // 信任链
    {
      "agent_id": "doc-assistant",
      "timestamp": 1714000000,
      "signature": "xxx"
    }
  ]
}
```

## 3. 权限模型
- **静态权限**：Agent注册时预先分配的能力集合，存储在IAM系统中
- **动态权限**：运行时根据上下文临时生成的权限，有效期短
- **权限交集计算**：委托授权时，权限 = 用户权限 ∩ Agent自身能力

## 4. A2A 认证流程
Agent A调用Agent B的流程：
1. Agent A携带自身的Access Token向IAM服务请求调用Agent B的授权
2. IAM验证Agent A的Token有效性，检查是否具备调用Agent B的权限
3. 验证通过后，IAM签发临时调用Token给Agent A
4. Agent A携带临时Token调用Agent B的接口
5. Agent B将Token提交给IAM验证，验证通过后执行请求
6. 所有步骤都记录到审计日志

## 5. 审计日志字段
每条审计日志包含：
```json
{
  "log_id": "log-123456",
  "timestamp": 1714000000,
  "event_type": "auth_decision",
  "decision": "allow/deny",
  "requestor_agent_id": "doc-assistant",
  "target_agent_id": "data-agent",
  "action": "data:read:spreadsheet",
  "resource": "spreadsheet:12345",
  "delegated_user": "user:1001",
  "token_id": "token-123456",
  "reason": "权限校验通过/缺少对应能力",
  "request_id": "req-123456"
}
```

## 6. Agent角色与权限定义
| Agent名称 | 角色 | 静态权限 |
|---------|------|---------|
| 飞书文档助手Agent | doc_assistant | doc:read, doc:write, agent:call:data-agent, agent:call:search-agent |
| 企业数据Agent | data_provider | data:read:spreadsheet, data:read:contact, data:read:calendar |
| 外部检索Agent | web_searcher | web:search, agent:call:* (无企业数据访问权限) |
