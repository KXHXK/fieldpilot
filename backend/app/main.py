from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

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

app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "message": "HelloAgents Trip Planner backend is running.",
    }
