import os
import sys

import uvicorn


ROOT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "7860"))
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=port,
    )
