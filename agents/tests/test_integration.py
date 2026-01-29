# -*- coding: utf-8 -*-
"""
Phase 4 集成与测试脚本
测试多模态智能 Agent 系统的各项功能
"""

import sys
import time
import httpx
from typing import Optional, Dict, Any

# 修复Windows控制台编码
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 测试配置
API_URL = "http://localhost:8000"
TIMEOUT = 60.0

def print_header(title: str):
    """打印测试标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_result(success: bool, message: str):
    """打印测试结果"""
    status = "[PASS]" if success else "[FAIL]"
    print(f"  {status}: {message}")

def test_health_check() -> bool:
    """测试1: 健康检查"""
    print_header("Test 1: Health Check")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.get(f"{API_URL}/health")
            response.raise_for_status()
            data = response.json()
            print(f"  Response: {data}")
            success = data.get("status") == "healthy"
            print_result(success, "Backend health check")
            return success
    except Exception as e:
        print_result(False, f"Connection failed: {e}")
        return False

def test_text_chat() -> bool:
    """测试2: 纯文本对话"""
    print_header("Test 2: Text Chat")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            payload = {
                "messages": [{"role": "user", "content": "Hello, please introduce yourself briefly"}],
                "use_tools": False,
                "use_rag": False
            }
            response = client.post(f"{API_URL}/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            resp_text = data.get('response', '')
            print(f"  User: Hello, please introduce yourself briefly")
            print(f"  Assistant: {resp_text[:200]}...")
            success = bool(resp_text)
            print_result(success, "Text chat response")
            return success
    except Exception as e:
        print_result(False, f"API call failed: {e}")
        return False

def test_tool_calling() -> bool:
    """测试3: 工具调用 (计算器)"""
    print_header("Test 3: Tool Calling (Calculator)")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            payload = {
                "messages": [{"role": "user", "content": "Please calculate 123 * 456"}],
                "use_tools": True,
                "use_rag": False
            }
            response = client.post(f"{API_URL}/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            print(f"  User: Please calculate 123 * 456")
            print(f"  Assistant: {data.get('response', '')}")
            tool_calls = data.get("tool_calls", [])
            print(f"  Tool calls: {len(tool_calls)}")
            for tc in tool_calls:
                result = str(tc.get('tool_output', ''))[:100]
                print(f"    - {tc.get('tool_name')}: {result}")
            success = bool(data.get("response"))
            print_result(success, "Tool calling test")
            return success
    except Exception as e:
        print_result(False, f"API call failed: {e}")
        return False

def test_knowledge_add() -> bool:
    """测试4: 添加知识"""
    print_header("Test 4: Add Knowledge to Vector DB")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # 添加测试知识
            test_knowledge = """
            The Multimodal Agent System is an application based on Qwen 2.5-VL model.
            It supports text and image input with joint reasoning capabilities.
            The system uses LangChain framework for tool calling and dialogue management.
            Backend uses FastAPI for RESTful API services.
            Frontend uses Streamlit for interactive interface.
            """
            response = client.post(
                f"{API_URL}/knowledge/add",
                data={"content": test_knowledge, "source": "test"}
            )
            response.raise_for_status()
            print(f"  Added knowledge: {len(test_knowledge)} characters")
            
            # 获取统计
            stats_response = client.get(f"{API_URL}/knowledge/stats")
            stats = stats_response.json()
            print(f"  Knowledge stats: {stats}")
            
            success = True
            print_result(success, "Knowledge added successfully")
            return success
    except Exception as e:
        print_result(False, f"Add failed: {e}")
        return False

def test_knowledge_search() -> bool:
    """测试5: 知识检索"""
    print_header("Test 5: Knowledge Search")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(
                f"{API_URL}/knowledge/search",
                data={"query": "Qwen model features", "n_results": 3}
            )
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            print(f"  Query: Qwen model features")
            print(f"  Results: {len(results)} items")
            for i, r in enumerate(results):
                doc = r.get('document', '') if isinstance(r, dict) else str(r)
                print(f"    {i+1}. {doc[:80]}...")
            success = len(results) > 0
            print_result(success, "Knowledge search test")
            return success
    except Exception as e:
        print_result(False, f"Search failed: {e}")
        return False

def test_rag_chat() -> bool:
    """测试6: RAG对话"""
    print_header("Test 6: RAG Enhanced Chat")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            payload = {
                "messages": [{"role": "user", "content": "What frameworks does this system use?"}],
                "use_tools": True,
                "use_rag": True
            }
            response = client.post(f"{API_URL}/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            print(f"  User: What frameworks does this system use?")
            print(f"  Assistant: {data.get('response', '')[:300]}...")
            retrieved = data.get("retrieved_docs", [])
            print(f"  Retrieved docs: {len(retrieved)}")
            success = bool(data.get("response"))
            print_result(success, "RAG chat test")
            return success
    except Exception as e:
        print_result(False, f"API call failed: {e}")
        return False

def test_datetime_tool() -> bool:
    """测试7: 日期时间工具"""
    print_header("Test 7: DateTime Tool")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            payload = {
                "messages": [{"role": "user", "content": "What time is it now? What is today's date?"}],
                "use_tools": True,
                "use_rag": False
            }
            response = client.post(f"{API_URL}/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            print(f"  User: What time is it now? What is today's date?")
            print(f"  Assistant: {data.get('response', '')}")
            success = bool(data.get("response"))
            print_result(success, "DateTime tool test")
            return success
    except Exception as e:
        print_result(False, f"API call failed: {e}")
        return False

def test_agent_history() -> bool:
    """测试8: 对话历史"""
    print_header("Test 8: Agent History Management")
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            # 获取历史
            history_response = client.get(f"{API_URL}/agent/history")
            history = history_response.json().get("history", [])
            print(f"  Current history: {len(history)} messages")
            
            # 清空历史
            clear_response = client.post(f"{API_URL}/agent/clear")
            print(f"  Clear history: {clear_response.json()}")
            
            # 再次获取
            history2_response = client.get(f"{API_URL}/agent/history")
            history2 = history2_response.json().get("history", [])
            print(f"  After clear: {len(history2)} messages")
            
            success = len(history2) == 0
            print_result(success, "Agent history management test")
            return success
    except Exception as e:
        print_result(False, f"Operation failed: {e}")
        return False

def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("  Multimodal Agent System - Phase 4 Integration Tests")
    print("=" * 60)
    print(f"\n  API URL: {API_URL}")
    print(f"  Timeout: {TIMEOUT} seconds")
    
    # 等待服务启动
    print("\n  Checking backend service...")
    max_retries = 5
    for i in range(max_retries):
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{API_URL}/health")
                if response.status_code == 200:
                    print("  [OK] Backend service is ready")
                    break
        except:
            if i < max_retries - 1:
                print(f"  [WAIT] Waiting for service... ({i+1}/{max_retries})")
                time.sleep(3)
            else:
                print("  [ERROR] Cannot connect to backend service")
                print("  Please start service first: .\\start.ps1")
                return 1
    
    # 运行测试
    results = {
        "Health Check": test_health_check(),
        "Text Chat": test_text_chat(),
        "Tool Calling": test_tool_calling(),
        "Add Knowledge": test_knowledge_add(),
        "Knowledge Search": test_knowledge_search(),
        "RAG Chat": test_rag_chat(),
        "DateTime Tool": test_datetime_tool(),
        "History Management": test_agent_history(),
    }
    
    # 汇总结果
    print_header("Test Results Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {name}")
    
    print(f"\n  Passed: {passed}/{total}")
    print(f"  Success Rate: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n  All tests passed!")
        return 0
    else:
        print(f"\n  Warning: {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
