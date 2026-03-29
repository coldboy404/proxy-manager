#!/usr/bin/env python3

import asyncio
import base64
import json
import logging
import os
import random
import socket
import struct
import threading
import time
from urllib.parse import urlsplit
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp
import requests
from flask import Flask, jsonify, render_template, request

from .proxy_query import filter_sort_paginate_proxies
from .runtime import ManagedAsyncServer


DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR.parent / "templates"
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))
TEST_INTERVAL = int(os.getenv("TEST_INTERVAL", "60"))
TEST_COUNT = int(os.getenv("TEST_COUNT", "50"))
TIMEOUT = int(os.getenv("TIMEOUT", "10"))
TEST_MODE = os.getenv("TEST_MODE", "tcp").lower()
TEST_URL = os.getenv("TEST_URL", "https://www.google.com")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

AUTO_FETCH = os.getenv("AUTO_FETCH", "false").lower() == "true"
AUTO_TEST = os.getenv("AUTO_TEST", "false").lower() == "true"
AUTO_FETCH_TYPE = os.getenv("AUTO_FETCH_TYPE", "all").lower()
AUTO_FETCH_COUNTRIES = [
    c.strip().upper()
    for c in os.getenv("AUTO_FETCH_COUNTRIES", "US,JP,SG").split(",")
    if c.strip()
]
AUTO_FETCH_LIMIT = int(os.getenv("AUTO_FETCH_LIMIT", "50"))
AUTO_TEST_COUNT = int(os.getenv("AUTO_TEST_COUNT", str(TEST_COUNT)))
FETCH_LIMIT_PER_COUNTRY = int(os.getenv("FETCH_LIMIT_PER_COUNTRY", "50"))

SOCKS5_ENABLED = os.getenv("SOCKS5_ENABLED", "true").lower() == "true"
SOCKS5_HOST = os.getenv("SOCKS5_HOST", "0.0.0.0")
SOCKS5_PORT = int(os.getenv("SOCKS5_PORT", "5001"))
SOCKS5_AUTH = os.getenv("SOCKS5_AUTH", "false").lower() == "true"
SOCKS5_USER = os.getenv("SOCKS5_USER", "proxyuser")
SOCKS5_PASS = os.getenv("SOCKS5_PASS", "proxypass")

HTTP_PROXY_ENABLED = os.getenv("HTTP_PROXY_ENABLED", "true").lower() == "true"
HTTP_PROXY_HOST = os.getenv("HTTP_PROXY_HOST", "0.0.0.0")
HTTP_PROXY_PORT = int(os.getenv("HTTP_PROXY_PORT", "5002"))
HTTP_PROXY_AUTH = os.getenv("HTTP_PROXY_AUTH", "false").lower() == "true"
HTTP_PROXY_USER = os.getenv("HTTP_PROXY_USER", "proxyuser")
HTTP_PROXY_PASS = os.getenv("HTTP_PROXY_PASS", "proxypass")


PROXY_URLS = {
    "all": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/all/data",
    "http": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data",
    "https": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/https/data",
    "socks4": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks4/data",
    "socks5": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data",
}


logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("proxy-manager")


@dataclass
class Proxy:
    ip: str
    port: str
    protocol: str
    country: str = ""
    anonymity: str = ""
    source: str = ""
    latency: Optional[float] = None
    last_tested: Optional[str] = None
    is_working: bool = False
    speed_ms: Optional[float] = None

    @property
    def address(self) -> str:
        return f"{self.ip}:{self.port}"

    @property
    def proxy_url(self) -> str:
        if self.protocol.lower() in {"socks4", "socks5"}:
            return f"{self.protocol.lower()}://{self.ip}:{self.port}"
        return f"http://{self.ip}:{self.port}"

    def to_dict(self) -> Dict:
        data = asdict(self)
        data["address"] = self.address
        return data


class AppState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.proxies: List[Proxy] = []
        self.working: Dict[str, Proxy] = {}
        self.last_update: Optional[datetime] = None
        self.last_test: Optional[datetime] = None
        self.current_proxy: Optional[Proxy] = None
        self.current_proxy_time: Optional[datetime] = None
        self.is_testing = False
        self.runtime = {
            "last_fetch_error": "",
            "last_test_error": "",
            "socks5_server_enabled": False,
            "http_proxy_server_enabled": False,
        }
        self.stats = {
            "total_fetched": 0,
            "total_tested": 0,
            "working_count": 0,
            "avg_latency": 0,
            "socks5_connections": 0,
            "socks5_bytes_transferred": 0,
            "http_proxy_connections": 0,
            "http_proxy_requests": 0,
            "http_proxy_bytes": 0,
        }

    def snapshot_config(self) -> Dict:
        return load_runtime_config()

    def set_proxies(self, proxies: List[Proxy]) -> None:
        with self.lock:
            self.proxies = proxies
            self.last_update = datetime.now()
            self.stats["total_fetched"] = len(proxies)
            valid_addresses = {proxy.address for proxy in proxies}
            self.working = {
                k: v for k, v in self.working.items() if k in valid_addresses
            }
            self.stats["working_count"] = len(self.working)
            self.stats["avg_latency"] = compute_average_latency(
                list(self.working.values())
            )
            if self.current_proxy and self.current_proxy.address not in valid_addresses:
                self.current_proxy = None
                self.current_proxy_time = None

    def get_all_proxies(self) -> List[Dict]:
        with self.lock:
            return [proxy.to_dict() for proxy in self.proxies]

    def get_working_proxies(self, limit: int = 100) -> List[Dict]:
        with self.lock:
            ordered = sorted(
                self.working.values(),
                key=lambda proxy: (
                    proxy.speed_ms if proxy.speed_ms is not None else float("inf")
                ),
            )
            return [proxy.to_dict() for proxy in ordered[:limit]]

    def get_stats(self) -> Dict:
        with self.lock:
            return {
                **self.stats,
                **self.runtime,
                "last_update": self.last_update.isoformat()
                if self.last_update
                else None,
                "last_test": self.last_test.isoformat() if self.last_test else None,
                "is_testing": self.is_testing,
            }

    def get_connection_info(self) -> Dict:
        config = self.snapshot_config()
        locked_address = str(config.get("preferred_address", ""))
        with self.lock:
            return {
                "connected": self.current_proxy is not None,
                "last_used": self.current_proxy_time.isoformat()
                if self.current_proxy_time
                else None,
                "proxy": self.current_proxy.to_dict() if self.current_proxy else None,
                "locked": bool(locked_address),
                "preferred": {
                    "protocol": config.get("protocol", "all"),
                    "country": config.get("country", ""),
                    "address": locked_address,
                },
            }

    def choose_proxy(
        self,
        preferred_protocol: str = "",
        preferred_country: str = "",
        allowed_protocols: Optional[List[str]] = None,
        prefer_protocols: Optional[List[str]] = None,
    ) -> Optional[Proxy]:
        config = self.snapshot_config()
        address = str(config.get("preferred_address", "")).strip()
        protocol = (preferred_protocol or str(config.get("protocol", "all"))).lower()
        country = (preferred_country or str(config.get("country", ""))).upper()
        allowed = {item.lower() for item in (allowed_protocols or []) if item}
        preferred_order = [item.lower() for item in (prefer_protocols or []) if item]

        def apply_filters(items: List[Proxy]) -> List[Proxy]:
            filtered = [proxy for proxy in items if proxy.is_working]
            if allowed:
                filtered = [
                    proxy for proxy in filtered if proxy.protocol.lower() in allowed
                ]
            if country:
                filtered = [
                    proxy for proxy in filtered if proxy.country.upper() == country
                ]
            if protocol and protocol != "all":
                filtered = [
                    proxy for proxy in filtered if proxy.protocol.lower() == protocol
                ]
            return filtered

        def rank_candidates(items: List[Proxy]) -> List[Proxy]:
            def order_value(proxy: Proxy) -> int:
                proto = proxy.protocol.lower()
                return preferred_order.index(proto) if proto in preferred_order else len(preferred_order)

            return sorted(
                items,
                key=lambda proxy: (
                    order_value(proxy),
                    proxy.speed_ms if proxy.speed_ms is not None else float("inf"),
                    proxy.address,
                ),
            )

        with self.lock:
            working = list(self.working.values())

            if self.current_proxy and self.current_proxy.address in self.working:
                active = self.working[self.current_proxy.address]
                if apply_filters([active]):
                    self.current_proxy = active
                    self.current_proxy_time = datetime.now()
                    return active

            if address:
                saved = self.working.get(address)
                if saved and apply_filters([saved]):
                    self.current_proxy = saved
                    self.current_proxy_time = datetime.now()
                    return saved

            candidates = apply_filters(working)
            if not candidates and protocol and protocol != "all":
                relaxed = [proxy for proxy in working if proxy.is_working]
                if allowed:
                    relaxed = [
                        proxy for proxy in relaxed if proxy.protocol.lower() in allowed
                    ]
                if country:
                    relaxed = [
                        proxy for proxy in relaxed if proxy.country.upper() == country
                    ]
                candidates = relaxed

            if not candidates and allowed:
                candidates = [
                    proxy
                    for proxy in working
                    if proxy.is_working and proxy.protocol.lower() in allowed
                ]

            if not candidates:
                candidates = [proxy for proxy in working if proxy.is_working]

            if not candidates:
                return None

            ordered = rank_candidates(candidates)
            proxy = ordered[0]
            self.current_proxy = proxy
            self.current_proxy_time = datetime.now()
            return proxy

    def set_current_proxy(self, address: str) -> Optional[Proxy]:
        with self.lock:
            proxy = self.working.get(address)
            if not proxy or not proxy.is_working:
                return None
            self.current_proxy = proxy
            self.current_proxy_time = datetime.now()
            return proxy

    def clear_current_proxy(self) -> None:
        with self.lock:
            self.current_proxy = None
            self.current_proxy_time = None

    def get_proxy_by_address(self, address: str) -> Optional[Proxy]:
        with self.lock:
            proxy = self.working.get(address)
            if proxy and proxy.is_working:
                return proxy
            return None

    async def test_proxies(
        self, count: int, protocol: str = "", country: str = ""
    ) -> List[Proxy]:
        with self.lock:
            candidates = list(self.proxies)
            self.is_testing = True

        try:
            if protocol and protocol.lower() != "all":
                candidates = [
                    proxy
                    for proxy in candidates
                    if proxy.protocol.lower() == protocol.lower()
                ]
            if country and country.upper() != "ALL":
                candidates = [
                    proxy
                    for proxy in candidates
                    if proxy.country.upper() == country.upper()
                ]
            if not candidates:
                logger.warning("没有可用的代理进行测试")
                return []

            candidates.sort(
                key=lambda proxy: (
                    0 if not proxy.last_tested else 1,
                    0 if not proxy.is_working else 1,
                    proxy.speed_ms if proxy.speed_ms is not None else float("inf"),
                    proxy.address,
                )
            )
            selected = candidates[: min(count, len(candidates))]
            logger.info("开始测试 %s 个代理...", len(selected))

            async with aiohttp.ClientSession() as session:
                await asyncio.gather(
                    *(self._test_single_proxy(session, proxy) for proxy in selected)
                )

            working = [proxy for proxy in selected if proxy.is_working]
            with self.lock:
                self.working = {
                    proxy.address: proxy for proxy in self.proxies if proxy.is_working
                }
                self.last_test = datetime.now()
                self.stats["total_tested"] += len(selected)
                self.stats["working_count"] = len(working)
                self.stats["avg_latency"] = compute_average_latency(working)
                if (
                    self.current_proxy
                    and self.current_proxy.address not in self.working
                ):
                    self.current_proxy = None
                    self.current_proxy_time = None

            with self.lock:
                self.runtime["last_test_error"] = ""
            logger.info("测试完成：%s/%s 可用", len(working), len(selected))
            return working
        except Exception as exc:
            with self.lock:
                self.runtime["last_test_error"] = str(exc)
            raise
        finally:
            with self.lock:
                self.is_testing = False

    async def _test_single_proxy(
        self, session: aiohttp.ClientSession, proxy: Proxy
    ) -> None:
        try:
            if TEST_MODE == "tcp":
                start = time.time()
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(proxy.ip, int(proxy.port)),
                    timeout=TIMEOUT,
                )
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                latency = (time.time() - start) * 1000
            else:
                start = time.time()
                async with session.get(
                    TEST_URL,
                    proxy=proxy.proxy_url,
                    timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                    allow_redirects=False,
                ) as response:
                    if response.status >= 400:
                        raise RuntimeError(f"bad status {response.status}")
                    latency = (time.time() - start) * 1000

            proxy.is_working = True
            proxy.speed_ms = latency
            proxy.latency = latency
            proxy.last_tested = datetime.now().isoformat()
        except Exception:
            proxy.is_working = False
            proxy.speed_ms = None
            proxy.latency = None
            proxy.last_tested = datetime.now().isoformat()


state = AppState()
socks5_runtime = None
http_runtime = None


def compute_average_latency(proxies: List[Proxy]) -> float:
    latencies = [proxy.speed_ms for proxy in proxies if proxy.speed_ms is not None]
    if not latencies:
        return 0
    return sum(latencies) / len(latencies)


def geo_cache_path() -> Path:
    return DATA_DIR / "geo_cache.json"


def load_geo_cache() -> Dict[str, str]:
    path = geo_cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_geo_cache(cache: Dict[str, str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    geo_cache_path().write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def resolve_country_code(value: str, cache: Optional[Dict[str, str]] = None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    cache = cache if cache is not None else load_geo_cache()
    if raw in cache:
        return cache[raw]
    target = raw
    try:
        ip = socket.gethostbyname(raw)
        target = ip
        if ip in cache:
            cache[raw] = cache[ip]
            return cache[ip]
    except Exception:
        target = raw
    try:
        response = requests.get(f"https://ipapi.co/{target}/country/", timeout=5)
        if response.ok:
            code = response.text.strip().upper()
            if len(code) == 2 and code.isalpha():
                cache[raw] = code
                cache[target] = code
                return code
    except Exception:
        pass
    return ""


def enrich_proxy_countries(items: List[Proxy]) -> None:
    cache = load_geo_cache()
    changed = False
    for proxy in items:
        if proxy.country:
            continue
        code = resolve_country_code(proxy.ip, cache)
        if code:
            proxy.country = code
            changed = True
    if changed:
        save_geo_cache(cache)


def config_path() -> Path:
    return DATA_DIR / "config.json"


def favorites_path() -> Path:
    return DATA_DIR / "favorites.json"


def socks5_config_path() -> Path:
    return DATA_DIR / "socks5_config.json"


def http_proxy_config_path() -> Path:
    return DATA_DIR / "http_proxy_config.json"


def default_socks5_config() -> Dict:
    return {
        "enabled": SOCKS5_ENABLED,
        "host": SOCKS5_HOST,
        "port": SOCKS5_PORT,
        "auth_enabled": SOCKS5_AUTH,
        "username": SOCKS5_USER,
        "password": SOCKS5_PASS,
    }


def default_http_proxy_config() -> Dict:
    return {
        "enabled": HTTP_PROXY_ENABLED,
        "host": HTTP_PROXY_HOST,
        "port": HTTP_PROXY_PORT,
        "auth_enabled": HTTP_PROXY_AUTH,
        "username": HTTP_PROXY_USER,
        "password": HTTP_PROXY_PASS,
    }


def load_socks5_config() -> Dict:
    path = socks5_config_path()
    if not path.exists():
        return default_socks5_config()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        merged = {**default_socks5_config(), **data}
        merged["port"] = int(merged.get("port", SOCKS5_PORT))
        merged["enabled"] = bool(merged.get("enabled", True))
        merged["auth_enabled"] = bool(merged.get("auth_enabled", False))
        merged["username"] = str(merged.get("username", SOCKS5_USER))
        merged["password"] = str(merged.get("password", SOCKS5_PASS))
        return merged
    except Exception:
        return default_socks5_config()


def load_http_proxy_config() -> Dict:
    path = http_proxy_config_path()
    if not path.exists():
        return default_http_proxy_config()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        merged = {**default_http_proxy_config(), **data}
        merged["port"] = int(merged.get("port", HTTP_PROXY_PORT))
        merged["enabled"] = bool(merged.get("enabled", True))
        merged["auth_enabled"] = bool(merged.get("auth_enabled", False))
        merged["username"] = str(merged.get("username", HTTP_PROXY_USER))
        merged["password"] = str(merged.get("password", HTTP_PROXY_PASS))
        return merged
    except Exception:
        return default_http_proxy_config()


def default_config() -> Dict:
    return {
        "enabled": True,
        "type": AUTO_FETCH_TYPE,
        "protocol": "all",
        "country": "",
        "test_count": TEST_COUNT,
        "test_interval": TEST_INTERVAL,
        "rotate_interval": 300,
        "preferred_address": "",
        "fetch_limit": AUTO_FETCH_LIMIT if AUTO_FETCH_LIMIT > 0 else 50,
        "fetch_countries": AUTO_FETCH_COUNTRIES,
        "subscriptions": [],
    }


def normalize_runtime_config(config: Dict) -> Dict:
    normalized = {**default_config(), **config}

    normalized["type"] = str(normalized.get("type", AUTO_FETCH_TYPE)).lower()
    normalized["protocol"] = str(
        normalized.get("protocol", normalized.get("type", "all"))
    ).lower()
    normalized["country"] = str(normalized.get("country", "")).upper()
    normalized["preferred_address"] = str(
        normalized.get("preferred_address", "")
    ).strip()

    try:
        normalized["test_count"] = max(
            1, min(200, int(normalized.get("test_count", TEST_COUNT)))
        )
    except Exception:
        normalized["test_count"] = TEST_COUNT

    try:
        normalized["test_interval"] = max(
            10, min(3600, int(normalized.get("test_interval", TEST_INTERVAL)))
        )
    except Exception:
        normalized["test_interval"] = TEST_INTERVAL

    try:
        normalized["rotate_interval"] = max(
            30, min(7200, int(normalized.get("rotate_interval", 300)))
        )
    except Exception:
        normalized["rotate_interval"] = 300

    try:
        normalized["fetch_limit"] = max(
            1, min(1000, int(normalized.get("fetch_limit", AUTO_FETCH_LIMIT or 50)))
        )
    except Exception:
        normalized["fetch_limit"] = AUTO_FETCH_LIMIT if AUTO_FETCH_LIMIT > 0 else 50

    fetch_countries = normalized.get("fetch_countries", AUTO_FETCH_COUNTRIES)
    if not isinstance(fetch_countries, list):
        fetch_countries = AUTO_FETCH_COUNTRIES
    normalized["fetch_countries"] = [
        str(item).strip().upper() for item in fetch_countries if str(item).strip()
    ]

    subscriptions = normalized.get("subscriptions", [])
    if not isinstance(subscriptions, list):
        subscriptions = []
    normalized["subscriptions"] = subscriptions
    normalized["subscription_urls"] = [
        str(item.get("url", "")).strip()
        for item in load_subscriptions_from_config(normalized)
        if str(item.get("url", "")).strip()
    ]

    return normalized


def load_subscriptions_from_config(config: Dict) -> List[Dict]:
    items = config.get("subscriptions", [])
    normalized = []
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                normalized.append(
                    {
                        "name": str(item.get("name", "")).strip(),
                        "source": str(item.get("source", "remote")).strip() or "remote",
                        "interval": max(10, int(item.get("interval", 60))),
                        "url": str(item.get("url", "")).strip(),
                    }
                )
            elif isinstance(item, str):
                value = item.strip()
                if value:
                    normalized.append(
                        {
                            "name": value,
                            "source": "remote",
                            "interval": 60,
                            "url": value,
                        }
                    )
    return normalized


def load_runtime_config() -> Dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = config_path()
    if not path.exists():
        return normalize_runtime_config(default_config())
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return normalize_runtime_config(data)
    except Exception:
        return normalize_runtime_config(default_config())


def save_runtime_config(updates: Dict) -> Dict:
    config = normalize_runtime_config({**load_runtime_config(), **updates})
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(config_path(), "w", encoding="utf-8") as handle:
        json.dump(config, handle, ensure_ascii=True, indent=2)
    return config


def load_favorites() -> List[Dict]:
    path = favorites_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_favorites(items: List[Dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(favorites_path(), "w", encoding="utf-8") as handle:
        json.dump(items, handle, ensure_ascii=True, indent=2)


def load_subscriptions() -> List[Dict]:
    config = load_runtime_config()
    return load_subscriptions_from_config(config)


def save_subscriptions(items: List[Dict]) -> Dict:
    normalized = []
    for item in items:
        normalized.append(
            {
                "name": str(item.get("name", "")).strip(),
                "source": str(item.get("source", "remote")).strip() or "remote",
                "interval": max(10, int(item.get("interval", 60))),
                "url": str(item.get("url", "")).strip(),
            }
        )
    config = save_runtime_config({"subscriptions": normalized})
    return config


def build_proxy_from_payload(
    payload: object, default_protocol: str, country_hint: str = ""
) -> Optional[Proxy]:
    if isinstance(payload, dict):
        country = payload.get("country") or payload.get("Country") or country_hint
        protocol = str(
            payload.get("protocol") or payload.get("Protocol") or default_protocol
        ).lower()
        if protocol not in SUPPORTED_PROTOCOLS:
            return None
        return Proxy(
            ip=str(payload.get("ip") or payload.get("Ip") or ""),
            port=str(payload.get("port") or payload.get("Port") or ""),
            protocol=protocol,
            country=str(country or "").upper(),
            anonymity=str(payload.get("anonymity") or payload.get("Anonymity") or ""),
            source=str(payload.get("source") or payload.get("Source") or ""),
        )

    parts = str(payload).split(":")
    if len(parts) < 2:
        return None
    protocol = str(default_protocol).lower()
    if protocol not in SUPPORTED_PROTOCOLS:
        return None
    return Proxy(
        ip=parts[0],
        port=parts[1],
        protocol=protocol,
        country=country_hint.upper() if country_hint else "",
        source="",
    )


def normalize_base64(text: str) -> str:
    text = text.strip().replace("\n", "").replace("\r", "")
    missing = len(text) % 4
    if missing:
        text += "=" * (4 - missing)
    return text


def decode_base64_text(text: str) -> str:
    try:
        return base64.b64decode(normalize_base64(text)).decode("utf-8", errors="ignore")
    except Exception:
        try:
            return base64.urlsafe_b64decode(normalize_base64(text)).decode("utf-8", errors="ignore")
        except Exception:
            return ""


def is_base64_text(value: str) -> bool:
    text = value.strip().replace("\n", "")
    if not text or len(text) % 4 != 0:
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=_-")
    return all(ch in allowed for ch in text)


def parse_uri_proxy(line: str) -> Optional[Proxy]:
    if line.startswith(("socks5://", "socks4://", "http://", "https://")):
        parsed = urlsplit(line)
        host = parsed.hostname or ""
        port = parsed.port or 0
        if not host or not port:
            return None
        protocol = parsed.scheme.lower()
        if protocol not in SUPPORTED_PROTOCOLS:
            return None
        return Proxy(ip=host, port=str(port), protocol=protocol, country="", source="")
    return None


def parse_clash_style_proxies(text: str) -> List[Proxy]:
    proxies: List[Proxy] = []
    in_block = False
    current: Dict[str, str] = {}

    def flush_current() -> None:
        nonlocal current
        if not current:
            return
        server = str(current.get("server", "")).strip()
        port = str(current.get("port", "")).strip()
        protocol = str(current.get("type", "")).strip().lower()
        if server and port and protocol in SUPPORTED_PROTOCOLS:
            proxies.append(Proxy(ip=server, port=port, protocol=protocol, country=""))
        current = {}

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("proxies:"):
            in_block = True
            continue
        if not in_block and not stripped.startswith("- "):
            continue
        if stripped.startswith("- "):
            flush_current()
            in_block = True
            stripped = stripped[2:].strip()
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                current[key.strip()] = value.strip().strip("\"'")
            continue
        if not in_block or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        current[key.strip()] = value.strip().strip("\"'")

    flush_current()
    return proxies


def parse_subscription_text(raw_text: str, default_protocol: str = "all") -> List[Proxy]:
    text = raw_text.strip()
    if not text:
        return []

    if "\n" not in text and is_base64_text(text):
        decoded = decode_base64_text(text)
        if decoded.strip():
            text = decoded.strip()

    if text.lstrip().startswith("proxies:") or "\nproxies:" in text or "server:" in text and "type:" in text:
        clash_proxies = parse_clash_style_proxies(text)
        if clash_proxies:
            return clash_proxies

    proxies: List[Proxy] = []
    for line in text.splitlines():
        row = line.strip()
        if not row or row.startswith("#"):
            continue

        proxy = parse_uri_proxy(row)
        if proxy:
            proxies.append(proxy)
            continue

        protocol = default_protocol if default_protocol and default_protocol != "all" else "http"
        address = row
        if "://" in row:
            parts = row.split("://", 1)
            protocol = parts[0].lower() or protocol
            address = parts[1]
        proxy = build_proxy_from_payload(address, protocol)
        if proxy and proxy.ip and proxy.port:
            proxy.protocol = protocol if protocol in SUPPORTED_PROTOCOLS else proxy.protocol
            if proxy.protocol in SUPPORTED_PROTOCOLS:
                proxies.append(proxy)
    return proxies


def dedupe_proxies(items: List[Proxy]) -> List[Proxy]:
    unique: Dict[str, Proxy] = {}
    for proxy in items:
        key = f"{proxy.protocol.lower()}://{proxy.address}"
        if key not in unique:
            unique[key] = proxy
    return list(unique.values())


def fetch_custom_subscription(url: str, default_protocol: str = "all") -> List[Proxy]:
    logger.info("正在拉取自定义订阅：%s", url)
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    content_type = (response.headers.get("content-type") or "").lower()
    rows: List[Proxy] = []

    try:
        payload = response.json()
        raw_rows = payload.get("proxies", payload) if isinstance(payload, dict) else payload
        if isinstance(raw_rows, list):
            for row in raw_rows:
                proxy = build_proxy_from_payload(row, default_protocol)
                if proxy and proxy.ip and proxy.port:
                    rows.append(proxy)
            return rows
    except Exception:
        pass

    text = response.text or ""
    if "application/json" in content_type:
        return []
    return parse_subscription_text(text, default_protocol=default_protocol)


def fetch_proxy_feed(proxy_type: str = "all", country: str = "") -> List[Proxy]:
    if country and country.upper() != "ALL":
        url = f"https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/{country.upper()}/data.json"
    else:
        url = f"{PROXY_URLS.get(proxy_type, PROXY_URLS['all'])}.json"

    logger.info("正在获取代理列表：%s", url)
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("proxies", payload) if isinstance(payload, dict) else payload
    proxies: List[Proxy] = []
    for row in rows:
        proxy = build_proxy_from_payload(row, proxy_type, country)
        if proxy and proxy.ip and proxy.port:
            proxies.append(proxy)

    if (
        country
        and FETCH_LIMIT_PER_COUNTRY > 0
        and len(proxies) > FETCH_LIMIT_PER_COUNTRY
    ):
        proxies = random.sample(proxies, FETCH_LIMIT_PER_COUNTRY)
    return proxies


def summarize_subscription_nodes() -> Dict:
    subs = load_subscriptions()
    if not subs:
        return {"total": 0, "available": 0, "sources": []}

    all_proxies = state.get_all_proxies()
    working_addresses = {
        item.get("address") for item in state.get_working_proxies(limit=100000)
    }

    sources = []
    total = 0
    available = 0
    for sub in subs:
        url = sub.get("url", "")
        source_nodes = [proxy for proxy in all_proxies if proxy.get("source") == url]
        source_total = len(source_nodes)
        source_available = sum(
            1 for proxy in source_nodes if proxy.get("address") in working_addresses
        )
        total += source_total
        available += source_available
        sources.append(
            {
                "name": sub.get("name", url),
                "source": sub.get("source", "remote"),
                "interval": sub.get("interval", 60),
                "url": url,
                "total": source_total,
                "available": source_available,
            }
        )

    return {"total": total, "available": available, "sources": sources}


def refresh_proxy_pool(
    proxy_type: str,
    country: str,
    countries: List[str],
    limit: int,
    subscription_urls: Optional[List[str]] = None,
) -> int:
    try:
        collected: List[Proxy] = []
        if countries:
            for item in countries:
                try:
                    collected.extend(fetch_proxy_feed(proxy_type, item))
                except Exception as exc:
                    logger.error("拉取 %s 代理失败：%s", item, exc)
        else:
            collected.extend(fetch_proxy_feed(proxy_type, country))

        for sub_url in (subscription_urls or []):
            if not sub_url:
                continue
            try:
                sub_nodes = fetch_custom_subscription(sub_url, default_protocol=proxy_type)
                for node in sub_nodes:
                    node.source = sub_url
                collected.extend(sub_nodes)
            except Exception as exc:
                logger.error("拉取自定义订阅失败 %s：%s", sub_url, exc)

        proxies = dedupe_proxies(collected)
        if limit > 0 and len(proxies) > limit:
            proxies = random.sample(proxies, limit)

        enrich_proxy_countries(proxies)
        state.set_proxies(proxies)
        with state.lock:
            state.runtime["last_fetch_error"] = ""
        logger.info("成功获取 %s 个代理", len(proxies))
        return len(proxies)
    except Exception as exc:
        with state.lock:
            state.runtime["last_fetch_error"] = str(exc)
        logger.error("获取代理失败：%s", exc)
        return 0


def background_fetch_loop() -> None:
    logger.info("后台拉取服务已启动")
    while True:
        config = load_runtime_config()
        time.sleep(max(30, POLL_INTERVAL))
        if not config.get("enabled", True):
            continue
        country = str(config.get("country", "")).upper()
        countries = (
            []
            if country
            else [
                item.upper()
                for item in config.get("fetch_countries", AUTO_FETCH_COUNTRIES)
            ]
        )
        refresh_proxy_pool(
            proxy_type=str(config.get("type", AUTO_FETCH_TYPE)).lower(),
            country=country,
            countries=countries,
            limit=int(config.get("fetch_limit", AUTO_FETCH_LIMIT)),
            subscription_urls=config.get("subscription_urls", []),
        )


def background_rotate_loop() -> None:
    logger.info("后台自动切换代理服务已启动")
    while True:
        config = load_runtime_config()
        interval = max(30, int(config.get("rotate_interval", 300)))
        time.sleep(interval)
        if not config.get("enabled", True):
            continue
        if str(config.get("preferred_address", "")).strip():
            continue
        proxy = state.choose_proxy(
            preferred_protocol=str(config.get("protocol", "all")),
            preferred_country=str(config.get("country", "")),
        )
        if proxy:
            logger.info("自动切换当前代理：%s", proxy.address)


def background_test_loop() -> None:
    logger.info("后台测速服务已启动")
    while True:
        config = load_runtime_config()
        time.sleep(max(10, int(config.get("test_interval", TEST_INTERVAL))))
        if not config.get("enabled", True):
            continue
        asyncio.run(
            state.test_proxies(
                count=int(config.get("test_count", TEST_COUNT)),
                protocol=str(config.get("protocol", "all")),
                country=str(config.get("country", "")),
            )
        )


def initial_refresh() -> None:
    config = load_runtime_config()
    if AUTO_FETCH:
        refresh_proxy_pool(
            proxy_type=str(config.get("type", AUTO_FETCH_TYPE)).lower(),
            country=str(config.get("country", "")).upper(),
            countries=[]
            if config.get("country")
            else [
                item.upper()
                for item in config.get("fetch_countries", AUTO_FETCH_COUNTRIES)
            ],
            limit=int(config.get("fetch_limit", AUTO_FETCH_LIMIT)),
            subscription_urls=config.get("subscription_urls", []),
        )
    if AUTO_TEST:
        asyncio.run(
            state.test_proxies(
                count=int(config.get("test_count", AUTO_TEST_COUNT)),
                protocol=str(config.get("protocol", "all")),
                country=str(config.get("country", "")),
            )
        )


async def pipe_stream(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, stat_key: str
) -> None:
    try:
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
            with state.lock:
                state.stats[stat_key] = state.stats.get(stat_key, 0) + len(chunk)
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def tunnel_bidirectional(
    client_reader, client_writer, upstream_reader, upstream_writer, stat_key: str
) -> None:
    await asyncio.gather(
        pipe_stream(client_reader, upstream_writer, stat_key),
        pipe_stream(upstream_reader, client_writer, stat_key),
        return_exceptions=True,
    )


class SOCKS5Server:
    def __init__(self) -> None:
        self.logger = logging.getLogger("socks5")

    async def start(self, runtime=None) -> None:
        config = load_socks5_config()
        if not config.get("enabled", True):
            self.logger.info("SOCKS5 服务器已禁用")
            return
        host = str(config.get("host", SOCKS5_HOST))
        port = int(config.get("port", SOCKS5_PORT))
        server = await asyncio.start_server(self.handle_client, host, port)
        if runtime is not None:
            runtime.attach(asyncio.get_running_loop(), server)
        with state.lock:
            state.runtime["socks5_listen_host"] = host
            state.runtime["socks5_listen_port"] = port
        self.logger.info("SOCKS5 服务器启动：%s:%s", host, port)
        async with server:
            await server.serve_forever()

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        client_addr = writer.get_extra_info("peername")
        self.logger.info("新连接：%s", client_addr)
        try:
            version = await reader.readexactly(1)
            if version[0] != 0x05:
                return
            nmethods = await reader.readexactly(1)
            methods = await reader.readexactly(nmethods[0])

            config = load_socks5_config()
            auth_enabled = bool(config.get("auth_enabled", False))

            if auth_enabled and 0x02 in methods:
                writer.write(bytes([0x05, 0x02]))
                await writer.drain()
                await self._handle_auth(reader, writer, config)
            elif not auth_enabled and 0x00 in methods:
                writer.write(bytes([0x05, 0x00]))
                await writer.drain()
            elif 0x00 in methods:
                writer.write(bytes([0x05, 0x00]))
                await writer.drain()
            else:
                writer.write(bytes([0x05, 0xFF]))
                await writer.drain()
                return

            version = await reader.readexactly(1)
            cmd = await reader.readexactly(1)
            await reader.readexactly(1)
            atype = await reader.readexactly(1)
            target_host, target_port, address_bytes = await self._read_destination(
                reader, atype[0]
            )
            if version[0] != 0x05 or cmd[0] != 0x01:
                await self._fail(writer, 0x07)
                return

            proxy = state.choose_proxy()
            if not proxy:
                self.logger.warning("没有可用的代理")
                await self._fail(writer, 0x01)
                return

            self.logger.info("使用代理：%s (%s)", proxy.address, proxy.protocol)
            success = await self._connect_via_proxy(
                proxy, target_host, target_port, atype[0], address_bytes, reader, writer
            )
            if success:
                with state.lock:
                    state.stats["socks5_connections"] += 1
        except Exception as exc:
            self.logger.error("处理连接错误：%s", exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_auth(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        config: Dict,
    ) -> None:
        await reader.readexactly(1)
        ulen = await reader.readexactly(1)
        username = await reader.readexactly(ulen[0])
        plen = await reader.readexactly(1)
        password = await reader.readexactly(plen[0])
        expected_user = str(config.get("username", SOCKS5_USER))
        expected_pass = str(config.get("password", SOCKS5_PASS))
        if username.decode() == expected_user and password.decode() == expected_pass:
            writer.write(bytes([0x01, 0x00]))
            await writer.drain()
            return
        writer.write(bytes([0x01, 0x01]))
        await writer.drain()
        raise RuntimeError("SOCKS5 auth failed")

    async def _read_destination(
        self, reader: asyncio.StreamReader, atype: int
    ) -> Tuple[str, int, bytes]:
        if atype == 0x01:
            raw = await reader.readexactly(4)
            host = socket.inet_ntoa(raw)
            address_bytes = raw
        elif atype == 0x03:
            length = await reader.readexactly(1)
            raw = await reader.readexactly(length[0])
            host = raw.decode()
            address_bytes = length + raw
        elif atype == 0x04:
            raw = await reader.readexactly(16)
            host = socket.inet_ntop(socket.AF_INET6, raw)
            address_bytes = raw
        else:
            raise RuntimeError("unsupported address type")
        port_raw = await reader.readexactly(2)
        return host, struct.unpack(">H", port_raw)[0], address_bytes

    async def _fail(self, writer: asyncio.StreamWriter, code: int) -> None:
        writer.write(
            bytes([0x05, code, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        )
        await writer.drain()

    async def _connect_via_proxy(
        self,
        proxy: Proxy,
        target_host: str,
        target_port: int,
        atype: int,
        address_bytes: bytes,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ) -> bool:
        if proxy.protocol.lower() == "socks5":
            return await self._connect_via_upstream_socks5(
                proxy, target_port, atype, address_bytes, client_reader, client_writer
            )
        if proxy.protocol.lower() == "socks4":
            return await self._connect_via_upstream_socks4(
                proxy,
                target_host,
                target_port,
                atype,
                address_bytes,
                client_reader,
                client_writer,
            )
        return await self._connect_via_upstream_http(
            proxy, target_host, target_port, client_reader, client_writer
        )

    async def _connect_via_upstream_socks5(
        self,
        proxy: Proxy,
        target_port: int,
        atype: int,
        address_bytes: bytes,
        client_reader,
        client_writer,
    ) -> bool:
        upstream_reader, upstream_writer = await asyncio.wait_for(
            asyncio.open_connection(proxy.ip, int(proxy.port)), timeout=TIMEOUT
        )
        upstream_writer.write(b"\x05\x01\x00")
        await upstream_writer.drain()
        response = await asyncio.wait_for(
            upstream_reader.readexactly(2), timeout=TIMEOUT
        )
        if response[1] == 0xFF:
            await self._fail(client_writer, 0x01)
            upstream_writer.close()
            return False

        request_buffer = bytearray(b"\x05\x01\x00")
        request_buffer.append(atype)
        request_buffer.extend(address_bytes)
        request_buffer.extend(struct.pack(">H", target_port))
        upstream_writer.write(request_buffer)
        await upstream_writer.drain()

        response = await asyncio.wait_for(
            upstream_reader.readexactly(4), timeout=TIMEOUT
        )
        if response[1] != 0x00:
            await self._fail(client_writer, 0x01)
            upstream_writer.close()
            return False

        if response[3] == 0x01:
            await upstream_reader.readexactly(4)
        elif response[3] == 0x03:
            length = await upstream_reader.readexactly(1)
            await upstream_reader.readexactly(length[0])
        elif response[3] == 0x04:
            await upstream_reader.readexactly(16)
        await upstream_reader.readexactly(2)

        client_writer.write(bytes([0x05, 0x00, 0x00, 0x01, 0, 0, 0, 0, 0, 0]))
        await client_writer.drain()
        await tunnel_bidirectional(
            client_reader,
            client_writer,
            upstream_reader,
            upstream_writer,
            "socks5_bytes_transferred",
        )
        return True

    async def _connect_via_upstream_socks4(
        self,
        proxy: Proxy,
        target_host: str,
        target_port: int,
        atype: int,
        address_bytes: bytes,
        client_reader,
        client_writer,
    ) -> bool:
        upstream_reader, upstream_writer = await asyncio.wait_for(
            asyncio.open_connection(proxy.ip, int(proxy.port)), timeout=TIMEOUT
        )
        request_buffer = bytearray(b"\x04\x01")
        request_buffer.extend(struct.pack(">H", target_port))
        if atype == 0x01:
            request_buffer.extend(address_bytes)
            request_buffer.extend(b"\x00")
        else:
            request_buffer.extend(b"\x00\x00\x00\x01\x00")
            request_buffer.extend(target_host.encode())
            request_buffer.extend(b"\x00")
        upstream_writer.write(request_buffer)
        await upstream_writer.drain()
        response = await asyncio.wait_for(
            upstream_reader.readexactly(8), timeout=TIMEOUT
        )
        if response[1] != 0x5A:
            await self._fail(client_writer, 0x01)
            upstream_writer.close()
            return False

        client_writer.write(bytes([0x05, 0x00, 0x00, 0x01, 0, 0, 0, 0, 0, 0]))
        await client_writer.drain()
        await tunnel_bidirectional(
            client_reader,
            client_writer,
            upstream_reader,
            upstream_writer,
            "socks5_bytes_transferred",
        )
        return True

    async def _connect_via_upstream_http(
        self,
        proxy: Proxy,
        target_host: str,
        target_port: int,
        client_reader,
        client_writer,
    ) -> bool:
        upstream_reader, upstream_writer = await asyncio.wait_for(
            asyncio.open_connection(proxy.ip, int(proxy.port)), timeout=TIMEOUT
        )
        upstream_writer.write(
            f"CONNECT {target_host}:{target_port} HTTP/1.1\r\nHost: {target_host}:{target_port}\r\n\r\n".encode()
        )
        await upstream_writer.drain()
        response = await asyncio.wait_for(upstream_reader.readline(), timeout=TIMEOUT)
        if b"200" not in response:
            await self._fail(client_writer, 0x01)
            upstream_writer.close()
            return False

        while True:
            line = await asyncio.wait_for(upstream_reader.readline(), timeout=TIMEOUT)
            if line in {b"\r\n", b"\n", b""}:
                break

        client_writer.write(bytes([0x05, 0x00, 0x00, 0x01, 0, 0, 0, 0, 0, 0]))
        await client_writer.drain()
        await tunnel_bidirectional(
            client_reader,
            client_writer,
            upstream_reader,
            upstream_writer,
            "socks5_bytes_transferred",
        )
        return True


class HTTPProxyServer:
    def __init__(self) -> None:
        self.logger = logging.getLogger("http-proxy")

    async def start(self, runtime=None) -> None:
        config = load_http_proxy_config()
        if not config.get("enabled", True):
            self.logger.info("HTTP 代理服务器已禁用")
            return
        host = str(config.get("host", HTTP_PROXY_HOST))
        port = int(config.get("port", HTTP_PROXY_PORT))
        server = await asyncio.start_server(self.handle_client, host, port)
        if runtime is not None:
            runtime.attach(asyncio.get_running_loop(), server)
        with state.lock:
            state.runtime["http_listen_host"] = host
            state.runtime["http_listen_port"] = port
        self.logger.info("HTTP/HTTPS 代理服务器启动：%s:%s", host, port)
        async with server:
            await server.serve_forever()

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        client_addr = writer.get_extra_info("peername")
        self.logger.info("HTTP 代理新连接：%s", client_addr)
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=TIMEOUT)
            if not request_line:
                return
            method, path, _ = (
                request_line.decode("utf-8", errors="ignore").strip().split(" ", 2)
            )
            headers = {}
            host = ""
            auth_header = ""
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=TIMEOUT)
                if line in {b"\r\n", b"\n", b""}:
                    break
                key, value = line.decode("utf-8", errors="ignore").split(":", 1)
                headers[key.strip().lower()] = value.strip()
                if key.strip().lower() == "host":
                    host = value.strip()
                if key.strip().lower() == "proxy-authorization":
                    auth_header = value.strip()

            proxy_config = load_http_proxy_config()
            if proxy_config.get("auth_enabled", False) and not self._auth_ok(
                auth_header, proxy_config
            ):
                writer.write(b"HTTP/1.1 407 Proxy Authentication Required\r\n\r\n")
                await writer.drain()
                return

            if method.upper() == "CONNECT":
                target_host, target_port = split_host_port(path or host, 443)
                success = await self._try_connect_tunnel(
                    target_host, target_port, reader, writer
                )
                if not success:
                    writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    await writer.drain()
                return

            target_host, target_port = self._resolve_http_target(path, host)
            success = await self._try_forward_http(
                method, path, headers, target_host, target_port, reader, writer
            )
            if not success:
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await writer.drain()
        except Exception as exc:
            self.logger.error("HTTP 代理错误：%s", exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def _auth_ok(self, auth_header: str, config: Dict) -> bool:
        if not auth_header:
            return False
        try:
            auth_type, encoded = auth_header.split(" ", 1)
            if auth_type.lower() != "basic":
                return False
            username, password = base64.b64decode(encoded).decode("utf-8").split(":", 1)
            expected_user = str(config.get("username", HTTP_PROXY_USER))
            expected_pass = str(config.get("password", HTTP_PROXY_PASS))
            return username == expected_user and password == expected_pass
        except Exception:
            return False

    def _list_candidates(self, mode: str) -> List[Proxy]:
        allowed = ["socks5", "socks4", "http", "https"]
        if mode == "connect":
            prefer = ["socks5", "socks4", "http", "https"]
        else:
            prefer = ["http", "https", "socks5", "socks4"]

        proxy = state.choose_proxy(
            allowed_protocols=allowed,
            prefer_protocols=prefer,
        )

        with state.lock:
            proxies = [item for item in state.working.values() if item.is_working]

        ordered = sorted(
            proxies,
            key=lambda item: (
                prefer.index(item.protocol.lower())
                if item.protocol.lower() in prefer
                else len(prefer),
                item.speed_ms if item.speed_ms is not None else float("inf"),
                item.address,
            ),
        )

        if proxy:
            for index, item in enumerate(ordered):
                if item.address == proxy.address:
                    ordered.insert(0, ordered.pop(index))
                    break
        return ordered

    async def _try_connect_tunnel(
        self,
        target_host: str,
        target_port: int,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ) -> bool:
        for proxy in self._list_candidates("connect")[:20]:
            try:
                success = await self._connect_tunnel(
                    proxy, target_host, target_port, client_reader, client_writer
                )
                if success:
                    state.set_current_proxy(proxy.address)
                    with state.lock:
                        state.stats["http_proxy_connections"] += 1
                        state.stats["http_proxy_requests"] += 1
                    return True
            except Exception as exc:
                self.logger.warning("CONNECT via %s 失败: %s", proxy.address, exc)
                continue
        return False

    async def _try_forward_http(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        target_host: str,
        target_port: int,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
    ) -> bool:
        for proxy in self._list_candidates("http")[:20]:
            try:
                success = await self._forward_http(
                    proxy,
                    method,
                    path,
                    headers,
                    target_host,
                    target_port,
                    client_reader,
                    client_writer,
                )
                if success:
                    state.set_current_proxy(proxy.address)
                    with state.lock:
                        state.stats["http_proxy_connections"] += 1
                        state.stats["http_proxy_requests"] += 1
                    return True
            except Exception as exc:
                self.logger.warning("HTTP 转发 via %s 失败: %s", proxy.address, exc)
                continue
        return False

    def _resolve_http_target(self, path: str, host: str) -> Tuple[str, int]:
        if host:
            return split_host_port(host, 80)
        if path.startswith("http://") or path.startswith("https://"):
            parsed = urlsplit(path)
            default_port = 443 if parsed.scheme == "https" else 80
            if parsed.hostname:
                return parsed.hostname, parsed.port or default_port
        return "", 80

    async def _connect_tunnel(
        self,
        proxy: Proxy,
        target_host: str,
        target_port: int,
        client_reader,
        client_writer,
    ) -> bool:
        if proxy.protocol.lower() == "socks5":
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(proxy.ip, int(proxy.port)), timeout=TIMEOUT
            )
            upstream_writer.write(b"\x05\x01\x00")
            await upstream_writer.drain()
            response = await asyncio.wait_for(
                upstream_reader.readexactly(2), timeout=TIMEOUT
            )
            if response[1] == 0xFF:
                client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await client_writer.drain()
                return False
            host_bytes = target_host.encode()
            request_buffer = bytearray(b"\x05\x01\x00\x03")
            request_buffer.append(len(host_bytes))
            request_buffer.extend(host_bytes)
            request_buffer.extend(struct.pack(">H", target_port))
            upstream_writer.write(request_buffer)
            await upstream_writer.drain()
            response = await asyncio.wait_for(
                upstream_reader.readexactly(4), timeout=TIMEOUT
            )
            if response[1] != 0x00:
                client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await client_writer.drain()
                return False
            if response[3] == 0x01:
                await upstream_reader.readexactly(4)
            elif response[3] == 0x03:
                length = await upstream_reader.readexactly(1)
                await upstream_reader.readexactly(length[0])
            elif response[3] == 0x04:
                await upstream_reader.readexactly(16)
            await upstream_reader.readexactly(2)
        elif proxy.protocol.lower() == "socks4":
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(proxy.ip, int(proxy.port)), timeout=TIMEOUT
            )
            request_buffer = bytearray(b"\x04\x01")
            request_buffer.extend(struct.pack(">H", target_port))
            request_buffer.extend(b"\x00\x00\x00\x01\x00")
            request_buffer.extend(target_host.encode())
            request_buffer.extend(b"\x00")
            upstream_writer.write(request_buffer)
            await upstream_writer.drain()
            response = await asyncio.wait_for(
                upstream_reader.readexactly(8), timeout=TIMEOUT
            )
            if response[1] != 0x5A:
                client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await client_writer.drain()
                return False
        else:
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(proxy.ip, int(proxy.port)), timeout=TIMEOUT
            )
            upstream_writer.write(
                f"CONNECT {target_host}:{target_port} HTTP/1.1\r\nHost: {target_host}:{target_port}\r\n\r\n".encode()
            )
            await upstream_writer.drain()
            response = await asyncio.wait_for(
                upstream_reader.readexactly(8), timeout=TIMEOUT
            )
            if b"200" not in response:
                client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await client_writer.drain()
                return False
            while True:
                line = await asyncio.wait_for(
                    upstream_reader.readline(), timeout=TIMEOUT
                )
                if line in {b"\r\n", b"\n", b""}:
                    break

        client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await client_writer.drain()
        await tunnel_bidirectional(
            client_reader,
            client_writer,
            upstream_reader,
            upstream_writer,
            "http_proxy_bytes",
        )
        return True

    async def _forward_http(
        self,
        proxy: Proxy,
        method: str,
        path: str,
        headers: Dict[str, str],
        target_host: str,
        target_port: int,
        client_reader,
        client_writer,
    ) -> bool:
        body = b""
        if headers.get("content-length"):
            body = await client_reader.read(int(headers.get("content-length", "0")))

        if not target_host:
            client_writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            await client_writer.drain()
            return False

        request_path = path or "/"
        if request_path.startswith("http://") or request_path.startswith("https://"):
            parsed = urlsplit(request_path)
            request_path = parsed.path or "/"
            if parsed.query:
                request_path = f"{request_path}?{parsed.query}"

        request_lines = [f"{method} {request_path} HTTP/1.1"]
        seen_host = False
        for key, value in headers.items():
            lower_key = key.lower()
            if lower_key in {
                "proxy-authorization",
                "proxy-connection",
                "connection",
                "keep-alive",
                "transfer-encoding",
                "upgrade",
            }:
                continue
            if lower_key == "host":
                seen_host = True
            request_lines.append(f"{key}: {value}")
        if not seen_host:
            request_lines.append(f"Host: {target_host}:{target_port}" if target_port not in {80, 443} else f"Host: {target_host}")
        request_lines.append("Connection: close")
        request_lines.append("")
        request_lines.append("")
        outbound_request = "\r\n".join(request_lines).encode() + body

        protocol = proxy.protocol.lower()
        if protocol in {"http", "https"}:
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(proxy.ip, int(proxy.port)), timeout=TIMEOUT
            )
            request_target = (
                path
                if path.startswith("http://") or path.startswith("https://")
                else f"http://{target_host}{request_path}"
            )
            request_lines = [f"{method} {request_target} HTTP/1.1"]
            for key, value in headers.items():
                lower_key = key.lower()
                if lower_key in {
                    "proxy-authorization",
                    "proxy-connection",
                    "connection",
                    "keep-alive",
                    "transfer-encoding",
                    "upgrade",
                }:
                    continue
                request_lines.append(f"{key}: {value}")
            request_lines.append("Connection: close")
            request_lines.append("")
            request_lines.append("")
            upstream_writer.write("\r\n".join(request_lines).encode() + body)
            await upstream_writer.drain()
        elif protocol == "socks5":
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(proxy.ip, int(proxy.port)), timeout=TIMEOUT
            )
            upstream_writer.write(b"\x05\x01\x00")
            await upstream_writer.drain()
            response = await asyncio.wait_for(upstream_reader.readexactly(2), timeout=TIMEOUT)
            if response[1] == 0xFF:
                return False
            host_bytes = target_host.encode()
            request_buffer = bytearray(b"\x05\x01\x00\x03")
            request_buffer.append(len(host_bytes))
            request_buffer.extend(host_bytes)
            request_buffer.extend(struct.pack(">H", target_port))
            upstream_writer.write(request_buffer)
            await upstream_writer.drain()
            response = await asyncio.wait_for(upstream_reader.readexactly(4), timeout=TIMEOUT)
            if response[1] != 0x00:
                return False
            if response[3] == 0x01:
                await upstream_reader.readexactly(4)
            elif response[3] == 0x03:
                length = await upstream_reader.readexactly(1)
                await upstream_reader.readexactly(length[0])
            elif response[3] == 0x04:
                await upstream_reader.readexactly(16)
            await upstream_reader.readexactly(2)
            upstream_writer.write(outbound_request)
            await upstream_writer.drain()
        elif protocol == "socks4":
            upstream_reader, upstream_writer = await asyncio.wait_for(
                asyncio.open_connection(proxy.ip, int(proxy.port)), timeout=TIMEOUT
            )
            request_buffer = bytearray(b"\x04\x01")
            request_buffer.extend(struct.pack(">H", target_port))
            request_buffer.extend(b"\x00\x00\x00\x01\x00")
            request_buffer.extend(target_host.encode())
            request_buffer.extend(b"\x00")
            upstream_writer.write(request_buffer)
            await upstream_writer.drain()
            response = await asyncio.wait_for(upstream_reader.readexactly(8), timeout=TIMEOUT)
            if response[1] != 0x5A:
                return False
            upstream_writer.write(outbound_request)
            await upstream_writer.drain()
        else:
            return False

        while True:
            chunk = await upstream_reader.read(4096)
            if not chunk:
                break
            client_writer.write(chunk)
            await client_writer.drain()
            with state.lock:
                state.stats["http_proxy_bytes"] = state.stats.get(
                    "http_proxy_bytes", 0
                ) + len(chunk)

        try:
            upstream_writer.close()
            await upstream_writer.wait_closed()
        except Exception:
            pass
        return True


def split_host_port(host: str, default_port: int) -> Tuple[str, int]:
    if ":" in host:
        name, port = host.rsplit(":", 1)
        return name, int(port)
    return host, default_port


app = Flask(
    __name__,
    template_folder=str(TEMPLATE_DIR),
    static_folder=str(BASE_DIR / "static"),
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "proxy-manager-secret-key")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/proxies/fetch", methods=["POST"])
def api_fetch_proxies():
    payload = request.json or {}
    proxy_type = str(payload.get("type", AUTO_FETCH_TYPE)).lower()
    country = str(payload.get("country", "")).upper()
    fetch_limit = int(
        payload.get("fetch_limit", load_runtime_config().get("fetch_limit", 50))
    )
    config = save_runtime_config(
        {
            "type": proxy_type,
            "protocol": proxy_type,
            "country": country,
            "fetch_limit": fetch_limit,
        }
    )
    count = refresh_proxy_pool(
        proxy_type,
        country,
        [] if country else config.get("fetch_countries", AUTO_FETCH_COUNTRIES),
        int(config.get("fetch_limit", 50)),
        subscription_urls=config.get("subscription_urls", []),
    )
    return jsonify(
        {"success": True, "count": count, "message": f"已获取 {count} 个代理"}
    )


@app.route("/api/proxies/test", methods=["POST"])
def api_test_proxies():
    payload = request.json or {}
    count = int(payload.get("count", TEST_COUNT))
    protocol = str(payload.get("protocol", "all"))
    country = str(payload.get("country", ""))
    results = asyncio.run(
        state.test_proxies(count=count, protocol=protocol, country=country)
    )
    return jsonify(
        {
            "success": True,
            "tested": count,
            "working": len(results),
            "results": [proxy.to_dict() for proxy in results],
        }
    )


@app.route("/api/proxies/test-one", methods=["POST"])
def api_test_one_proxy():
    payload = request.json or {}
    address = str(payload.get("address", "")).strip()
    if not address:
        return jsonify({"success": False, "message": "缺少代理地址"}), 400

    proxy = state.get_proxy_by_address(address)
    if not proxy:
        all_proxies = state.get_all_proxies()
        proxy_data = next((item for item in all_proxies if item.get("address") == address), None)
        if not proxy_data:
            return jsonify({"success": False, "message": "找不到该节点"}), 404
        proxy = Proxy(
            ip=str(proxy_data.get("ip", "")),
            port=str(proxy_data.get("port", "")),
            protocol=str(proxy_data.get("protocol", "http")),
            country=str(proxy_data.get("country", "")),
            anonymity=str(proxy_data.get("anonymity", "")),
            source=str(proxy_data.get("source", "")),
        )

    async def do_test() -> None:
        async with aiohttp.ClientSession() as session:
            await state._test_single_proxy(session, proxy)

    asyncio.run(do_test())
    return jsonify({"success": True, "proxy": proxy.to_dict()})


@app.route("/api/proxies", methods=["GET"])
def api_get_proxies():
    working_only = request.args.get("working", "false").lower() == "true"
    protocol = request.args.get("protocol", "").lower()
    country = request.args.get("country", "").upper()
    source = request.args.get("source", "").strip()
    status = request.args.get("status", "").lower()
    page = int(request.args.get("page", "1"))
    page_size = int(request.args.get("page_size", request.args.get("limit", "50")))
    sort_by = request.args.get("sort_by", "speed_ms")
    sort_order = request.args.get("sort_order", "asc")

    all_proxies = state.get_all_proxies()
    base = state.get_working_proxies(limit=100000) if working_only else all_proxies
    proxies, filtered_count, sources = filter_sort_paginate_proxies(
        base,
        protocol=protocol,
        country=country,
        source=source,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    return jsonify(
        {
            "success": True,
            "count": len(proxies),
            "filtered_count": filtered_count,
            "total_fetched": len(all_proxies),
            "page": page,
            "page_size": page_size,
            "total_pages": (filtered_count + page_size - 1) // page_size if page_size else 1,
            "sources": sources,
            "proxies": proxies,
        }
    )


@app.route("/api/stats", methods=["GET"])
def api_stats():
    stats = state.get_stats()
    if socks5_runtime is not None:
        stats["socks5_runtime"] = socks5_runtime.status()
    if http_runtime is not None:
        stats["http_runtime"] = http_runtime.status()
    return jsonify({"success": True, "stats": stats})


@app.route("/api/connection", methods=["GET"])
def api_connection():
    return jsonify({"success": True, "connection": state.get_connection_info()})


@app.route("/api/proxies/top", methods=["GET"])
def api_proxies_top():
    limit = int(request.args.get("limit", "10"))
    items = state.get_working_proxies(limit=1000)
    items = sorted(
        items,
        key=lambda proxy: proxy.get("speed_ms") if proxy.get("speed_ms") is not None else float("inf"),
    )[:limit]
    return jsonify({"success": True, "items": items, "count": len(items)})


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST":
        payload = request.json or {}
        payload["protocol"] = payload.get("protocol") or payload.get("type", "all")
        if "test_count" in payload:
            try:
                payload["test_count"] = max(
                    1, min(200, int(payload.get("test_count", TEST_COUNT)))
                )
            except Exception:
                payload["test_count"] = TEST_COUNT
        if "rotate_interval" in payload:
            try:
                payload["rotate_interval"] = max(
                    30, min(7200, int(payload.get("rotate_interval", 300)))
                )
            except Exception:
                payload["rotate_interval"] = 300
        config = save_runtime_config(payload)
        return jsonify({"success": True, "message": "配置已保存", "config": config})
    return jsonify({"success": True, "config": load_runtime_config()})


@app.route("/api/subscriptions/stats", methods=["GET"])
def api_subscriptions_stats():
    summary = summarize_subscription_nodes()
    return jsonify({"success": True, "stats": summary})


@app.route("/api/subscriptions", methods=["GET", "POST", "PUT", "DELETE"])
def api_subscriptions():
    subs = load_subscriptions()

    if request.method == "GET":
        return jsonify({"success": True, "subscriptions": subs})

    if request.method == "POST":
        payload = request.json or {}
        name = str(payload.get("name", "")).strip()
        source = str(payload.get("source", "remote")).strip() or "remote"
        interval = int(payload.get("interval", 60))
        raw_url = str(payload.get("url", "")).strip()
        parsed = urlsplit(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return jsonify({"success": False, "message": "订阅链接格式无效"}), 400
        if not name:
            name = raw_url
        if any(item.get("url") == raw_url for item in subs):
            return jsonify({"success": True, "message": "订阅已存在", "subscriptions": subs})
        subs.append({"name": name, "source": source, "interval": interval, "url": raw_url})
        new_config = save_subscriptions(subs)
        return jsonify({"success": True, "message": "订阅已添加", "subscriptions": new_config.get("subscriptions", [])})

    if request.method == "PUT":
        payload = request.json or {}
        original_url = str(payload.get("original_url", "")).strip()
        if not original_url:
            return jsonify({"success": False, "message": "缺少原始订阅链接"}), 400
        new_name = str(payload.get("name", "")).strip()
        new_source = str(payload.get("source", "remote")).strip() or "remote"
        new_interval = int(payload.get("interval", 60))
        new_url = str(payload.get("url", "")).strip()
        parsed = urlsplit(new_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return jsonify({"success": False, "message": "订阅链接格式无效"}), 400
        found = False
        for item in subs:
            if item.get("url") == original_url:
                item["name"] = new_name or new_url
                item["source"] = new_source
                item["interval"] = new_interval
                item["url"] = new_url
                found = True
                break
        if not found:
            return jsonify({"success": False, "message": "找不到该订阅"}), 404
        new_config = save_subscriptions(subs)
        return jsonify({"success": True, "message": "订阅已更新", "subscriptions": new_config.get("subscriptions", [])})

    target = str(request.args.get("url", "")).strip()
    if not target:
        return jsonify({"success": False, "message": "缺少订阅链接"}), 400
    new_subs = [item for item in subs if item.get("url") != target]
    new_config = save_subscriptions(new_subs)
    return jsonify({"success": True, "message": "订阅已移除", "subscriptions": new_config.get("subscriptions", [])})


@app.route("/api/countries", methods=["GET"])
def api_countries():
    current = {
        proxy.get("country", "")
        for proxy in state.get_all_proxies()
        if proxy.get("country")
    }
    common = {"US", "JP", "SG", "GB", "DE", "FR", "KR", "HK", "TW", "CN"}
    return jsonify({"success": True, "countries": sorted(current.union(common))})


@app.route("/api/favorites", methods=["GET", "POST", "DELETE"])
def api_favorites():
    if request.method == "GET":
        return jsonify({"success": True, "favorites": load_favorites()})
    if request.method == "POST":
        payload = request.json or {}
        address = str(payload.get("address", ""))
        if not address:
            return jsonify({"success": False, "message": "缺少代理地址"}), 400
        favorites = [
            item for item in load_favorites() if item.get("address") != address
        ]
        favorites.append(
            {
                "address": address,
                "protocol": payload.get("protocol", ""),
                "country": payload.get("country", ""),
                "latency": payload.get("latency"),
                "last_tested": payload.get("last_tested"),
            }
        )
        save_favorites(favorites)
        return jsonify({"success": True, "favorites": favorites})

    address = request.args.get("address", "")
    if not address:
        return jsonify({"success": False, "message": "缺少代理地址"}), 400
    favorites = [item for item in load_favorites() if item.get("address") != address]
    save_favorites(favorites)
    return jsonify({"success": True, "favorites": favorites})


@app.route("/api/preferred", methods=["POST"])
def api_preferred():
    payload = request.json or {}
    address = str(payload.get("address", ""))
    if not address:
        return jsonify({"success": False, "message": "缺少代理地址"}), 400
    proxy = state.set_current_proxy(address)
    if not proxy:
        return jsonify(
            {
                "success": False,
                "message": "该代理当前不可用，无法锁定，请先测速或选择可用代理",
            }
        ), 400
    config = save_runtime_config({"preferred_address": address})
    return jsonify(
        {
            "success": True,
            "preferred_address": config.get("preferred_address"),
            "proxy": proxy.to_dict() if proxy else None,
            "message": f"已锁定代理 {address}",
        }
    )


@app.route("/api/preferred", methods=["DELETE"])
def api_clear_preferred():
    config = save_runtime_config({"preferred_address": ""})
    return jsonify(
        {
            "success": True,
            "preferred_address": config.get("preferred_address", ""),
            "message": "已解除锁定代理",
        }
    )


@app.route("/api/connect", methods=["POST", "DELETE"])
def api_connect_proxy():
    if request.method == "DELETE":
        state.clear_current_proxy()
        return jsonify({"success": True, "message": "已断开当前代理"})

    payload = request.json or {}
    address = str(payload.get("address", "")).strip()

    if address:
        proxy = state.set_current_proxy(address)
        if not proxy:
            return jsonify(
                {"success": False, "message": "该代理当前不可用，无法连接"}
            ), 400
        return jsonify(
            {
                "success": True,
                "message": f"已连接代理 {address}",
                "proxy": proxy.to_dict(),
            }
        )

    config = load_runtime_config()
    preferred_address = str(config.get("preferred_address", "")).strip()
    if preferred_address:
        preferred_proxy = state.get_proxy_by_address(preferred_address)
        if preferred_proxy:
            proxy = state.set_current_proxy(preferred_address)
            return jsonify(
                {
                    "success": True,
                    "message": f"已连接锁定代理 {preferred_address}",
                    "proxy": proxy.to_dict() if proxy else None,
                }
            )

    proxy = state.choose_proxy(
        preferred_protocol=str(config.get("protocol", "all")),
        preferred_country=str(config.get("country", "")),
    )
    if not proxy:
        return jsonify({"success": False, "message": "当前没有可连接的可用代理"}), 400

    return jsonify(
        {
            "success": True,
            "message": f"已连接代理 {proxy.address}",
            "proxy": proxy.to_dict(),
        }
    )


@app.route("/api/socks5", methods=["GET"])
def api_socks5_info():
    config = load_socks5_config()
    with state.lock:
        return jsonify(
            {
                "success": True,
                "socks5": {
                    "enabled": bool(config.get("enabled", True)),
                    "host": str(config.get("host", SOCKS5_HOST)),
                    "port": int(config.get("port", SOCKS5_PORT)),
                    "auth_enabled": bool(config.get("auth_enabled", False)),
                    "username": config.get("username") if config.get("auth_enabled") else None,
                    "password": config.get("password") if config.get("auth_enabled") else None,
                    "connections": state.stats.get("socks5_connections", 0),
                    "bytes_transferred": state.stats.get("socks5_bytes_transferred", 0),
                },
            }
        )


@app.route("/api/http-proxy", methods=["GET"])
def api_http_proxy_info():
    config = load_http_proxy_config()
    with state.lock:
        return jsonify(
            {
                "success": True,
                "http_proxy": {
                    "enabled": bool(config.get("enabled", True)),
                    "host": str(config.get("host", HTTP_PROXY_HOST)),
                    "port": int(config.get("port", HTTP_PROXY_PORT)),
                    "auth_enabled": bool(config.get("auth_enabled", False)),
                    "username": config.get("username") if config.get("auth_enabled") else None,
                    "password": config.get("password") if config.get("auth_enabled") else None,
                    "connections": state.stats.get("http_proxy_connections", 0),
                    "requests_handled": state.stats.get("http_proxy_requests", 0),
                    "bytes_transferred": state.stats.get("http_proxy_bytes", 0),
                },
            }
        )


@app.route("/api/config/socks5", methods=["GET", "POST"])
def api_config_socks5():
    path = socks5_config_path()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if request.method == "POST":
        request_payload = request.json or {}
        payload = {
            "enabled": bool(request_payload.get("enabled", True)),
            "host": str(request_payload.get("host", SOCKS5_HOST)),
            "port": int(request_payload.get("port", SOCKS5_PORT)),
            "auth_enabled": bool(request_payload.get("auth_enabled", False)),
            "username": str(request_payload.get("username", SOCKS5_USER)),
            "password": str(request_payload.get("password", SOCKS5_PASS)),
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2)
        return jsonify(
            {
                "success": True,
                "message": "配置已保存，请重启 SOCKS5 服务使配置生效",
                "config": payload,
                "restart_required": True,
            }
        )

    return jsonify({"success": True, "config": load_socks5_config()})


@app.route("/api/config/http-proxy", methods=["GET", "POST"])
def api_config_http_proxy():
    path = http_proxy_config_path()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if request.method == "POST":
        request_payload = request.json or {}
        payload = {
            "enabled": bool(request_payload.get("enabled", True)),
            "host": str(request_payload.get("host", HTTP_PROXY_HOST)),
            "port": int(request_payload.get("port", HTTP_PROXY_PORT)),
            "auth_enabled": bool(request_payload.get("auth_enabled", False)),
            "username": str(request_payload.get("username", HTTP_PROXY_USER)),
            "password": str(request_payload.get("password", HTTP_PROXY_PASS)),
        }
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2)
        return jsonify(
            {
                "success": True,
                "message": "配置已保存，请重启 HTTP 代理服务使配置生效",
                "config": payload,
                "restart_required": True,
            }
        )

    return jsonify({"success": True, "config": load_http_proxy_config()})


@app.route("/api/restart/socks5", methods=["POST"])
def api_restart_socks5():
    global socks5_runtime
    if socks5_runtime is None:
        return jsonify({"success": False, "message": "SOCKS5 runtime 未初始化"}), 500
    result = socks5_runtime.restart()
    with state.lock:
        state.runtime["socks5_server_enabled"] = bool(load_socks5_config().get("enabled", True))
    return jsonify({"success": True, "message": "SOCKS5 服务已重启", "runtime": result})


@app.route("/api/restart/http-proxy", methods=["POST"])
def api_restart_http_proxy():
    global http_runtime
    if http_runtime is None:
        return jsonify({"success": False, "message": "HTTP runtime 未初始化"}), 500
    result = http_runtime.restart()
    with state.lock:
        state.runtime["http_proxy_server_enabled"] = bool(load_http_proxy_config().get("enabled", True))
    return jsonify({"success": True, "message": "HTTP 代理服务已重启", "runtime": result})


def start_services() -> None:
    global socks5_runtime, http_runtime
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    initial_refresh()

    threading.Thread(target=background_fetch_loop, daemon=True).start()
    threading.Thread(target=background_test_loop, daemon=True).start()
    threading.Thread(target=background_rotate_loop, daemon=True).start()

    socks5_config = load_socks5_config()
    http_proxy_config = load_http_proxy_config()

    socks5_runtime = ManagedAsyncServer("socks5", lambda runtime: SOCKS5Server())
    http_runtime = ManagedAsyncServer("http-proxy", lambda runtime: HTTPProxyServer())

    with state.lock:
        state.runtime["socks5_server_enabled"] = bool(socks5_config.get("enabled", True))
        state.runtime["http_proxy_server_enabled"] = bool(http_proxy_config.get("enabled", True))

    if socks5_config.get("enabled", True):
        socks5_runtime.start()
    if http_proxy_config.get("enabled", True):
        http_runtime.start()

    logger.info("启动 Proxy Manager Web 服务...")
    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    start_services()
