# AegisLink Agent身份与权限系统

## 项目简介

AegisLink是一个面向多Agent协作场景的身份与权限管理系统，为AI Agent提供企业级的安全保障。通过JWT Token实现Agent身份认证、基于能力声明的细粒度权限控制、委托授权与动态权限计算、实时越权拦截以及完整的审计追溯能力。

---

## 环境配置

### 环境要求

- Python 3.10+
- pip

### 安装步骤

```bash
# 1. 进入项目目录
cd /Users/elwood/Desktop/test/AegisLink

# 2. 创建虚拟环境（推荐）
python3 -m venv venv

# 3. 激活虚拟环境
source venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 安装Tavily搜索API客户端（如需使用搜索功能）
pip install tavily
```

### 配置文件

系统使用以下环境变量（可在 `.env` 文件中配置）：

```bash
# JWT密钥
JWT_SECRET_KEY="aegislink-super-secret-key-2026!!"

# LLM API配置（360 AI）
LLM_API_KEY="fk3468961406.sTKRtoJ_flJSlI0u28kLOqFTWPqdOyRSa204f806"
LLM_BASE_URL="https://api.360.cn/v1"
LLM_MODEL="deepseek-v3.2"

# Tavily搜索API（如需使用搜索功能）
TAVILY_API_KEY="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"
```

---

## 启动服务

### 方式一：脚本启动（推荐）

```bash
# 启动所有服务
bash scripts/start_all.sh

# 停止所有服务
bash scripts/stop_all.sh
```

### 方式二：手动启动

```bash
# 终端1: 启动IAM服务
source venv/bin/activate
cd /Users/elwood/Desktop/test/AegisLink
python -m src.iam.service

# 终端2: 启动文档助手Agent
source venv/bin/activate
cd /Users/elwood/Desktop/test/AegisLink
python -m src.agents.doc_assistant

# 终端3: 启动企业数据Agent
source venv/bin/activate
cd /Users/elwood/Desktop/test/AegisLink
python -m src.agents.data_agent

# 终端4: 启动外部检索Agent
source venv/bin/activate
cd /Users/elwood/Desktop/test/AegisLink
python -m src.agents.search_agent

# 终端5: 启动Web控制台
source venv/bin/activate
cd /Users/elwood/Desktop/test/AegisLink
python -m src.web_console
```

---

## 服务端口

| 服务 | 端口 | 描述 |
|-----|------|------|
| IAM授权服务 | 8000 | Token签发、验证、权限校验、监控 |
| 文档助手Agent | 8001 | 协调其他Agent生成报告 |
| 企业数据Agent | 8002 | 提供企业内部数据 |
| 外部检索Agent | 8003 | 提供外部公开信息 |
| Web控制台 | 8080 | 可视化界面 |

---

## Web可视化界面

启动服务后，打开浏览器访问：

```
http://localhost:8080/static/index.html
```

### 界面功能导航

| 页面 | 功能 |
|-----|------|
| 📊 总览 | 系统健康检查、核心指标展示 |
| ⚡ 验收测试 | 完整的测试流程向导 |
| 💬 Agent对话 | 与Agent自由对话，测试工具调用 |
| 🔗 Agent拓扑 | Agent职责分工、交互链路图 |
| 🔍 任务追踪 | 任务在多Agent间的流转过程 |
| 🔑 Token管理 | Token签发、查询、撤销、追溯 |
| 📋 审计日志 | 完整授权决策记录查询 |
| 📈 监控告警 | 系统指标、告警信息 |
| 🔐 权限管理 | 动态授权、权限交集计算、异构Agent |
| ⚙️ 系统配置 | LLM/搜索API供应商配置、Agent接入 |

---

## 验收步骤（评委复现指南）

### 步骤1: 启动系统

```bash
bash scripts/start_all.sh
```

**预期结果**: 显示4个服务启动信息

### 步骤2: Web界面健康检查

打开 http://localhost:8080/static/index.html#overview

**预期结果**: 显示所有服务状态为"运行中"

### 步骤3: Token签发

**Web界面**: 访问"🔑 Token管理"页面，点击"签发Token"

**或命令行**:
```bash
curl -s -X POST http://localhost:8000/token/issue \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"doc-assistant","agent_role":"coordinator","delegated_user":"user:1001"}'
```

### 步骤4: 正常委托流程

**Web界面**: 访问"⚡ 验收测试"页面，点击"执行正常委托"

或发送请求：
```bash
curl -X POST http://localhost:8001/task \
  -H "Content-Type: application/json" \
  -d '{"task":"查看公司通讯录","user_id":"user:1001"}'
```

**预期结果**: 返回通讯录数据（8名员工，7个部门）

### 步骤5: 越权拦截流程

**Web界面**: 访问"⚡ 验收测试"页面，点击"执行越权测试"

或直接测试：
```bash
curl -X POST http://localhost:8003/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"调用企业数据Agent获取内部数据"}'
```

**预期结果**: 返回403越权拦截错误

### 步骤6: 审计日志查看

**Web界面**: 访问"📋 审计日志"页面，点击"刷新日志"

**预期结果**: 显示完整的授权决策记录

### 步骤7: Token撤销测试

**Web界面**: 访问"🔑 Token管理"页面，查询Token后点击"撤销"

**预期结果**: Token被撤销后立即失效

### 步骤8: 异常场景测试

**Web界面**: 访问"⚡ 验收测试"页面，找到"步骤7/7: 异常场景处理"

可以测试：
- 权限不足拦截
- Token过期验证
- Agent不可用
- 数据不存在

---

## 核心API接口

### IAM服务API (端口 8000)

| 接口 | 方法 | 描述 |
|-----|------|------|
| `/token/issue` | POST | Agent Token签发 |
| `/token/issue-user` | POST | 用户Token签发 |
| `/token/verify` | POST | Token验证 |
| `/token/revoke` | POST | Token撤销（实时） |
| `/token/validate-security` | POST | Token安全验证 |
| `/token/reissue` | POST | Token重新签发（带新权限） |
| `/auth/call` | POST | Agent间调用授权 |
| `/auth/verify-call` | POST | 调用Token验证 |
| `/agent/capabilities/{id}` | GET | 查询Agent静态权限 |
| `/capabilities/all` | GET | 查询所有Agent能力声明 |
| `/capabilities/dynamic/grant-capability` | POST | 动态授予权限 |
| `/capabilities/dynamic/revoke-capability` | POST | 动态撤销权限 |
| `/delegation/intersect` | GET | 计算用户权限∩Agent能力 |
| `/delegation/authorize` | POST | 验证操作授权 |
| `/agents/heterogeneous` | GET | 获取异构Agent信息 |
| `/agent/info/{id}` | GET | 获取Agent详细信息 |
| `/audit/logs` | GET | 审计日志查询 |
| `/monitoring/metrics` | GET | 系统指标 |
| `/monitoring/alerts` | GET | 告警查询 |
| `/health` | GET | 健康检查 |

### Agent服务API

| 接口 | 方法 | 描述 |
|-----|------|------|
| `POST /task` | 文档助手 | 创建报告任务 |
| `POST /query` | 数据Agent | 自然语言数据查询 |
| `POST /chat` | 搜索Agent | 自然语言搜索 |
| `GET /read-spreadsheet` | 数据Agent | 读取表格数据 |
| `GET /read-contact` | 数据Agent | 读取通讯录 |
| `GET /read-calendar` | 数据Agent | 读取日历 |

---

## 核心功能验证

### 1. Capability Statement - Agent能力声明

访问"🔐 权限管理"页面，查看各Agent的能力声明：
- doc-assistant: doc:read, doc:write, agent:call:data-agent, agent:call:search-agent
- data-agent: data:read:spreadsheet, data:read:contact, data:read:calendar
- search-agent: web:search

### 2. Delegated Authorization - 委托授权

访问"🔐 权限管理"页面，选择用户和Agent，点击"计算交集"：
- 有效权限 = 用户权限 ∩ Agent能力

### 3. 动态授权

访问"🔐 权限管理"页面：
- 实时授予/撤销Agent权限
- 所有变更记录审计日志

### 4. Token安全机制

- Token实时撤销：撤销后立即失效
- Token安全验证：检测Token异常
- Token重新签发：带新权限集

### 5. 异构Agent接入

访问"⚙️ 系统配置"页面：
- 查看已接入的异构Agent
- 支持配置不同LLM供应商
- 支持配置不同搜索API供应商
- 可添加新的Agent接入

---

## 项目结构

```
AegisLink/
├── docs/
│   ├── TECHNICAL_DESIGN.md    # 技术方案设计
│   ├── architecture.md         # 架构设计
│   ├── demo_guide.md          # 演示指南
│   └── security_analysis.md   # 安全分析
├── src/
│   ├── agents/                # Agent实现
│   │   ├── base_agent.py     # Agent基类
│   │   ├── doc_assistant.py  # 文档助手
│   │   ├── data_agent.py     # 企业数据Agent
│   │   └── search_agent.py   # 外部检索Agent
│   ├── audit/                # 审计与监控
│   │   ├── audit_logger.py   # 审计日志
│   │   └── monitoring.py     # 监控告警
│   ├── common/               # 公共模块
│   │   ├── config.py         # 配置
│   │   ├── data_loader.py    # 数据加载
│   │   └── llm_client.py     # LLM客户端
│   ├── iam/                  # IAM核心
│   │   ├── service.py        # API服务
│   │   ├── token_manager.py  # Token管理
│   │   └── permission_checker.py # 权限校验
│   └── web_console.py       # Web控制台
├── internal_data/            # 企业内部数据
│   ├── spreadsheet_weekly-sales.json
│   ├── contact_company.json
│   └── calendar_events.json
├── static/                   # Web静态文件
│   └── index.html           # 可视化界面
├── scripts/
│   ├── start_all.sh         # 启动脚本
│   └── stop_all.sh          # 停止脚本
├── requirements.txt
└── README.md
```

---

## 常见问题

### Q: 服务启动后无法访问？
```bash
lsof -i :8000 -i :8001 -i :8002 -i :8003 -i :8080
```

### Q: 如何查看完整日志？
```bash
cat logs/*.log
cat audit_logs/audit_logs.jsonl
```

### Q: Web界面显示"无法连接到IAM服务"？
确保IAM服务（端口8000）已启动，并添加了CORS支持。

### Q: 如何测试搜索功能？
确保已安装tavily包并配置了有效的TAVILY_API_KEY。

---

本项目为AegisLink Agent身份与权限系统的完整实现。
