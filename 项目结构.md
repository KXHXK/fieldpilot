# 项目结构

参考 Datawhale Hello Agents 第十三章：

```text
helloagents-trip-planner/
├── backend/                    # 后端代码
│   ├── app/
│   │   ├── agents/             # 智能体实现
│   │   ├── api/                # API 路由
│   │   ├── models/             # 数据模型
│   │   ├── services/           # 服务层 / 外部工具封装
│   │   └── config.py           # 配置文件
│   └── requirements.txt        # Python 依赖
│
└── frontend/                   # 前端代码
    ├── src/
    │   ├── views/              # 页面组件
    │   ├── services/           # API 服务
    │   ├── types/              # 类型定义
    │   └── router/             # 路由配置
    └── package.json            # npm 依赖
```

