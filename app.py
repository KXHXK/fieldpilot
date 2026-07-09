import os
import sys

import gradio as gr
import uvicorn


ROOT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.api.main import app as fastapi_app  # noqa: E402


def backend_status() -> str:
    return (
        "FastAPI 后端已启动。\n\n"
        "健康检查地址：/api/health\n\n"
        "旅行规划接口：/api/trip/plan"
    )


demo = gr.Interface(
    fn=backend_status,
    inputs=None,
    outputs=gr.Textbox(label="Backend Status"),
    title="Kxh Trip Planner API",
    description="这个 Space 用 Gradio 作为启动入口，同时挂载 FastAPI 后端接口。",
)

app = gr.mount_gradio_app(fastapi_app, demo, path="/")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
    )
