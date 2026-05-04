import requests
import json
import time
from tabulate import tabulate

IAM_BASE = "http://localhost:8000"
DOC_BASE = "http://localhost:8001"
DATA_BASE = "http://localhost:8002"
SEARCH_BASE = "http://localhost:8003"

def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_step(step, description):
    print(f"\n[Step {step}] {description}")

def demo_normal_flow():
    print_header("场景1: 正常委托流程 - 文档助手委托企业数据Agent")
    
    print_step(1, "用户发起报告生成请求")
    print("发送请求到文档助手Agent，请求生成周报...")
    
    try:
        response = requests.post(
            f"{DOC_BASE}/task",
            json={"task": "生成周报", "user_id": "user:1001"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 请求成功!")
            print(f"  - 状态: {result.get('status')}")
            print(f"  - 数据来源: {result.get('data_source')}")
            print(f"  - 搜索来源: {result.get('search_source')}")
            print(f"  - 委托用户: {result.get('delegated_user')}")
            print(f"\n生成的报告:\n{result.get('report', 'N/A')}")
            return True
        else:
            print(f"✗ 请求失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ 请求异常: {str(e)}")
        return False

def demo_unauthorized_flow():
    print_header("场景2: 越权拦截 - 外部检索Agent尝试访问企业数据")
    
    print_step(1, "外部检索Agent尝试直接调用企业数据Agent")
    print("模拟外部检索Agent尝试越权访问企业数据...")
    
    search_agent_token_response = requests.post(
        f"{IAM_BASE}/token/issue",
        json={"agent_id": "search-agent", "agent_role": "web_searcher"}
    )
    
    if search_agent_token_response.status_code != 200:
        print(f"✗ Token获取失败")
        return False
    
    search_token = search_agent_token_response.json()["access_token"]
    
    print_step(2, "尝试获取调用企业数据Agent的授权")
    call_response = requests.post(
        f"{IAM_BASE}/auth/call",
        params={"token": search_token},
        json={
            "target_agent_id": "data-agent",
            "action": "data:read:spreadsheet",
            "resource": "spreadsheet:weekly-sales"
        }
    )
    
    if call_response.status_code == 403:
        result = call_response.json()
        detail = result.get("detail", {})
        print(f"✓ 请求被拦截!")
        print(f"  - 错误码: {detail.get('error', 'N/A')}")
        print(f"  - 错误描述: {detail.get('error_description', 'N/A')}")
        print(f"  - 原因: 外部检索Agent不具备 'agent:call:data-agent' 权限")
        return True
    else:
        print(f"✗ 拦截失败 - 状态码: {call_response.status_code}")
        return False

def show_audit_logs():
    print_header("审计日志查看")
    
    print_step(1, "获取所有审计日志")
    response = requests.get(f"{IAM_BASE}/audit/logs?limit=50")
    
    if response.status_code == 200:
        logs = response.json()
        print(f"\n共找到 {logs['count']} 条审计记录:\n")
        
        table_data = []
        for log in logs["logs"][:10]:
            table_data.append([
                log.get("requestor_agent_id", "N/A")[:15],
                log.get("target_agent_id", "N/A")[:15],
                log.get("decision", "N/A"),
                log.get("action", "N/A")[:20],
                log.get("reason", "N/A")[:25]
            ])
        
        headers = ["请求方", "目标", "决策", "动作", "原因"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        return True
    else:
        print(f"✗ 获取日志失败: {response.text}")
        return False

def check_system_status():
    print_header("系统状态检查")
    
    services = [
        ("IAM服务", IAM_BASE),
        ("文档助手Agent", DOC_BASE),
        ("企业数据Agent", DATA_BASE),
        ("外部检索Agent", SEARCH_BASE)
    ]
    
    all_healthy = True
    for name, base in services:
        try:
            response = requests.get(f"{base}/health", timeout=2)
            if response.status_code == 200:
                print(f"✓ {name}: 运行正常")
            else:
                print(f"✗ {name}: 异常 (状态码: {response.status_code})")
                all_healthy = False
        except:
            try:
                response = requests.get(f"{base}/status", timeout=2)
                if response.status_code == 200:
                    print(f"✓ {name}: 运行正常")
                else:
                    print(f"✗ {name}: 异常")
                    all_healthy = False
            except Exception as e:
                print(f"✗ {name}: 未运行或无法连接")
                all_healthy = False
    
    return all_healthy

def main():
    print("\n" + "=" * 60)
    print("  AegisLink - Agent身份与权限系统演示")
    print("=" * 60)
    
    print("\n正在检查系统状态...")
    if not check_system_status():
        print("\n⚠ 警告: 部分服务未运行，请先启动所有服务")
        print("启动命令: bash scripts/start_all.sh")
        return
    
    print("\n" + "-" * 60)
    
    scenario = input("选择演示场景:\n1. 正常委托流程\n2. 越权拦截流程\n3. 查看审计日志\n4. 运行全部演示\n请输入选项 (1-4): ").strip()
    
    if scenario == "1":
        demo_normal_flow()
    elif scenario == "2":
        demo_unauthorized_flow()
    elif scenario == "3":
        show_audit_logs()
    elif scenario == "4":
        demo_normal_flow()
        time.sleep(1)
        demo_unauthorized_flow()
        time.sleep(1)
        show_audit_logs()
    else:
        print("无效选项")

if __name__ == "__main__":
    main()
