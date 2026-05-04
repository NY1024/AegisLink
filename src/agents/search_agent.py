from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import requests
from tavily import TavilyClient
from src.agents.base_agent import BaseAgent
from src.common.config import AGENT_PORTS, IAM_SERVICE_HOST, IAM_SERVICE_PORT
from src.common.llm_client import chat

app = FastAPI(title="Search Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

search_agent = BaseAgent("search-agent", "web_searcher")

IAM_URL = f"http://{IAM_SERVICE_HOST}:{IAM_SERVICE_PORT}"

TAVILY_API_KEY = "***"
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

SEARCH_AGENT_SYSTEM = """你是一个外部检索Agent，名叫"小搜"。

你的能力：
- web:search - 搜索外部公开网页信息（使用Tavily搜索引擎）
- agent:call:data-agent - 调用企业数据Agent获取内部数据（需要通过IAM授权）

你可以：
1. 搜索互联网公开信息（使用Tavily API实时搜索）
2. 通过IAM授权调用企业数据Agent

当用户请求获取企业内部数据时，应该尝试通过IAM授权调用data-agent。"""

def get_agent_token(agent_id: str, agent_role: str):
    resp = requests.post(f"{IAM_URL}/token/issue", json={
        "agent_id": agent_id,
        "agent_role": agent_role
    })
    if resp.status_code == 200:
        return resp.json().get("access_token")
    return None

def authorize_call(token: str, target_agent: str, action: str):
    resp = requests.post(f"{IAM_URL}/auth/call?token={token}", json={
        "target_agent_id": target_agent,
        "action": action,
        "resource": "internal:data"
    })
    return resp

def call_data_agent(call_token: str, resource: str):
    resp = requests.get(f"http://localhost:8002/read-spreadsheet", params={
        "token": call_token,
        "spreadsheet_id": resource
    })
    return resp

def do_web_search(query: str) -> List[dict]:
    try:
        response = tavily_client.search(
            query=query,
            search_depth="advanced"
        )
        results = []
        for item in response.get("results", [])[:5]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", "")[:200]
            })
        return results
    except Exception as e:
        print(f"[ERROR] Tavily search failed: {e}")
        return []

SYSTEM_PROMPT = """你是一个外部检索Agent，负责根据用户查询搜索公开信息，并用专业语言总结结果。

你的能力：
- web:search - 使用Tavily搜索引擎搜索外部公开网页信息

你会收到原始搜索结果，需要：
1. 理解用户查询意图
2. 分析搜索结果
3. 用简洁专业的语言总结关键信息

注意：不要罗列原始结果，要提炼核心观点和结论。
"""

def verify_token_and_check_permission(token: str, required_action: str):
    verify_response = requests.post(
        f"http://{IAM_SERVICE_HOST}:{IAM_SERVICE_PORT}/token/verify",
        json={"token": token}
    )

    if verify_response.status_code != 200:
        return None, "Invalid or expired token"

    payload = verify_response.json()["payload"]
    capabilities = payload.get("capabilities", [])

    if required_action not in capabilities:
        return None, "Missing required capability"

    return payload, None

def summarize_results(query: str, results: List[dict]) -> str:
    if not results:
        return "未找到相关搜索结果"

    prompt = f"""{SYSTEM_PROMPT}

用户查询：{query}

搜索结果：
"""
    for i, r in enumerate(results, 1):
        prompt += f"{i}. {r['title']}\n   摘要：{r['snippet']}\n   来源：{r['url']}\n"

    prompt += """
请总结：
1. 与用户查询最相关的核心信息
2. 关键趋势或发现
3. 信息来源的可靠性评估
"""
    return chat(prompt)

class SearchRequest(BaseModel):
    query: str

@app.get("/search")
def web_search(token: str, query: str):
    payload, error = verify_token_and_check_permission(token, "web:search")
    if error:
        raise HTTPException(status_code=403, detail={
            "error": "insufficient_capability",
            "description": error
        })

    results = do_web_search(query)
    summary = summarize_results(query, results)

    return {
        "status": "success",
        "query": query,
        "summary": summary,
        "results": results,
        "agent": search_agent.agent_id,
        "accessed_by": payload.get("agent_id")
    }

@app.post("/search")
def search(req: SearchRequest, token: str):
    payload, error = verify_token_and_check_permission(token, "web:search")
    if error:
        raise HTTPException(status_code=403, detail={
            "error": "insufficient_capability",
            "description": error
        })

    results = do_web_search(req.query)
    summary = summarize_results(req.query, results)

    return {
        "status": "success",
        "query": req.query,
        "summary": summary,
        "results": results,
        "agent": search_agent.agent_id,
        "accessed_by": payload.get("agent_id")
    }

class ChatRequest(BaseModel):
    query: str
    history: Optional[list] = []

@app.post("/chat")
def chat_search(req: ChatRequest):
    query_lower = req.query.lower()

    need_data_agent = any(kw in query_lower for kw in ["企业数据", "内部数据", "销量", "通讯录", "联系人", "日历", "会议", "表格"])

    if need_data_agent:
        token = get_agent_token("search-agent", "web_searcher")
        if not token:
            return {
                "status": "error",
                "result": "无法获取Agent Token，请检查IAM服务是否运行"
            }

        auth_resp = authorize_call(token, "data-agent", "data:read:spreadsheet")

        if auth_resp.status_code == 403:
            auth_data = auth_resp.json()
            return {
                "status": "error",
                "result": f"❌ 越权拦截！search-agent没有权限调用data-agent。\n错误: {auth_data.get('detail', {}).get('error_description', '权限不足')}\n\n这是预期的安全行为，证明IAM的A2A授权机制正常工作！"
            }

        if auth_resp.status_code == 200:
            call_token = auth_resp.json().get("call_token")
            data_resp = call_data_agent(call_token, "weekly-sales")
            if data_resp.status_code == 200:
                data = data_resp.json()
                return {
                    "status": "success",
                    "result": f"✅ 通过IAM授权成功调用企业数据Agent！\n\n数据来源: {data.get('accessed_by')}\n\n{data.get('data', '数据获取成功')}",
                    "query": req.query,
                    "source": "data_agent_via_iam"
                }
            else:
                return {
                    "status": "error",
                    "result": f"调用data-agent成功，但获取数据失败: {data_resp.text}"
                }

    results = do_web_search(req.query)
    summary = summarize_results(req.query, results)
    return {
        "status": "success",
        "result": summary,
        "query": req.query,
        "source": "web_search"
    }

@app.get("/status")
def get_status():
    return {
        "agent_id": search_agent.agent_id,
        "role": search_agent.agent_role,
        "registered": search_agent.access_token is not None
    }

@app.get("/capabilities")
def get_capabilities():
    return {"capabilities": search_agent.get_capabilities()}

if __name__ == "__main__":
    import uvicorn
    port = AGENT_PORTS.get("search-agent", 8003)
    uvicorn.run(app, host="0.0.0.0", port=port)
