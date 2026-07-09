# 智能旅行助手 Agent Demo 开发日志

> 项目版本：1.0.0 冻结版，1.0.1 起作为后续修改分支  
> 项目定位：面向 AI Agent 开发新手的教学型 Demo  
> 参考教程：Datawhale Hello Agents 第十三章“智能旅行助手”

## 1. 项目初衷

这个项目不是一开始就为了做一个完整商业产品，而是为了从 0 到 1 熟悉 AI Agent 项目的完整开发流程。

最初目标很朴素：

- 先跟着 Datawhale Hello Agents 教程跑通一个最小智能体。
- 理解 Thought -> Action -> Observation 的 Agent 循环。
- 再把简单命令行 Agent 逐步扩展成一个可交互的 Web 应用。
- 最后尝试真实部署，让前端、后端、外部 API、Agent 编排真正连起来。

过程中刻意避免一上来使用过重的框架，优先采用“新手能看懂”的技术：

- Python + FastAPI 做后端。
- Vue3 + TypeScript 做前端。
- Pydantic 做数据模型。
- 简单服务封装代替复杂 Agent 框架。
- 真实 API 逐步接入，而不是一开始就堆很多抽象。

## 2. 项目技术栈

### 2.1 前端

前端位于：

```text
frontend/
```

使用技术：

- Vue 3
- TypeScript
- Vite
- Vue Router
- 原生 `fetch`
- 高德 JS API 可选交互地图
- Netlify 静态部署

前端主要负责：

- 首页表单输入旅行需求。
- 调用后端 `/api/trip/plan` 生成旅行计划。
- 展示行程概览、预算、地图、天气、每日行程。
- 支持简单编辑行程，例如景点上移、下移、删除。
- 支持导出文本和浏览器打印 PDF。

### 2.2 后端

后端位于：

```text
backend/
```

使用技术：

- Python 3.11
- FastAPI
- Uvicorn
- Pydantic v2
- pydantic-settings
- requests
- OpenAI Python SDK
- tavily-python

后端主要负责：

- 接收前端旅行规划请求。
- 用 Pydantic 校验请求和响应数据结构。
- 调度多个 Agent。
- 调用外部服务。
- 整合成统一的 `TripPlan` 返回前端。

### 2.3 Agent 层

Agent 代码位于：

```text
backend/app/agents/
```

当前包含：

- `TripPlannerAgent`：总协调器。
- `WeatherQueryAgent`：天气查询 Agent。
- `AttractionSearchAgent`：景点搜索 Agent。
- `HotelRecommendAgent`：酒店推荐 Agent。
- `ItineraryPlanAgent`：每日行程规划 Agent。

这套实现没有直接引入 LangChain、AutoGen 等框架，而是手写了一个更容易理解的多 Agent 协作流程：

```text
用户请求
-> 天气 Agent
-> 景点 Agent
-> 酒店 Agent
-> 行程规划 Agent
-> LLM 总体建议
-> TripPlan
```

这么做的好处是：新手可以先理解 Agent 项目的本质，再考虑引入框架。

### 2.4 外部 API

项目接入过这些外部服务：

- Kimi / Moonshot API：生成总体旅行建议。
- Tavily API：用搜索方式获取天气相关信息。
- 高德 Web 服务 API：景点、酒店、坐标、POI 图片、静态地图。
- Unsplash API：景点图片兜底。
- 高德 JS API：可选前端交互地图。

### 2.5 部署

最终探索过多种部署方式：

- Netlify：前端静态站点。
- Vercel：后端 FastAPI Serverless 部署。
- Render：尝试后发现要求 Payment Information。
- Hugging Face Spaces：尝试 Gradio / Docker，但硬件和网络限制较多。
- 腾讯云：后续考虑用于国内更稳定的后端部署。

## 3. 目录结构

当前核心结构如下：

```text
helloagents-trip-planner/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   ├── api/
│   │   ├── models/
│   │   ├── services/
│   │   ├── config.py
│   │   └── main.py
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── router/
│   │   ├── services/
│   │   ├── types/
│   │   └── views/
│   └── package.json
├── api/
│   └── index.py
├── app.py
├── Dockerfile
├── netlify.toml
├── vercel.json
├── render.yaml
└── requirements.txt
```

几个容易混淆的入口：

- `backend/app/main.py`：真正的 FastAPI app。
- `backend/app/api/main.py`：供 `uvicorn app.api.main:app` 使用的兼容入口。
- `api/index.py`：Vercel Python serverless 入口。
- `app.py`：Hugging Face Gradio Space 入口。
- `Dockerfile`：容器部署入口。

## 4. 开发历程

### 4.1 第一步：从最小 Agent 开始

一开始先做 Datawhale 教程里的 1.3 “5 分钟实现第一个智能体”。

这个阶段的重点不是 Web，也不是工程结构，而是理解：

- Agent 不只是一次性问 LLM。
- Agent 会根据任务决定下一步。
- Agent 需要工具。
- Agent 会把工具返回的 Observation 作为下一轮输入。

最小旅行助手大致是：

```text
用户：查询北京天气，并根据天气推荐景点

第 1 轮：
Thought: 需要先查天气
Action: get_weather(city="北京")

Observation: 北京天气晴朗

第 2 轮：
Thought: 根据天气推荐景点
Action: get_attraction(city="北京", weather="晴朗")

Observation: 推荐颐和园、长城

第 3 轮：
Thought: 信息足够，给最终答案
Action: Finish[...]
```

这一阶段踩过的坑：

- Python 虚拟环境里没有安装 `openai`。
- `.env` 文件没配置，导致 `KeyError: OPENAI_API_KEY` 或 `MOONSHOT_API_KEY`。
- 环境变量名不统一，代码里读 `OPENAI_API_KEY`，但实际只有 `MOONSHOT_API_KEY`。

后来统一思路：

- API Key 不硬编码。
- 统一放到 `.env`。
- 用 `os.environ.get()` 或 pydantic-settings 管理配置。

### 4.2 第二步：拆分学习线

项目早期有两条线：

- 线 A：个人任务助手 Demo。
- 线 B：Datawhale 教程 Agent Demo。

后来明确先做线 B，再做线 A。

为了避免混乱，把不同方向拆成不同文件夹，并把中断的项目先放到 `wasted` 里。

这个阶段最大的收获是：新手做 Agent 项目时，最容易因为“想做的太多”而乱。拆分目录和冻结阶段目标很重要。

### 4.3 第三步：进入第十三章智能旅行助手

根据 Datawhale 第十三章，项目架构设计为：

```text
前端层 Vue3 + TypeScript
-> 后端层 FastAPI
-> 智能体层 HelloAgents 风格多 Agent
-> 外部服务层 高德 / Unsplash / LLM / Tavily
```

数据流：

```text
用户填写表单
-> 前端提交请求
-> FastAPI 校验请求
-> TripPlannerAgent 协调多个 Agent
-> 各 Agent 调用工具服务
-> 生成 TripPlan
-> 前端展示
```

这个阶段重点实现：

- Pydantic 数据模型。
- 多 Agent 协作。
- MCP 思路下的服务封装。
- 前后端分离。
- 行程展示、预算、地图、天气、编辑、导出。

### 4.4 第四步：数据模型设计

核心模型位于：

```text
backend/app/models/schemas.py
frontend/src/types/trip.ts
```

后端 Pydantic 模型包括：

- `Location`
- `Attraction`
- `Meal`
- `Hotel`
- `Budget`
- `DayPlan`
- `WeatherInfo`
- `TripPlan`
- `TripPlanRequest`

前端 TypeScript 类型和后端模型保持一致。

这个阶段的经验：

- Web 应用里，数据结构比界面更早确定。
- 前端和后端如果字段名不一致，很容易出现页面渲染为空。
- Pydantic 的 `Field` 和校验器可以让数据更可靠。
- 天气温度经常带 `℃`、`°C`、中文“度”，需要做解析清洗。

### 4.5 第五步：多 Agent 协作设计

一开始没有直接做“全自动超级 Agent”，而是拆成多个角色：

- 天气 Agent 只管天气。
- 景点 Agent 只管景点。
- 酒店 Agent 只管住宿。
- 行程 Agent 只管把已有信息排成每日计划。
- 总协调器负责串流程。

这样做的好处：

- 每个 Agent 职责清楚。
- 出问题时容易定位。
- 新手更容易理解工程结构。

踩过的坑：

- 每天文案太重复。
- 后几天都变成“轻松收尾与弹性安排”。
- 交通建议、住宿建议也高度重复。
- 景点重复出现在不同日期。

后来改进：

- 先对景点按名称去重。
- 每天分配不同景点。
- 文案模板按天数轮换。
- 交通建议根据交通偏好、天气、天数变化。
- 住宿建议区分抵达日、中间日、返程日。

### 4.6 第六步：工具服务封装

服务代码位于：

```text
backend/app/services/
```

包括：

- `llm_service.py`
- `tavily_weather_service.py`
- `amap_mcp_service.py`
- `unsplash_service.py`

这里借鉴了 MCP 的思想：不要在 Agent 里到处直接写 API 请求，而是把外部能力封装成服务。

例如高德服务负责：

- 搜索景点。
- 搜索酒店。
- 解析经纬度。
- 获取 POI 图片。
- 生成静态地图。

踩过的坑：

- 高德关键词最初乱码，导致历史文化偏好搜不到合适景点。
- 高德静态地图多 marker 有时返回错误，后来先降级为单 marker 可用版本。
- 景点图片和名称不匹配，后来改成优先使用高德 POI 自带照片，Unsplash 只做兜底。
- Tavily 偶尔 SSL EOF 或网络异常，不能直接让整个请求 500。

改进：

- Tavily 查询加 try/except 和 fallback。
- 天气查询失败时返回可读的占位天气。
- 高德 POI 图片优先。
- Unsplash 根据景点类别选择更贴近的图片关键词。

### 4.7 第七步：前端页面开发

前端页面主要包括：

- `HomeView.vue`
- `ResultView.vue`
- `TripMap.vue`

首页负责收集：

- 目的地城市。
- 开始日期。
- 结束日期。
- 预算。
- 交通类型。
- 住宿类型。
- 旅行偏好。

结果页负责展示：

- 行程概览。
- 预算明细。
- 景点地图。
- 天气信息。
- 每日行程。
- 景点图片。
- 编辑按钮。
- 导出文本 / 打印 PDF。

踩过的坑：

- 部分源码中文变成乱码。
- 前端页面显示乱码。
- 地图区域一开始只是占位文案。
- Netlify 前端请求 `/api`，部署后找不到后端。

改进：

- 重写乱码文件。
- 增加 `VITE_API_BASE_URL` 支持线上后端地址。
- 增加 `TripMap.vue`，支持高德 JS 交互地图。
- 没有前端高德 JS Key 时，自动回退后端静态地图。

### 4.8 第八步：真实 API 接入

一开始为了节省 Kimi 余额，先使用 Mock LLM：

```env
USE_MOCK_LLM=true
USE_MOCK_TOOLS=true
USE_MOCK_IMAGES=true
```

后来用户明确要求：

- 可以接入所有 API。
- 不用 mock。
- 天气用 Tavily，不用高德。

真实模式：

```env
USE_MOCK_LLM=false
USE_MOCK_TOOLS=false
USE_MOCK_IMAGES=false
```

真实 API 接入后发现：

- API 不稳定是常态。
- 外部搜索结果可能是英文。
- 图片可能不匹配。
- Vercel / Netlify / 本地网络对不同域名可达性不同。

所以真实项目必须有：

- 错误兜底。
- 超时设置。
- 友好的失败信息。
- 尽量不让一个工具失败拖垮整个 Agent。

## 5. 部署历程

### 5.1 GitHub

项目上传到：

```text
https://github.com/KXHXK/helloagents-trip-planner
```

过程中做了：

- 初始化 Git 仓库。
- 设置远程 `origin`。
- 提交项目源码。
- 忽略 `.env`、`.venv`、`node_modules`、`dist`、日志、参考项目。
- 后来打了本地 `v1.0.0` 标签。
- 新建 `v1.0.1-dev` 分支作为后续开发线。

踩过的坑：

- Git 没配置用户名和邮箱，无法 commit。
- GitHub push 经常因为网络失败。
- Windows 下 Git 出现 `dubious ownership`，需要添加 safe.directory。

### 5.2 Netlify 前端部署

前端部署到：

```text
https://kxh-trip-planner.netlify.app/
```

一开始出现：

```text
Page not found
```

原因：

- 仓库根目录不是前端项目。
- 前端在 `frontend/`。
- Netlify 默认从根目录找页面，自然找不到 `index.html`。

解决：

新增：

```text
netlify.toml
```

内容：

```toml
[build]
  base = "frontend"
  command = "npm run build"
  publish = "dist"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

另一个坑：

- Vue Router 使用 history 模式。
- 如果没有 fallback 到 `index.html`，刷新 `/result` 会 404。

### 5.3 Render 后端部署尝试

曾尝试 Render 部署 FastAPI。

新增过：

```text
render.yaml
```

但 Render 要求 Payment Information，需要绑卡，用户不想填卡，所以放弃。

### 5.4 Hugging Face Spaces 尝试

尝试过 Hugging Face Spaces：

- Docker Space：需要 billing。
- Gradio Space：可以运行 Python，但部署 FastAPI 比较绕。
- CPU basic 后来也提示需要 PRO。

期间做过：

- `app.py` 作为 Hugging Face Gradio 入口。
- `requirements.txt` 作为根目录依赖。
- `hf-space-backend-upload` 手动上传包。

踩过的坑：

- Git push Hugging Face 连不上。
- READ token 不能 push，需要 Write token。
- Space 报 `No @spaces.GPU function detected during startup`。
- CPU basic 也受账号/订阅限制。

结论：

- Hugging Face 更适合模型 Demo，不太适合这个 FastAPI 后端新手部署场景。

### 5.5 Vercel 后端部署

后来改用 Vercel 部署后端。

新增：

```text
api/index.py
vercel.json
requirements.txt
```

`api/index.py` 负责把后端 FastAPI app 暴露给 Vercel：

```python
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.api.main import app
```

`vercel.json` 让 Vercel 把所有请求转发到 Python Serverless 函数。

踩过的坑：

- Vercel 不支持根目录 `requirements.txt` 里写 `-r backend/requirements.txt`。
- 报错：

```text
Failed to parse "requirements.txt"
Error parsing included file
```

解决：

- 把根目录 `requirements.txt` 改成直接列出依赖。

部署成功后，后端地址类似：

```text
https://helloagents-trip-planner-ochre.vercel.app
```

健康检查：

```text
https://helloagents-trip-planner-ochre.vercel.app/api/health
```

返回：

```json
{"status":"ok"}
```

### 5.6 CORS 问题

Netlify 前端调用 Vercel 后端时出现：

```text
Access to fetch at ... has been blocked by CORS policy
No 'Access-Control-Allow-Origin' header is present
```

现象：

- 直接打开 `/api/health` 能返回 `{"status":"ok"}`。
- 前端按钮请求失败。
- Network 里显示 `net::ERR_FAILED 200 (OK)`。

原因：

- 后端确实返回了 200。
- 但没有带浏览器需要的 CORS 响应头。
- 浏览器因此拦截响应。

解决：

在 `backend/app/main.py` 中加固 CORS：

```python
allowed_origins = sorted(
    {
        *settings.cors_origins,
        "https://kxh-trip-planner.netlify.app",
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.netlify\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

并用 FastAPI TestClient 本地验证：

```text
status_code = 200
access-control-allow-origin = https://kxh-trip-planner.netlify.app
```

### 5.7 国内访问问题

后来发现：

- 开 VPN 可以访问 Vercel 后端。
- 不开 VPN 时后端连接超时。

典型错误：

```text
Failed to load resource: net::ERR_CONNECTION_TIMED_OUT
```

判断：

- 这不是 Kimi、Tavily、高德、Unsplash 哪个工具调用需要 VPN。
- 而是本地浏览器访问 Vercel 后端域名本身超时。

也就是说：

```text
浏览器 -> Vercel 后端
```

这一段在国内网络不稳定。

后续考虑：

- 腾讯云。
- 阿里云。
- 国内轻量服务器。
- 容器部署 + 域名 + HTTPS。

## 6. 当前 1.0.0 状态

1.0.0 版本已经冻结在：

```text
D:\CODEX\个人\helloagents-trip-planner
```

本地标签：

```text
v1.0.0
```

1.0.1 开发副本：

```text
D:\CODEX\个人\helloagents-trip-planner-1.0.1
```

分支：

```text
v1.0.1-dev
```

原则：

- 不再直接改 1.0.0 原目录。
- 后续改动都在 1.0.1 副本里做。
- 稳定后再决定是否合并、打标签或重新部署。

## 7. 重要经验总结

### 7.1 Agent 开发经验

1. 先做最小闭环，不要一开始追求复杂框架。
2. Agent 的关键不是“调用 LLM”，而是“任务分解 + 工具调用 + 观察结果再利用”。
3. 多 Agent 不一定要复杂，每个 Agent 有清晰职责就已经很有价值。
4. 工具调用一定要有失败兜底。
5. 外部 API 返回的数据不可控，必须清洗、去重、兜底。
6. Mock 模式非常重要，可以省钱，也能稳定调试流程。
7. 真实 API 模式一定要准备好超时、异常和错误提示。

### 7.2 前后端开发经验

1. 前后端分离项目必须先设计数据模型。
2. 后端 Pydantic 和前端 TypeScript 类型最好保持同步。
3. `VITE_*` 环境变量是在构建时写入前端代码，不是运行时读取。
4. Netlify 加完环境变量后必须重新部署。
5. Vue history 路由部署到静态站点时必须配置 fallback。
6. 浏览器报 `200 OK` 但请求失败时，优先看 CORS。

### 7.3 部署经验

1. Netlify 适合部署前端，不适合直接跑 FastAPI。
2. Vercel 可以跑 Python Serverless，但不等同于长期运行的服务器。
3. Render、Koyeb 等平台可能要求绑卡。
4. Hugging Face Spaces 对普通后端部署不是最自然。
5. 国内访问 Vercel / Hugging Face 可能不稳定。
6. 如果面向国内用户，后端最好考虑国内云服务。
7. HTTPS 很重要，前端是 HTTPS 时，后端也必须是 HTTPS。

### 7.4 Git 和版本管理经验

1. `.env` 永远不要提交。
2. `node_modules`、`.venv`、`dist` 不要提交。
3. 阶段性成果要打 tag。
4. 大改前创建新分支或新 worktree。
5. 冻结版和开发版分开，能避免“修着修着把稳定版本弄坏”。
6. 网络不稳定时，先确保本地 commit 完成；push 可以稍后再做。

## 8. 后续 1.0.1 可以做什么

1. 把后端迁到腾讯云，解决国内访问 Vercel 超时问题。
2. 统一整理 README，修复历史乱码内容。
3. 增加后端请求日志和错误日志。
4. 给 `/api/trip/plan` 增加更友好的错误响应。
5. 增加 API 缓存，减少 Kimi、Tavily、高德调用次数。
6. 优化预算算法，让预算拆分更符合真实旅行场景。
7. 支持导出 PDF 文件，而不是只依赖浏览器打印。
8. 增加历史行程保存功能。
9. 增加用户可选择“省钱 / 舒适 / 深度游 / 亲子游”等模式。
10. 继续学习 Datawhale 后续章节，把这个项目逐步升级成更完整的 Agent 应用。

## 9. 给未来自己的提醒

这个项目最有价值的地方，不是某一段代码，而是完整经历了一遍：

```text
概念学习
-> 最小 Agent
-> 数据模型
-> 多 Agent 协作
-> 工具封装
-> 前后端联调
-> 真实 API 接入
-> 线上部署
-> CORS / 网络 / 平台限制排错
-> 版本冻结
```

以后再做 Agent 项目时，不要急着一上来堆框架。先问自己：

- 用户输入是什么？
- 最终输出是什么？
- 中间需要哪些工具？
- 每一步失败了怎么办？
- 哪些数据结构必须稳定？
- 哪些地方需要 Mock？
- 哪些 API 会花钱？
- 部署环境是否能访问这些 API？

把这些问题想清楚，Agent 项目就不会乱。

