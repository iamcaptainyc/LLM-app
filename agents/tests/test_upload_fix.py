"""
测试脚本：验证多文档上传和RAG检索功能
"""
import requests
import time
import os

BASE_URL = "http://localhost:8000"

def test_multi_document_upload():
    print("=" * 60)
    print("测试：多文档上传和RAG检索")
    print("=" * 60)
    
    # 1. 创建新会话
    print("\n[1] 创建新会话...")
    response = requests.post(f"{BASE_URL}/sessions")
    session = response.json()
    session_id = session.get("id")
    print(f"    会话ID: {session_id}")
    
    # 2. 创建测试文件A
    print("\n[2] 上传测试文件A...")
    file_a_content = b"This is File A. It contains information about Apple company. Apple was founded in 1976."
    files = {"file": ("test_file_a.txt", file_a_content, "text/plain")}
    data = {"session_id": session_id}
    response = requests.post(f"{BASE_URL}/knowledge/upload", files=files, data=data)
    result = response.json()
    print(f"    上传状态: {result.get('status')}")
    
    # 等待处理完成
    print("    等待处理完成...")
    for _ in range(10):
        time.sleep(1)
        status_resp = requests.get(f"{BASE_URL}/knowledge/upload/status/test_file_a.txt")
        status = status_resp.json().get("status")
        print(f"    处理状态: {status}")
        if status == "completed":
            break
    
    # 3. 检查会话文档列表
    print("\n[3] 检查会话的文档列表...")
    docs_resp = requests.get(f"{BASE_URL}/sessions/{session_id}/documents")
    docs = docs_resp.json().get("documents", [])
    print(f"    已上传文档: {docs}")
    
    # 4. 上传测试文件B
    print("\n[4] 上传测试文件B...")
    file_b_content = b"This is File B. It contains information about Google company. Google was founded in 1998."
    files = {"file": ("test_file_b.txt", file_b_content, "text/plain")}
    data = {"session_id": session_id}
    response = requests.post(f"{BASE_URL}/knowledge/upload", files=files, data=data)
    result = response.json()
    print(f"    上传状态: {result.get('status')}")
    
    # 等待处理完成
    print("    等待处理完成...")
    for _ in range(10):
        time.sleep(1)
        status_resp = requests.get(f"{BASE_URL}/knowledge/upload/status/test_file_b.txt")
        status = status_resp.json().get("status")
        print(f"    处理状态: {status}")
        if status == "completed":
            break
    
    # 5. 再次检查会话文档列表
    print("\n[5] 再次检查会话的文档列表...")
    docs_resp = requests.get(f"{BASE_URL}/sessions/{session_id}/documents")
    docs = docs_resp.json().get("documents", [])
    print(f"    已上传文档: {docs}")
    
    # 验证
    if len(docs) == 2 and "test_file_a.txt" in docs and "test_file_b.txt" in docs:
        print("\n    ✅ 文档列表正确：包含两个文件")
    else:
        print("\n    ❌ 文档列表有问题!")
        return False
    
    # 6. 测试聊天 (询问关于Google的问题)
    print("\n[6] 测试聊天 - 询问关于Google的问题...")
    chat_data = {
        "message": "Tell me about Google",
        "session_id": session_id,
        "use_tools": False,
        "use_rag": True
    }
    response = requests.post(f"{BASE_URL}/chat", data=chat_data)
    chat_result = response.json()
    assistant_response = chat_result.get("response", "")
    print(f"    模型回答: {assistant_response[:200]}...")
    
    # 检查回答是否包含Google相关信息
    if "Google" in assistant_response or "1998" in assistant_response:
        print("\n    ✅ 模型正确识别了文件B的内容 (Google信息)")
    else:
        print("\n    ⚠️ 模型可能没有正确使用文件B的内容")
    
    # 7. 测试清空历史
    print("\n[7] 测试清空历史...")
    response = requests.post(f"{BASE_URL}/agent/clear", data={"session_id": session_id})
    print(f"    结果: {response.json()}")
    
    # 检查文档列表是否被清空
    docs_resp = requests.get(f"{BASE_URL}/sessions/{session_id}/documents")
    docs = docs_resp.json().get("documents", [])
    print(f"    清空后文档列表: {docs}")
    
    if len(docs) == 0:
        print("\n    ✅ 文档列表已清空")
    else:
        print("\n    ⚠️ 文档列表未被清空")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        # 先检查服务是否运行
        health = requests.get(f"{BASE_URL}/health", timeout=3)
        print(f"服务状态: {health.json()}")
        test_multi_document_upload()
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器!")
        print("请先启动后端服务: uvicorn app.main:app --reload --port 8000")
