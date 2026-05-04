from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from src.agents.base_agent import BaseAgent
from src.common.config import AGENT_PORTS
from src.common.llm_client import chat

app = FastAPI(title="Doc Assistant Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

doc_agent = BaseAgent("doc-assistant", "doc_writer", delegated_user="user:1001")

class TaskRequest(BaseModel):
    task: str
    user_id: Optional[str] = "user:1001"

SYSTEM_PROMPT = """你是一个文档助手Agent，负责协调其他Agent完成用户任务。

你的能力：
- doc:read, doc:write - 读写文档
- agent:call:data-agent - 调用企业数据Agent获取内部数据
- agent:call:search-agent - 调用外部检索Agent获取公开信息

工作流程：
1. 理解用户任务
2. 决定需要调用哪些Agent
3. 执行调用并获取结果
4. 聚合结果生成最终报告

每次调用其他Agent前，必须先调用IAM的/auth/call接口获取授权。
"""

@app.post("/task")
def create_report_task(req: TaskRequest):
    try:
        planning_prompt = f"""{SYSTEM_PROMPT}

用户任务：{req.task}
代表用户：{req.user_id}

分析用户需要什么数据：
- 如果问销量、销售、产品数据 -> data_source: spreadsheet
- 如果问通讯录、联系人、同事 -> data_source: contact
- 如果问日历、会议、日程 -> data_source: calendar

回复JSON格式：
{{"data_source": "spreadsheet/contact/calendar/none", "need_search": true/false}}
"""

        plan = chat(planning_prompt).strip().lower()
        print(f"[LLM Planning] {plan}")

        import re
        data_source_match = re.search(r'"data_source"\s*:\s*"(\w+)"', plan)
        data_source = data_source_match.group(1) if data_source_match else "none"

        data_result = None
        search_result = None

        if data_source == "spreadsheet":
            try:
                call_token = doc_agent.request_call_auth(
                    target_agent_id="data-agent",
                    action="data:read:spreadsheet",
                    resource="weekly-sales"
                )
                data_result = doc_agent.call_agent(
                    target_agent_id="data-agent",
                    action="data:read:spreadsheet",
                    resource="weekly-sales",
                    call_token=call_token
                )
                print(f"[Data Agent] 获取销量数据成功")
            except Exception as e:
                print(f"[Data Agent] 调用失败: {e}")

        elif data_source == "contact":
            try:
                call_token = doc_agent.request_call_auth(
                    target_agent_id="data-agent",
                    action="data:read:contact",
                    resource="company"
                )
                data_result = doc_agent.call_agent(
                    target_agent_id="data-agent",
                    action="data:read:contact",
                    resource="company",
                    call_token=call_token
                )
                print(f"[Data Agent] 获取通讯录成功")
            except Exception as e:
                print(f"[Data Agent] 调用失败: {e}")

        elif data_source == "calendar":
            try:
                call_token = doc_agent.request_call_auth(
                    target_agent_id="data-agent",
                    action="data:read:calendar",
                    resource="events"
                )
                data_result = doc_agent.call_agent(
                    target_agent_id="data-agent",
                    action="data:read:calendar",
                    resource="events",
                    call_token=call_token
                )
                print(f"[Data Agent] 获取日历成功")
            except Exception as e:
                print(f"[Data Agent] 调用失败: {e}")

        if "search" in plan or "true" in plan:
            try:
                search_token = doc_agent.request_call_auth(
                    target_agent_id="search-agent",
                    action="web:search",
                    resource="web:market-trends"
                )
                search_result = doc_agent.call_agent(
                    target_agent_id="search-agent",
                    action="web:search",
                    resource="web:market-trends",
                    call_token=search_token
                )
                print(f"[Search Agent] 获取搜索结果成功")
            except Exception as e:
                print(f"[Search Agent] 调用失败: {e}")

        data_desc = data_result.get('data') if data_result else '无'
        report_prompt = f"""用户任务：{req.task}

基于获取到的数据生成报告：

{data_desc}

请直接基于以上数据生成报告，不要虚构任何数字或内容。如果数据为"无"，请说明无法获取数据。
"""

        final_report = chat(report_prompt)

        return {
            "status": "success",
            "report": final_report,
            "data_source": data_source if data_source != "none" else None,
            "search_source": "search-agent" if search_result else None,
            "delegated_user": req.user_id,
            "llm_plan": plan
        }

    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
def get_status():
    return {
        "agent_id": doc_agent.agent_id,
        "role": doc_agent.agent_role,
        "registered": doc_agent.access_token is not None
    }

@app.get("/capabilities")
def get_capabilities():
    return {"capabilities": doc_agent.get_capabilities()}

if __name__ == "__main__":
    import uvicorn
    port = AGENT_PORTS.get("doc-assistant", 8001)
    uvicorn.run(app, host="0.0.0.0", port=port)
