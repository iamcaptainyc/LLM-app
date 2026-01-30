# 多模态智能 Agent 系统

基于 **Qwen 2.5-VL** 多模态大模型的智能问答与对话系统，采用前后端分离架构，支持文本+图像+文档输入，具备图文联合推理与知识检索增强（RAG）能力。

## ✨ 核心特性

- 🖼️ **多模态理解**: 支持图片上传，能够基于 Qwen VL 模型进行深入的图像分析和图文联合推理
- 📄 **文档知识库 (RAG)**: 支持上传 PDF/TXT/MD 文件，自动分块向量化，提供精确的基于文档的问答
- 🔧 **工具调用**: 集成计算器、天气查询、知识检索等工具，Agent 可自主决定是否调用
- 💬 **智能历史管理**: 
  - **侧边栏 (Frontend)**: 基于 Chainlit 的本地极速历史记录，支持会话增删改名
  - **记忆同步 (Backend)**: 前后端通过 ID 自动同步，保证对话上下文在服务端持久化
- 🚀 **现代架构**: FastAPI 高性能后端 + Chainlit 交互式前端

---

## 🏗️ 系统架构

```mermaid
graph TD
    User[用户] --> Chainlit[Chainlit 前端 (UI)]
    
    subgraph Frontend [Chainlit App]
        Chainlit --> LocalData[本地历史 (.json)]
        Chainlit --> APIClient[API 客户端]
    end
    
    APIClient -- HTTP/WebSocket --> FastAPI[FastAPI 后端]
    
    subgraph Backend [Backend Service]
        FastAPI --> Agent[LangGraph ReAct Agent]
        Agent --> Tools[工具集 (计算器/搜索)]
        Agent --> RAG[RAG 服务]
        Agent --> Qwen[Qwen 2.5-VL 模型]
        
        RAG --> Chroma[Chroma 向量数据库]
        Agent --> Sessions[会话记忆 (.json)]
    end
```

---

## 🚀 快速开始

### 1. 环境准备

推荐使用 Conda 创建环境：

```bash
conda create -n multimodal-agent python=3.11 -y
conda activate multimodal-agent
```

安装依赖：

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

复制配置模板：

```bash
# Windows
copy .env.example .env
```

编辑 `.env` 文件，填入您的 DashScope API Key：

```env
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> 💡 获取 Key: [阿里云百炼平台](https://dashscope.console.aliyun.com/)

### 3. 启动服务 

您可以分别启动前后端，或者使用脚本。

**方式 A: 分别启动 (开发调试)**

*终端 1 (后端):*
```bash
uvicorn app.main:app --reload --port 8000
```

*终端 2 (前端):*
```bash
chainlit run chainlit_app/cl_app.py -w --port 8501
```

**方式 B: 脚本启动 (Windows)**

```powershell
.\start_chainlit.bat
```

### 4. 访问应用

打开浏览器访问: **http://localhost:8501**

---

## 📖 功能指南

### <1> 侧边栏模式
系统左侧提供完整的 **历史对话记录**。
- **新建对话**: 点击 "+" 号开始新话题。
- **切换对话**: 点击历史记录可无缝切换，上下文自动恢复。
- **管理**: 支持重命名和删除会话（删除操作会同步清除后端的记忆）。

### <2> 知识库 (RAG)
1. 点击输入框左侧的 `+` 号，上传 **PDF** 或 **TXT** 文件。
2. 系统会自动处理文件并存入向量库。
3. **提问示例**: "根据上传的文档，总结主要观点。"

### <3> 图像分析
1. 上传一张图片。
2. **提问示例**: "分析这张图片的内容" 或 "提取图片中的表格数据"。
3. Agent 会自动识别意图并调用视觉模型。

### <4> 全局设置
点击右上角的设置图标，可以切换：
- **🔧 启用工具**: 是否允许 Agent 使用计算器等外部工具。
- **📚 启用 RAG**: 是否允许 Agent 检索知识库。

---

## 📁 项目结构

```
agents/
├── app/                          # 后端核心服务 (FastAPI)
│   ├── main.py                   # API 入口
│   ├── services/                 # 业务逻辑
│   │   ├── agent_service.py      # LangGraph Agent 核心
│   │   ├── vector_service.py     # RAG 向量检索
│   │   └── ...
│   └── tools/                    # Agent 工具集
├── chainlit_app/                 # 前端应用 (Chainlit)
│   ├── cl_app.py                 # 前端入口
│   ├── custom_data_layer.py      # 本地数据持久化层
│   └── api_client.py             # 后端通信客户端
├── data/                         # 数据存储
│   ├── chainlit_storage/         # 前端历史记录 (threads.json)
│   ├── sessions/                 # 后端会话记忆
│   └── chroma/                   # 向量数据库文件
├── requirements.txt              # 项目依赖
└── README.md                     # 说明文档
```

---

## ⚠️ 注意事项

* **文件锁**: 在 Windows 上，如果遇到删除会话失败，通常是因为文件被占用，系统会自动处理大部分情况，但建议不要在后台手动打开数据文件。
* **首次运行**: 首次启动时会下载必要的模型组件（如果配置了本地模型），请保持网络通畅。
* **API 费用**: 使用 Qwen-VL 模型会产生少量 API 调用费用，请关注阿里云控制台。

---

## 📄 许可证

MIT License
