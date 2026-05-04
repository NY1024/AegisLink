from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
import requests
from src.agents.base_agent import BaseAgent
from src.common.config import AGENT_PORTS, IAM_SERVICE_HOST, IAM_SERVICE_PORT, USER_STATIC_CAPABILITIES
from src.common.llm_client import chat
from src.common.data_loader import load_spreadsheet, load_contact, load_calendar

app = FastAPI(title="Data Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data_agent = BaseAgent("data-agent", "data_provider")

DATA_AGENT_SYSTEM = """你是一个企业数据Agent，名叫"小数据"。

你的能力：
- 当用户询问销量、销售、产品数据时，可以调用 data:read:spreadsheet 工具
- 当用户询问同事、联系人、公司人员时，可以调用 data:read:contact 工具
- 当用户询问会议、日程、calendar时，可以调用 data:read:calendar 工具

你可以：
1. 回答用户关于企业数据的一般性问题
2. 当用户请求具体数据时，调用相应工具获取数据并用自然语言解释

如果没有明确的数据请求，就直接回答用户问题，不要调用工具。
"""

TOOL_DESCRIPTIONS = """
可用的数据工具：
- data:read:spreadsheet - 获取周销量数据
- data:read:contact - 获取公司通讯录
- data:read:calendar - 获取日历事件
"""

SYSTEM_PROMPT = """你是一个企业数据Agent，负责根据用户需求查询并解释企业内部数据。

你的能力：
- data:read:spreadsheet - 读取多维表格数据
- data:read:contact - 读取通讯录
- data:read:calendar - 读取日历

数据来源：
- spreadsheet:weekly-sales - 周销量数据
- contact:company - 公司通讯录
- calendar:events - 日历事件

你会收到原始数据，需要：
1. 理解数据含义
2. 分析数据特征
3. 用自然语言描述数据

注意：绝不能返回原始JSON，要返回LLM分析后的自然语言描述。
"""

def verify_call_token(call_token: str, required_action: str):
    verify_response = requests.post(
        f"http://{IAM_SERVICE_HOST}:{IAM_SERVICE_PORT}/auth/verify-call",
        json={"token": call_token}
    )

    if verify_response.status_code != 200:
        return None, "Call token is invalid or expired"

    payload = verify_response.json().get("payload", {})
    token_action = payload.get("action")

    if token_action != required_action:
        return None, f"Token action mismatch: expected {required_action}, got {token_action}"

    return payload, None

def describe_spreadsheet(data: Dict) -> str:
    if not data:
        return "未找到周销量数据"
    prompt = f"""{SYSTEM_PROMPT}

请分析以下周销量数据，用专业的商业语言描述：

数据名称：{data.get('name', '周销量数据')}
更新时间：{data.get('last_updated', '未知')}

表头：{data.get('headers', [])}
数据行：
"""
    for row in data.get('rows', []):
        prompt += f"- {row[0]}: 本周销量{row[1]}，上周销量{row[2]}，变化{row[3]}，负责人{row[4]}，区域{row[5]}\n"

    prompt += f"""
数据汇总：
- 本周总销量：{data.get('summary', {}).get('total_this_week', 0)}
- 上周总销量：{data.get('summary', {}).get('total_last_week', 0)}
- 增长率：{data.get('summary', {}).get('growth_rate', '0%')}

请提供：
1. 整体销售趋势分析
2. 增长最快/下降最多的产品
3. 需要关注的问题产品
4. 简单的商业建议
"""
    return chat(prompt)

def describe_contacts(data: Dict) -> str:
    if not data:
        return "未找到通讯录数据"
    prompt = f"""{SYSTEM_PROMPT}

请分析以下通讯录数据：

数据名称：{data.get('name', '公司通讯录')}
更新时间：{data.get('last_updated', '未知')}
部门总数：{len(set(c.get('department', '') for c in data.get('contacts', [])))}

联系人列表：
"""
    for contact in data.get('contacts', []):
        prompt += f"- {contact['name']} | {contact['department']} | {contact['position']} | {contact['email']} | {contact['phone']}\n"

    prompt += """
请提供：
1. 部门分布情况
2. 关键联系人推荐
"""
    return chat(prompt)

def describe_calendar(data: Dict) -> str:
    if not data:
        return "未找到日历数据"
    prompt = f"""{SYSTEM_PROMPT}

请分析以下日历安排：

数据名称：{data.get('name', '企业日历')}
更新时间：{data.get('last_updated', '未知')}

日程安排：
"""
    for event in data.get('events', []):
        prompt += f"- {event['title']} | 时间：{event['time']} | 时长：{event['duration']} | 地点：{event['location']} | 组织者：{event['organizer']} | 参与人：{','.join(event['participants'])}\n"

    prompt += """
请提供：
1. 本周重要日程概览
2. 时间冲突提醒
"""
    return chat(prompt)

@app.get("/read-spreadsheet")
def read_spreadsheet(token: str, spreadsheet_id: str):
    try:
        payload, error = verify_call_token(token, "data:read:spreadsheet")
        if error:
            raise HTTPException(status_code=403, detail={
                "error": "insufficient_capability",
                "description": error
            })

        raw_data = load_spreadsheet(spreadsheet_id)
        if not raw_data:
            raise HTTPException(status_code=404, detail="Spreadsheet not found")

        description = describe_spreadsheet(raw_data)

        return {
            "status": "success",
            "data": description,
            "raw_data": raw_data,
            "accessed_by": payload.get("agent_id"),
            "delegated_user": payload.get("delegated_user")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/read-contact")
def read_contact(token: str, contact_id: str):
    try:
        payload, error = verify_call_token(token, "data:read:contact")
        if error:
            raise HTTPException(status_code=403, detail={
                "error": "insufficient_capability",
                "description": error
            })

        raw_data = load_contact(contact_id)
        if not raw_data:
            raise HTTPException(status_code=404, detail="Contact not found")

        description = describe_contacts(raw_data)

        return {
            "status": "success",
            "data": description,
            "raw_data": raw_data,
            "accessed_by": payload.get("agent_id")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/read-calendar")
def read_calendar(token: str, calendar_id: str):
    try:
        payload, error = verify_call_token(token, "data:read:calendar")
        if error:
            raise HTTPException(status_code=403, detail={
                "error": "insufficient_capability",
                "description": error
            })

        raw_data = load_calendar(calendar_id)
        if not raw_data:
            raise HTTPException(status_code=404, detail="Calendar not found")

        description = describe_calendar(raw_data)

        return {
            "status": "success",
            "data": description,
            "raw_data": raw_data,
            "accessed_by": payload.get("agent_id")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class QueryRequest(BaseModel):
    query: str
    user_id: Optional[str] = "user:1001"
    history: Optional[list] = []

@app.post("/query")
def query_data(req: QueryRequest):
    try:
        intent_prompt = f"""用户问：{req.query}

判断用户是否在请求具体的企业数据？
- 如果问"有什么功能"、"你是谁"、"介绍一下" -> 不调用工具
- 如果问销量、销售、产品数据 -> 调用 data:read:spreadsheet
- 如果问同事、联系人、某个人 -> 调用 data:read:contact
- 如果问会议、日程安排 -> 调用 data:read:calendar

只回复"不需要"或者"spreadsheet:weekly-sales"或"contact:company"或"calendar:events"。
"""
        intent = chat(intent_prompt).strip().lower()

        tool_result = None
        if "spreadsheet" in intent or "销量" in req.query or "销售" in req.query or "产品" in req.query:
            raw_data = load_spreadsheet("weekly-sales")
            tool_result = describe_spreadsheet(raw_data)
        elif "contact" in intent or "通讯" in req.query or "联系人" in req.query or "同事" in req.query:
            raw_data = load_contact("company")
            tool_result = describe_contacts(raw_data)
        elif "calendar" in intent or "日历" in req.query or "会议" in req.query or "日程" in req.query:
            raw_data = load_calendar("events")
            tool_result = describe_calendar(raw_data)

        if tool_result:
            final_prompt = f"""用户问：{req.query}

根据以下工具返回的数据回答：

{tool_result}

请用自然语言回答用户问题，整合数据给出专业分析。
"""
            answer = chat(final_prompt)
        else:
            answer = chat(req.query, system_prompt=DATA_AGENT_SYSTEM, history=req.history or [])

        return {
            "status": "success",
            "result": answer,
            "query": req.query
        }
    except Exception as e:
        return {"status": "error", "result": str(e)}

@app.get("/status")
def get_status():
    return {
        "agent_id": data_agent.agent_id,
        "role": data_agent.agent_role,
        "registered": data_agent.access_token is not None
    }

@app.get("/capabilities")
def get_capabilities():
    return {"capabilities": data_agent.get_capabilities()}

if __name__ == "__main__":
    import uvicorn
    port = AGENT_PORTS.get("data-agent", 8002)
    uvicorn.run(app, host="0.0.0.0", port=port)
