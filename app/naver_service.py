"""Naver Maps geocoding & navigation URL construction."""

import logging
from urllib.parse import quote

import aiohttp

from app.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

logger = logging.getLogger(__name__)

_GEOCODE_URL = "https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode"


async def geocode(query: str) -> dict | None:
    """Geocode a place name/address to WGS84 coordinates.

    Returns {"lat": float, "lng": float, "address": str} on success,
    or None if no results or API error.
    """
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        logger.error("Naver API credentials not configured")
        return None

    headers = {
        "X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET,
    }
    params = {"query": query}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                _GEOCODE_URL,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logger.error("Naver geocode API returned status %s", resp.status)
                    return None
                data = await resp.json()
    except Exception:
        logger.exception("Naver geocode request failed")
        return None

    addresses = data.get("addresses", [])
    if not addresses:
        return None

    first = addresses[0]
    return {
        "lat": float(first["y"]),
        "lng": float(first["x"]),
        "address": first.get("roadAddress") or first.get("jibunAddress") or query,
    }


def build_directions_url(
    start_lat: float,
    start_lng: float,
    dest_lat: float,
    dest_lng: float,
    dest_name: str,
) -> str:
    """Build a Naver Maps transit directions URL."""
    encoded_name = quote(dest_name)
    return (
        f"https://map.naver.com/v5/directions/"
        f"{start_lng},{start_lat},%ED%98%84%EC%9E%AC%EC%9C%84%EC%B9%98/"
        f"{dest_lng},{dest_lat},{encoded_name}/"
        f"-/transit"
    )
