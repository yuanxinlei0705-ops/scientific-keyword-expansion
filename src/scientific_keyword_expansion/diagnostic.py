"""Fresh DNS and HTTPS probes for the academic metadata providers."""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from .verification import Crossref, HttpClient, OpenAlex, RequestFailure, classify_network_error


def _safe_proxy(value: str | None) -> str | None:
    if not value:
        return value
    parsed = urllib.parse.urlsplit(value if "://" in value else "http://" + value)
    if parsed.username or parsed.password:
        host = parsed.hostname or "[hidden]"
        return urllib.parse.urlunsplit((parsed.scheme, f"[redacted]@{host}:{parsed.port}" if parsed.port else f"[redacted]@{host}",
                                        parsed.path, "", ""))
    return value


def _windows_proxy() -> dict:
    if sys.platform != "win32":
        return {}
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as key:
            def value(name: str):
                try:
                    return winreg.QueryValueEx(key, name)[0]
                except FileNotFoundError:
                    return None
            return {"enabled": bool(value("ProxyEnable")), "server": _safe_proxy(value("ProxyServer")),
                    "auto_config_url": _safe_proxy(value("AutoConfigURL"))}
    except OSError as error:
        return {"error": str(error)}


def run_doctor(args) -> int:
    try:
        client = HttpClient(ttl_seconds=0, proxy_url=args.proxy_url, timeout=args.timeout,
                            retries=args.retries, min_interval=0)
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    effective = urllib.request.getproxies()
    report = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "python": sys.version.split()[0], "ssl_verification": "enabled",
              "proxy": {"explicit": _safe_proxy(client.proxy_url),
                        "environment": {name: _safe_proxy(os.environ.get(name)) for name in
                                        ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy")
                                        if name in os.environ},
                        "urllib_detected": {name: _safe_proxy(value) for name, value in effective.items()},
                        "windows_internet_settings": _windows_proxy()},
              "providers": {}}
    for provider, host in ((OpenAlex(), "api.openalex.org"), (Crossref(), "api.crossref.org")):
        result = {"dns": {}, "https": {}, "proxy_bypass": urllib.request.proxy_bypass(host)}
        try:
            addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            result["dns"] = {"status": "ok", "addresses": sorted({item[4][0] for item in addresses})}
        except OSError as error:
            result["dns"] = {"status": "failed", "category": classify_network_error(error), "error": str(error)}
        try:
            rows = provider.search("lithography", client, limit=1)
            result["https"] = {"status": "ok", "metadata_count": len(rows),
                               "sample": {"title": rows[0].get("title"), "doi": rows[0].get("doi"),
                                          "url": rows[0].get("url")} if rows else None}
        except (RequestFailure, OSError, ValueError, KeyError, TypeError) as error:
            result["https"] = {"status": "failed", "category": error.category if isinstance(error, RequestFailure) else
                               classify_network_error(error), "error": str(error)}
        report["providers"][provider.name] = result
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(item["https"]["status"] == "ok" for item in report["providers"].values()) else 1
