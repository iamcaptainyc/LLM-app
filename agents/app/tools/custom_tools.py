"""
自定义工具集
为 LangChain Agent 提供可调用的工具
"""

from typing import Optional, List
from langchain_core.tools import tool


@tool
def calculator_tool(expression: str) -> str:
    """
    计算数学表达式。支持基本的数学运算如加减乘除、幂运算等。
    
    Args:
        expression: 要计算的数学表达式，例如 "2 + 3 * 4" 或 "sqrt(16)"
        
    Returns:
        计算结果的字符串表示
    """
    import math
    
    # 安全的数学函数映射
    safe_dict = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
    }
    
    try:
        # 清理表达式
        expression = expression.strip()
        
        # 安全求值
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        
        return f"计算结果: {expression} = {result}"
        
    except Exception as e:
        return f"计算错误: {str(e)}"


@tool
def knowledge_search_tool(query: str) -> str:
    """
    在知识库中搜索相关信息。当用户询问特定领域知识或需要查找资料时使用。
    
    Args:
        query: 搜索查询，描述要查找的信息
        
    Returns:
        搜索到的相关知识内容
    """
    from app.services.vector_service import get_vector_service
    
    try:
        vector_service = get_vector_service()
        results = vector_service.search(query, n_results=3)
        
        if not results:
            return "未在知识库中找到相关信息。"
        
        # 格式化结果
        formatted = "从知识库中找到以下相关信息:\n\n"
        for i, result in enumerate(results, 1):
            content = result["content"][:300]  # 限制长度
            source = result.get("metadata", {}).get("source", "未知来源")
            formatted += f"【{i}】{content}...\n来源: {source}\n\n"
        
        return formatted
        
    except Exception as e:
        return f"知识检索错误: {str(e)}"


# 用于存储当前图片的全局变量
_current_image_base64: Optional[str] = None


def set_current_image(image_base64: Optional[str]):
    """设置当前图片"""
    global _current_image_base64
    _current_image_base64 = image_base64


def get_current_image() -> Optional[str]:
    """获取当前图片"""
    return _current_image_base64


@tool
def image_analyzer_tool(question: str) -> str:
    """
    分析当前上传的图片并回答问题。当用户上传图片并询问相关问题时使用。
    
    Args:
        question: 关于图片的问题，例如 "图片中有什么?" 或 "描述这张图片的内容"
        
    Returns:
        图片分析结果
    """
    from app.services.qwen_service import get_qwen_service
    
    image_base64 = get_current_image()
    
    if not image_base64:
        return "当前没有上传的图片。请先上传一张图片再使用图像分析功能。"
    
    try:
        qwen_service = get_qwen_service()
        result = qwen_service.analyze_image(image_base64, question)
        
        if result["success"]:
            return f"图像分析结果:\n{result['content']}"
        else:
            return f"图像分析失败: {result.get('error', '未知错误')}"
            
    except Exception as e:
        return f"图像分析错误: {str(e)}"


@tool
def get_current_time_tool() -> str:
    """
    获取当前日期和时间。当用户询问现在的时间或日期时使用。
    
    Returns:
        当前的日期和时间
    """
    from datetime import datetime
    
    now = datetime.now()
    return f"当前时间: {now.strftime('%Y年%m月%d日 %H:%M:%S')} (星期{['一','二','三','四','五','六','日'][now.weekday()]})"


@tool  
def weather_tool(city: str) -> str:
    """
    查询城市天气（模拟）。当用户询问天气情况时使用。
    
    Args:
        city: 城市名称，例如 "北京" 或 "上海"
        
    Returns:
        天气信息
    """
    # 模拟天气数据
    import random
    
    weather_conditions = ["晴", "多云", "阴", "小雨", "阵雨"]
    temp = random.randint(-5, 35)
    humidity = random.randint(30, 90)
    condition = random.choice(weather_conditions)
    
    return f"{city}天气:\n天气: {condition}\n温度: {temp}°C\n湿度: {humidity}%\n(注: 这是模拟数据，实际项目中应接入真实天气API)"


def get_all_tools() -> List:
    """获取所有可用工具"""
    return [
        calculator_tool,
        knowledge_search_tool,
        image_analyzer_tool,
        get_current_time_tool,
        weather_tool,
    ]
