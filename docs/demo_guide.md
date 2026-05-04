# AegisLink 演示指南

## 快速开始

### 1. 启动所有服务

```bash
cd /Users/elwood/Desktop/test/AegisLink
bash scripts/start_all.sh
```

### 2. 打开Web界面

访问 http://localhost:8080/static/index.html

---

## Web界面功能演示

### 演示1: 系统健康检查

1. 打开"📊 总览"页面
2. 查看所有服务状态
3. 确认所有服务显示为"运行中"

### 演示2: Agent对话

1. 打开"💬 Agent对话"页面
2. 选择"企业数据 (data-agent)"
3. 输入"查看本周销量"
4. 查看返回的数据分析结果

### 演示3: 正常委托流程

1. 打开"⚡ 验收测试"页面
2. 点击"执行正常委托"按钮
3. 查看完整的交互链路

### 演示4: 越权拦截

1. 打开"⚡ 验收测试"页面
2. 点击"执行越权测试"按钮
3. 查看403拦截结果

### 演示5: 权限管理

1. 打开"🔐 权限管理"页面
2. 查看Agent能力声明
3. 计算用户权限∩Agent能力交集
4. 测试动态授权（授予/撤销权限）

### 演示6: Token追溯

1. 打开"🔑 Token管理"页面
2. 选择Agent查看其Token列表
3. 使用Token追溯功能查看使用记录

### 演示7: 审计日志

1. 打开"📋 审计日志"页面
2. 点击"刷新日志"
3. 查看完整的授权决策记录

### 演示8: 异构Agent信息

1. 打开"🔐 权限管理"页面
2. 点击"加载异构Agent信息"
3. 查看不同Agent的模型、引擎、工具集

### 演示9: 系统配置

1. 打开"⚙️ 系统配置"页面
2. 查看当前LLM配置（360 AI）
3. 查看搜索API配置（Tavily）
4. 查看已接入的Agent列表

---

## 命令行演示

### 1. 签发Token

```bash
curl -X POST http://localhost:8000/token/issue \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"doc-assistant","agent_role":"coordinator","delegated_user":"user:1001"}'
```

### 2. 验证Token

```bash
curl -X POST http://localhost:8000/token/verify \
  -H "Content-Type: application/json" \
  -d '{"token":"YOUR_TOKEN_HERE"}'
```

### 3. 查询权限交集

```bash
curl "http://localhost:8000/delegation/intersect?user_id=user:1001&agent_id=doc-assistant"
```

### 4. 查看审计日志

```bash
curl "http://localhost:8000/audit/logs?limit=10"
```

### 5. 创建报告任务

```bash
curl -X POST http://localhost:8001/task \
  -H "Content-Type: application/json" \
  -d '{"task":"查看公司通讯录","user_id":"user:1001"}'
```

### 6. 测试越权拦截

```bash
curl -X POST http://localhost:8003/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"调用企业数据Agent获取内部数据"}'
```

---

## 演示场景

### 场景1: Agent协调报告生成

**用户请求**: "帮我生成一份周报，包含本周销量和行业动态"

**执行流程**:
1. doc-assistant接收任务
2. 通过IAM授权调用data-agent获取销量数据
3. 通过IAM授权调用search-agent获取行业动态
4. 汇聚多源数据生成综合报告

**验证点**:
- 审计日志显示完整的A2A调用链
- Token使用记录正确

### 场景2: 越权拦截

**用户请求**: "search-agent调用data-agent"

**执行流程**:
1. search-agent向IAM申请调用data-agent
2. IAM检查权限列表
3. 发现search-agent没有agent:call:data-agent权限
4. 返回403 Forbidden

**验证点**:
- 返回403错误码
- 审计日志记录deny事件

### 场景3: 动态权限变更

**操作**:
1. 撤销doc-assistant的agent:call:data-agent权限
2. 重新执行报告生成任务
3. 任务失败（因权限不足）

**验证点**:
- 权限变更立即生效
- 后续请求被正确拦截

---

## 数据文件

系统使用以下内部数据：

- `internal_data/spreadsheet_weekly-sales.json` - 周销量数据
- `internal_data/contact_company.json` - 公司通讯录
- `internal_data/calendar_events.json` - 日历事件

---

## 注意事项

1. 所有服务需要在同一台机器上运行
2. 端口8000-8003和8080需要未被占用
3. API Key需要有效（360 AI和Tavily）
4. 浏览器需要支持JavaScript
