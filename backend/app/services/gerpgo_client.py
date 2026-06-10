from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
import asyncio

import httpx

from app.core.config import get_settings


@dataclass(frozen=True)
class GerpgoPage:
    data: list[dict[str, Any]]
    next_id: int | None
    raw: dict[str, Any]


class GerpgoRateLimitError(RuntimeError):
    pass


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"your_app_id", "your_app_key", "your_access_token", "appid", "密钥"}


def _is_rate_limit_error(code: Any, messages: Any) -> bool:
    message_text = " ".join(str(message) for message in messages) if isinstance(messages, list) else str(messages or "")
    return code == 90008 or "超过限制" in message_text or "调用次数" in message_text


class GerpgoClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.gerpgo_base_url.rstrip("/")
        self.app_id = settings.gerpgo_app_id
        self.app_key = settings.gerpgo_app_key
        self.access_token = settings.gerpgo_access_token

    def ensure_configured(self) -> None:
        if self.access_token:
            if _looks_like_placeholder(self.access_token):
                raise ValueError("GERPGO_ACCESS_TOKEN 仍是示例值，请在 .env 中填写真实值或留空改用 AppID/AppKey")
            return
        if not self.app_id or not self.app_key:
            raise ValueError("请配置 GERPGO_APP_ID 和 GERPGO_APP_KEY，或设置 GERPGO_ACCESS_TOKEN")
        if _looks_like_placeholder(self.app_id) or _looks_like_placeholder(self.app_key):
            raise ValueError("GERPGO_APP_ID 或 GERPGO_APP_KEY 仍是示例值，请替换为真实值")

    async def get_access_token(self) -> str:
        if self.access_token:
            return self.access_token

        self.ensure_configured()
        url = f"{self.base_url}/open/api_token"
        payload = {"appId": self.app_id, "appKey": self.app_key}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

        code = result.get("code")
        if code not in (0, 200, None):
            messages = result.get("messages") or []
            raise RuntimeError(f"积加 token 接口返回错误 code={code}, messages={messages}")

        token = (result.get("data") or {}).get("accessToken")
        if not token:
            raise RuntimeError("积加 accessToken 响应缺少 accessToken")
        self.access_token = token
        return token

    async def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        access_token = await self.get_access_token()
        # 开放平台调试器实际请求为 /api/open + 文档 apiUrl。
        url = f"{self.base_url}/open{path}"
        headers = {"accessToken": access_token}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                raise RuntimeError(f"积加 HTTP 请求失败 {response.status_code}: {response.text[:500]}")
            result = response.json()
        code = result.get("code")
        if code not in (0, 200, None):
            messages = result.get("messages") or []
            if _is_rate_limit_error(code, messages):
                raise GerpgoRateLimitError(
                    "积加 API 已限流，请等待后重试；保持 count/max_pages 较低，并让 page_delay_seconds >= 1.2"
                )
            raise RuntimeError(f"积加 API 返回错误 code={code}, messages={messages}")
        return result

    async def iter_sp_keyword_pages(
        self,
        market_id: int,
        start_date: str,
        end_date: str,
        count: int = 100,
        max_pages: int | None = None,
        page_delay_seconds: float = 1.2,
    ) -> AsyncIterator[GerpgoPage]:
        next_id = 0
        seen_next_ids: set[int] = set()
        page_count = 0

        while True:
            payload: dict[str, Any] = {
                "marketId": market_id,
                "startDataDate": start_date,
                "endDataDate": end_date,
                "count": count,
                "nextId": next_id,
            }
            raw = await self.post("/operation/ads/spKeywordsPage/query", payload)
            rows = raw.get("data") or []
            ext_obj = raw.get("extObj")
            page_next_id = int(ext_obj) if ext_obj not in (None, "", 0, "0") else None

            yield GerpgoPage(data=rows, next_id=page_next_id, raw=raw)

            page_count += 1
            if max_pages is not None and page_count >= max_pages:
                break
            if not rows or page_next_id is None or page_next_id in seen_next_ids:
                break
            await asyncio.sleep(page_delay_seconds)
            seen_next_ids.add(page_next_id)
            next_id = page_next_id

    async def _iter_paged_report(
        self,
        path: str,
        market_id: int,
        start_date: str,
        end_date: str,
        count: int,
        max_pages: int | None,
        page_delay_seconds: float,
    ) -> AsyncIterator[GerpgoPage]:
        next_id = 0
        seen_next_ids: set[int] = set()
        page_count = 0

        while True:
            payload: dict[str, Any] = {
                "marketId": market_id,
                "startDataDate": start_date,
                "endDataDate": end_date,
                "count": count,
                "nextId": next_id,
            }
            raw = await self.post(path, payload)
            rows = raw.get("data") or []
            ext_obj = raw.get("extObj")
            page_next_id = int(ext_obj) if ext_obj not in (None, "", 0, "0") else None

            yield GerpgoPage(data=rows, next_id=page_next_id, raw=raw)

            page_count += 1
            if max_pages is not None and page_count >= max_pages:
                break
            if not rows or page_next_id is None or page_next_id in seen_next_ids:
                break
            await asyncio.sleep(page_delay_seconds)
            seen_next_ids.add(page_next_id)
            next_id = page_next_id

    async def iter_sp_search_targeting_pages(
        self,
        market_id: int,
        start_date: str,
        end_date: str,
        count: int = 100,
        max_pages: int | None = None,
        page_delay_seconds: float = 1.2,
    ) -> AsyncIterator[GerpgoPage]:
        async for page in self._iter_paged_report(
            "/operation/ads/spSearchTargetingReport/page",
            market_id,
            start_date,
            end_date,
            count,
            max_pages,
            page_delay_seconds,
        ):
            yield page

    async def iter_sp_search_keyword_pages(
        self,
        market_id: int,
        start_date: str,
        end_date: str,
        count: int = 100,
        max_pages: int | None = None,
        page_delay_seconds: float = 1.2,
    ) -> AsyncIterator[GerpgoPage]:
        async for page in self._iter_paged_report(
            "/operation/ads/spSearchKeywordsReport/page",
            market_id,
            start_date,
            end_date,
            count,
            max_pages,
            page_delay_seconds,
        ):
            yield page
