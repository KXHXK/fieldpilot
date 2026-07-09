---
title: Kxh Trip Planner Api
sdk: gradio
app_file: app.py
pinned: false
---

# HelloAgents Trip Planner

这是跟随 Datawhale Hello Agents 第十三章“智能旅行助手”逐步实现的教学项目。

当前进度：`13.6 功能实现详解`。本阶段目标不是一次性做完整成品，而是按教程顺序熟悉智能旅行助手的工程结构、数据模型、多 Agent 协作、工具封装、前端页面流转和核心交互功能。

## 环境要求

教程要求：

- Python 3.10 或更高版本
- Node.js 16.0 或更高版本
- npm 8.0 或更高版本

当前本机检查结果：

- Python 3.11.7
- Node.js v24.18.0
- npm 11.16.0

环境满足要求。

## API 密钥准备

你需要准备以下 API 密钥，并统一放入后端 `.env` 文件：

- LLM API：如 OpenAI、DeepSeek、Moonshot Kimi 等
- 高德地图 Web 服务 Key：访问 https://console.amap.com/ 注册并创建应用
- Unsplash Access Key：访问 https://unsplash.com/developers 注册并创建应用

开发阶段为了节省 Kimi 余额，可以保持：

```env
USE_MOCK_LLM=true
USE_MOCK_TOOLS=true
USE_MOCK_IMAGES=true
```

如果需要查看真实数据，切换为：

```env
USE_MOCK_LLM=false
USE_MOCK_TOOLS=false
USE_MOCK_IMAGES=false
```

真实模式会调用：

- Tavily API：实时天气搜索
- 高德地图 API：景点、酒店地点搜索
- Moonshot Kimi API：生成行程总体建议
- Unsplash API：补充景点图片

真实模式会消耗对应 API 的调用额度。

所有密钥只放在后端：

```text
backend/.env
```

前端不保存任何 API 密钥。

## 技术架构

按照第十三章的四层结构：

- 前端层：Vue3 + TypeScript，负责用户交互和数据展示。
- 后端层：FastAPI，负责 API 路由、数据验证和业务编排。
- 智能体层：HelloAgents 思路，多 Agent 协作完成任务分解、工具调用和结果整合。
- 外部服务层：高德地图 API、Unsplash API、LLM API 等。

目标数据流：

```text
用户填写表单
-> 后端验证数据
-> 调用智能体系统
-> 景点搜索 / 天气查询 / 酒店推荐 / 行程规划 Agent 协作
-> Agent 通过 MCP 或服务封装调用外部 API
-> 整合结果
-> 返回前端
-> 前端渲染行程、预算、地图、天气和每日详情
```

## 目录结构

```text
helloagents-trip-planner/
  backend/
    app/
      agents/
      api/
      models/
      services/
      config.py
      main.py
    requirements.txt
  frontend/
    src/
      views/
      services/
      types/
      router/
    package.json
```

## 后端运行方式

```powershell
cd D:\CODEX\个人\helloagents-trip-planner\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `backend/.env`，填入你的 API 密钥。

启动后端：

```powershell
.\.venv\Scripts\uvicorn.exe app.api.main:app --reload
```

或者：

```powershell
.\.venv\Scripts\python.exe run.py
```

成功后访问：

```text
http://localhost:8000/docs
http://localhost:8000/api/health
```

## 前端运行方式

打开新的终端窗口：

```powershell
cd D:\CODEX\个人\helloagents-trip-planner\frontend
npm install
npm run dev
```

成功后访问：

```text
http://localhost:5173
```

## 13.2 数据模型

后端模型位置：

```text
backend/app/models/schemas.py
```

已定义：

- `Location`
- `Attraction`
- `Meal`
- `Hotel`
- `Budget`
- `DayPlan`
- `WeatherInfo`
- `TripPlan`
- `TripPlanRequest`

前端类型位置：

```text
frontend/src/types/trip.ts
```

当前接口：

```text
POST /api/trip/plan
```

## 13.3 多智能体协作

当前 Agent 文件位置：

```text
backend/app/agents/
  weather_agent.py       # 天气查询 Agent
  attraction_agent.py    # 景点搜索 Agent
  hotel_agent.py         # 酒店推荐 Agent
  planner_agent.py       # 行程规划 Agent
  trip_planner.py        # 总编排 Agent
```

当前协作流程：

```text
TripPlannerAgent
-> WeatherQueryAgent
-> AttractionSearchAgent
-> HotelRecommendAgent
-> ItineraryPlanAgent
-> Budget 汇总
-> TripPlan
```

本阶段仍然是 Mock Agent，不调用 Kimi，也不调用真实外部 API。

## 13.4 MCP 工具集成

当前先按教程思想完成工具层封装，但默认不真实调用外部 API：

```text
backend/app/services/
  amap_mcp_service.py   # 高德地图 MCP 共享服务封装
  unsplash_service.py   # Unsplash 图片服务封装
```

当前接入方式：

```text
TripPlannerAgent 创建共享 AmapMCPService
POST /api/trip/plan 生成 TripPlan
-> UnsplashService 为景点补充 image_url
-> 返回前端
```

为了节省 Kimi 余额，本阶段仍然不调用 LLM；为了避免提前消耗外部 API，本阶段也不真实调用高德和 Unsplash。关闭 Mock 后再进入真实 API 验证。

## 13.5 前端开发

当前前端结构：

```text
frontend/src/
  views/
    HomeView.vue       # 首页表单
    ResultView.vue     # 结果页
  services/
    api.ts             # API 请求封装
  types/
    trip.ts            # 旅行计划类型
    index.ts           # 类型统一导出
  router/
    index.ts           # 路由配置
```

当前页面流转：

```text
HomeView 填写旅行需求
-> generateTripPlan 调用 POST /api/trip/plan
-> sessionStorage 暂存 TripPlan
-> 跳转 ResultView
-> 展示概览、预算、地图占位、天气、每日行程和景点图片
```

本节暂时没有引入 Axios、Ant Design Vue、高德 JS API、html2canvas 或 jsPDF，避免现在就安装额外依赖。我们先用原生 `fetch` 和 Vue 页面跑通前后端分离的数据流。

## 13.6 功能实现

当前已实现：

- 预算展示：按景点、住宿、餐饮、交通展示费用，并突出总费用。
- 加载进度条：首页提交时展示模拟进度和当前状态。
- 行程编辑：结果页支持进入编辑模式，对景点执行上移、下移、删除，并可保存或取消。
- 导出功能：当前先实现无依赖版本，支持导出文本和使用浏览器打印为 PDF。
- 侧边导航：结果页支持跳转到概览、预算、地图、天气和每日行程。

教程中的图片/PDF 导出依赖 `html2canvas` 和 `jsPDF`，本阶段暂不引入新包。等基础流程跑通后，再升级为教程版本。

## 下一步

进入最终体验与联调：

1. 安装后端依赖并启动 FastAPI。
2. 安装前端依赖并启动 Vite。
3. 访问 `http://localhost:5173`，填写表单并生成旅行计划。
4. 在结果页验证预算、编辑、导出和侧边导航。
