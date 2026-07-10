import logging
from typing import Any

import requests

from app.config import settings


logger = logging.getLogger(__name__)


class UnsplashService:
    """Unsplash image service."""

    def __init__(self, access_key: str, use_mock: bool = True):
        self.access_key = access_key
        self.use_mock = use_mock
        self.base_url = "https://api.unsplash.com"

    def search_photos(self, query: str, per_page: int = 10) -> list[dict[str, Any]]:
        """Search photos and return normalized image metadata."""
        if self.use_mock:
            return [
                {
                    "url": f"https://source.unsplash.com/800x600/?{query}",
                    "description": f"Mock image for {query}",
                    "photographer": "Unsplash",
                }
            ]

        if not self.access_key:
            logger.warning("UNSPLASH_ACCESS_KEY is empty; skip image search.")
            return []

        try:
            response = requests.get(
                f"{self.base_url}/search/photos",
                params={
                    "query": query,
                    "per_page": per_page,
                    "client_id": self.access_key,
                },
                timeout=6,
            )
            response.raise_for_status()
            data = response.json()

            photos = []
            for result in data.get("results", []):
                photos.append(
                    {
                        "url": result["urls"]["regular"],
                        "description": result.get("description") or "",
                        "photographer": result["user"]["name"],
                    }
                )
            return photos
        except Exception as exc:
            logger.warning(
                "Unsplash image search failed for query=%r, error_type=%s",
                query,
                type(exc).__name__,
            )
            return []

    def get_photo_url(self, query: str) -> str | None:
        """Get one image URL for a query."""
        photos = self.search_photos(query=query, per_page=1)
        return photos[0].get("url") if photos else None

    def get_attraction_photo_url(
        self,
        city: str,
        attraction_name: str,
        category: str | None,
    ) -> str | None:
        """Get one real attraction image without serial fallback retries."""
        category_query = _category_to_unsplash_query(category)
        return self.get_photo_url(f"{city} {attraction_name} {category_query}")


def get_unsplash_service() -> UnsplashService:
    return UnsplashService(
        access_key=settings.unsplash_access_key,
        use_mock=settings.use_mock_images,
    )


def _category_to_unsplash_query(category: str | None) -> str:
    text = category or ""
    if "博物馆" in text or "科教" in text or "文化" in text:
        return "museum exterior"
    if "公园" in text or "风景" in text or "自然" in text:
        return "park landscape"
    if "商业" in text or "购物" in text:
        return "city street"
    if "纪念" in text or "历史" in text:
        return "historic landmark"
    return "landmark"
