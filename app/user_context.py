from datetime import datetime, timezone
from typing import Any, Dict, Optional
import ipaddress
import re
import uuid

from fastapi import Request
from pydantic import BaseModel, Field


class UserContextDebugRequest(BaseModel):
    user: Optional[str] = None
    dashboard: Optional[str] = None
    session_id: Optional[str] = None
    event_id: Optional[str] = None
    event_type: Optional[str] = "debug_probe"
    client_context: Dict[str, Any] = Field(default_factory=dict)


def _safe_ip(raw_ip: str):
    if not raw_ip:
        return None
    try:
        return ipaddress.ip_address(raw_ip.strip())
    except ValueError:
        return None


def _extract_ip_candidates(request: Request) -> Dict[str, Any]:
    x_forwarded_for = request.headers.get("x-forwarded-for", "")
    forwarded_chain = [ip.strip() for ip in x_forwarded_for.split(",") if ip.strip()]

    x_real_ip = (request.headers.get("x-real-ip") or "").strip()
    remote_ip = request.client.host if request.client and request.client.host else ""

    selected_ip = "unknown"
    selected_source = "none"

    if forwarded_chain:
        selected_ip = forwarded_chain[0]
        selected_source = "x-forwarded-for:first"
    elif x_real_ip:
        selected_ip = x_real_ip
        selected_source = "x-real-ip"
    elif remote_ip:
        selected_ip = remote_ip
        selected_source = "request.client.host"

    return {
        "selected_ip": selected_ip,
        "selected_source": selected_source,
        "forwarded_chain": forwarded_chain,
        "x_real_ip": x_real_ip or None,
        "remote_ip": remote_ip or None,
    }


def _guess_network_for_ip(ip_obj) -> Dict[str, Any]:
    if isinstance(ip_obj, ipaddress.IPv4Address):
        ip_text = str(ip_obj)
        if ip_obj.is_loopback:
            network = ipaddress.ip_network(f"{ip_text}/8", strict=False)
            confidence = "high"
            reason = "ipv4 loopback range"
        elif ip_text.startswith("10."):
            network = ipaddress.ip_network(f"{ip_text}/8", strict=False)
            confidence = "high"
            reason = "rfc1918 10.0.0.0/8"
        elif ip_text.startswith("192.168."):
            network = ipaddress.ip_network(f"{ip_text}/16", strict=False)
            confidence = "high"
            reason = "rfc1918 192.168.0.0/16"
        elif ip_text.startswith("172.") and 16 <= int(ip_text.split(".")[1]) <= 31:
            network = ipaddress.ip_network(f"{ip_text}/12", strict=False)
            confidence = "high"
            reason = "rfc1918 172.16.0.0/12"
        else:
            network = ipaddress.ip_network(f"{ip_text}/24", strict=False)
            confidence = "low"
            reason = "public ipv4 coarse /24 approximation"

        return {
            "network_cidr": str(network),
            "network_ip": str(network.network_address),
            "broadcast_ip": str(network.broadcast_address),
            "guess_confidence": confidence,
            "guess_reason": reason,
        }

    network_v6 = ipaddress.ip_network(f"{str(ip_obj)}/64", strict=False)
    return {
        "network_cidr": str(network_v6),
        "network_ip": str(network_v6.network_address),
        "broadcast_ip": None,
        "guess_confidence": "medium",
        "guess_reason": "ipv6 /64 approximation",
    }


def _build_ip_details(raw_ip: str) -> Dict[str, Any]:
    ip_obj = _safe_ip(raw_ip)
    if not ip_obj:
        return {
            "raw": raw_ip,
            "valid": False,
            "family": "unknown",
            "is_private": None,
            "is_loopback": None,
            "is_global": None,
            "is_reserved": None,
            "is_multicast": None,
            "network_guess": None,
        }

    network_guess = _guess_network_for_ip(ip_obj)
    return {
        "raw": raw_ip,
        "valid": True,
        "family": "ipv6" if ip_obj.version == 6 else "ipv4",
        "compressed": ip_obj.compressed,
        "is_private": ip_obj.is_private,
        "is_loopback": ip_obj.is_loopback,
        "is_global": ip_obj.is_global,
        "is_reserved": ip_obj.is_reserved,
        "is_multicast": ip_obj.is_multicast,
        "network_guess": network_guess,
    }


def _parse_user_agent(user_agent: str) -> Dict[str, str]:
    ua = (user_agent or "").lower()

    browser_name = "unknown"
    browser_version = "unknown"
    os_name = "unknown"
    os_version = "unknown"
    browser_major = "unknown"
    device_type = "desktop"

    if "edg/" in ua:
        browser_name = "Edge"
        browser_version = user_agent.split("Edg/")[-1].split(" ")[0]
    elif "chrome/" in ua and "safari/" in ua:
        browser_name = "Chrome"
        browser_version = user_agent.split("Chrome/")[-1].split(" ")[0]
    elif "firefox/" in ua:
        browser_name = "Firefox"
        browser_version = user_agent.split("Firefox/")[-1].split(" ")[0]
    elif "safari/" in ua and "version/" in ua:
        browser_name = "Safari"
        browser_version = user_agent.split("Version/")[-1].split(" ")[0]

    if browser_version != "unknown":
        browser_major = browser_version.split(".")[0]

    if "windows nt" in ua:
        os_name = "Windows"
        match = re.search(r"windows nt ([0-9.]+)", ua)
        if match:
            os_version = match.group(1)
    elif "mac os x" in ua:
        os_name = "macOS"
        match = re.search(r"mac os x ([0-9_]+)", ua)
        if match:
            os_version = match.group(1).replace("_", ".")
    elif "android" in ua:
        os_name = "Android"
        match = re.search(r"android ([0-9.]+)", ua)
        if match:
            os_version = match.group(1)
    elif "iphone" in ua or "ipad" in ua or "ios" in ua:
        os_name = "iOS"
        match = re.search(r"os ([0-9_]+)", ua)
        if match:
            os_version = match.group(1).replace("_", ".")
    elif "linux" in ua:
        os_name = "Linux"

    if "mobile" in ua or "iphone" in ua or "android" in ua:
        device_type = "mobile"
    if "ipad" in ua or "tablet" in ua:
        device_type = "tablet"

    return {
        "browser_name": browser_name,
        "browser_version": browser_version,
        "browser_major": browser_major,
        "os_name": os_name,
        "os_version": os_version,
        "device_type": device_type,
    }


def _build_confidence(ip_details: Dict[str, Any], ip_source: str, ua_meta: Dict[str, str]) -> Dict[str, str]:
    if not ip_details.get("valid"):
        ip_confidence = "low"
    elif ip_source.startswith("x-forwarded-for"):
        ip_confidence = "medium"
    elif ip_source == "x-real-ip":
        ip_confidence = "medium"
    elif ip_source == "request.client.host":
        ip_confidence = "high"
    else:
        ip_confidence = "low"

    browser_confidence = "high" if ua_meta.get("browser_name") != "unknown" else "low"
    os_confidence = "high" if ua_meta.get("os_name") != "unknown" else "low"

    return {
        "ip_confidence": ip_confidence,
        "browser_confidence": browser_confidence,
        "os_confidence": os_confidence,
    }


def _extract_client_hints(request: Request) -> Dict[str, Optional[str]]:
    return {
        "sec_ch_ua": request.headers.get("sec-ch-ua"),
        "sec_ch_ua_platform": request.headers.get("sec-ch-ua-platform"),
        "sec_ch_ua_mobile": request.headers.get("sec-ch-ua-mobile"),
        "sec_ch_ua_full_version": request.headers.get("sec-ch-ua-full-version"),
    }


def build_server_context(request: Request) -> Dict[str, Any]:
    ip_candidates = _extract_ip_candidates(request)
    client_ip = ip_candidates["selected_ip"]
    ip_details = _build_ip_details(client_ip)
    user_agent = request.headers.get("user-agent", "")
    ua_meta = _parse_user_agent(user_agent)
    confidence = _build_confidence(ip_details, ip_candidates["selected_source"], ua_meta)
    client_hints = _extract_client_hints(request)

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "client_ip": client_ip,
        "client_ip_source": ip_candidates["selected_source"],
        "ip_details": ip_details,
        "network_ip": ip_details.get("network_guess", {}).get("network_ip") if ip_details.get("network_guess") else None,
        "network_cidr": ip_details.get("network_guess", {}).get("network_cidr") if ip_details.get("network_guess") else None,
        "forwarded_chain": ip_candidates["forwarded_chain"],
        "remote_ip": ip_candidates["remote_ip"],
        "user_agent": user_agent,
        "accept_language": request.headers.get("accept-language"),
        "origin": request.headers.get("origin"),
        "referer": request.headers.get("referer"),
        "forwarded_for": request.headers.get("x-forwarded-for"),
        "real_ip": request.headers.get("x-real-ip"),
        "client_hints": client_hints,
        **ua_meta,
        "confidence": confidence,
    }


def get_or_create_session_id(session_id: Optional[str]) -> str:
    return session_id or str(uuid.uuid4())


def get_or_create_event_id(event_id: Optional[str]) -> str:
    return event_id or str(uuid.uuid4())
