# 1.0.1：部署后端到腾讯云 CloudBase 云托管

本文将 FastAPI 后端从 Vercel 迁移到腾讯云 CloudBase 云托管。目标是让中国大陆用户访问 Netlify 前端时，可以直接连到国内后端，不再依赖 VPN；前端仍保留在 Netlify。

## 开始前

- 前端地址保持为：`https://kxh-trip-planner.netlify.app`。
- 本次只将后端容器部署到腾讯云。
- 不要提交 `backend/.env`，也不要在 GitHub、文档或截图中暴露 API 密钥。
- 仓库根目录已经有可用的 `Dockerfile`，不要把构建目录选成 `backend/`，否则云托管找不到 Dockerfile。

## 第 1 步：创建云托管服务

1. 登录腾讯云控制台，打开“云开发 CloudBase”中的“云托管”。
2. 创建环境，区域可优先选择上海或广州。
3. 新建服务，服务名填写 `kxh-trip-planner-api`。
4. 选择“从代码仓库部署”，关联 GitHub 仓库 `KXHXK/helloagents-trip-planner`。
5. 推送完成后选择 `v1.0.1-dev` 分支。如果该分支尚未推送，则先不要部署 `main`，避免把 1.0.0 的旧版本部署上去。
6. 构建目录选择仓库根目录，Dockerfile 名称保持 `Dockerfile`。
7. 监听端口填 `7860`，开启公网访问，并将 100% 流量发布到新版本。

项目的 Dockerfile 会读取云平台传入的 `PORT`。控制台填写 `7860` 方便检查，平台提供其他端口时也能正常启动。

## 第 2 步：配置环境变量

在服务版本的“环境变量”面板中逐条添加以下变量。普通 API Key 不要加引号，值替换为你自己的真实密钥。

```text
APP_VERSION=1.0.1
USE_MOCK_LLM=false
USE_MOCK_TOOLS=false
USE_MOCK_IMAGES=false
OPENAI_API_KEY=你的_Kimi_API_Key
OPENAI_BASE_URL=https://api.moonshot.cn/v1
MODEL_NAME=kimi-k2.6
TAVILY_API_KEY=你的_Tavily_API_Key
AMAP_API_KEY=你的_高德_Web服务_Key
UNSPLASH_ACCESS_KEY=你的_Unsplash_Access_Key
CORS_ORIGINS=["https://kxh-trip-planner.netlify.app"]
```

`CORS_ORIGINS` 是 JSON 格式文本，因此方括号和双引号都要保留。它允许 Netlify 前端跨域调用腾讯云后端。

## 第 3 步：先验证腾讯云后端

服务发布完成后，云托管会分配一个公网 HTTPS 域名。复制域名，在浏览器打开：

```text
https://你的腾讯云域名/api/health
```

正确结果为：

```json
{"status":"ok"}
```

再打开：

```text
https://你的腾讯云域名/docs
```

应能看到 FastAPI 的接口文档。此时浏览器访问的是国内云端后端，已不再经过 Vercel。

## 第 4 步：让 Netlify 前端指向腾讯云

打开 Netlify：

```text
Project configuration -> Environment variables -> VITE_API_BASE_URL
```

将 **Production** 的值改成：

```text
https://你的腾讯云域名/api
```

末尾不要加 `/`。随后进入 Netlify 的 Deploys 页面重新触发一次生产部署。因为 Vite 在构建前端时读取 `VITE_API_BASE_URL`，只改环境变量不会影响已构建的网站。

## 第 5 步：最终验收

1. 不开 VPN 访问 `https://kxh-trip-planner.netlify.app`。
2. 点击“检测后端”，应显示后端已连接。
3. 先提交一个 1 天行程，节省 Kimi 调用额度。
4. 在浏览器开发者工具的 Network 中确认请求目标是腾讯云域名，而不是 `*.vercel.app`。

## 常见错误怎么判断

| 现象 | 含义 | 检查位置 |
| --- | --- | --- |
| `/api/health` 打不开 | 云托管服务或域名尚不可用。 | 公网访问、流量比例、服务日志、域名状态。 |
| 浏览器提示 CORS | 后端未允许 Netlify 域名跨域访问。 | 将 `CORS_ORIGINS` 按上文原样配置后，重新发布后端版本。 |
| “检测后端”成功，但规划返回 HTTP 500 | 浏览器已连通后端，失败发生在后端调用外部服务时。 | 云托管日志与对应 API Key。 |
| 天气或图片失败 | Tavily、Unsplash 由腾讯云服务器调用，不是用户浏览器调用。 | 检查云托管出网能力和服务商在该区域的可用性。 |

## 一个边界

这次迁移解决的是“浏览器访问 Vercel 后端超时”的问题，不会把所有第三方 API 都变成国内服务。Kimi 和高德属于国内服务；Tavily 和 Unsplash 仍是海外服务。若它们从腾讯云服务器调用失败，需要查看云托管日志，再在后续版本中替换服务或使用项目已有的降级结果。
