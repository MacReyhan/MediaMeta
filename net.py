"""HTTP transport with a DNS-over-HTTPS fallback.

Some ISPs poison `api.themoviedb.org` (and friends) by returning a black-hole
IP from the local resolver, while the real CloudFront endpoints are fine. When
a direct request fails we resolve the host through Cloudflare/Google DoH and
retry against the real IP, keeping SNI and certificate validation intact.
"""

from __future__ import annotations

import http.client
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request

DOH_ENDPOINTS = (
    "https://cloudflare-dns.com/dns-query?name={host}&type=A",
    "https://dns.google/resolve?name={host}&type=A",
)

_doh_cache: dict[str, str] = {}
_pin_cache: dict[str, str] = {}
_poisoned: set[str] = set()
_probed: set[str] = set()
_bad_hosts: set[str] = set()

# Hosts that some ISPs reset at the TLS layer. The first host is the canonical
# one; the second is the same pull zone under its own name, which usually works.
FALLBACK_HOSTS = {
    "image.tmdb.org": "tmdb-image-prod.b-cdn.net",
}


def _reachable(host: str, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, 443), timeout=timeout):
            return True
    except OSError:
        return False


class NetError(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection that dials a specific IP but validates the real host."""

    def __init__(self, host: str, ip: str, timeout: float, context: ssl.SSLContext):
        super().__init__(host, 443, timeout=timeout, context=context)
        self._ip = ip

    def connect(self) -> None:  # type: ignore[override]
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _plain(url: str, headers: dict, timeout: float) -> tuple[int, bytes, dict]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(), _lower(resp.headers)
    except urllib.error.HTTPError as exc:  # non-2xx is data, not a transport failure
        return exc.code, exc.read(), _lower(exc.headers or {})


def _lower(headers) -> dict:
    return {str(k).lower(): v for k, v in dict(headers).items()}


def _pinned(url: str, host: str, ip: str, headers: dict, timeout: float) -> tuple[int, bytes, dict]:
    parts = urllib.parse.urlsplit(url)
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    context = ssl.create_default_context()
    conn = _PinnedHTTPSConnection(host, ip, timeout, context)
    try:
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
        return resp.status, resp.read(), _lower(resp.getheaders())
    finally:
        conn.close()


def _doh(host: str) -> str | None:
    if host in _doh_cache:
        return _doh_cache[host]
    for template in DOH_ENDPOINTS:
        url = template.format(host=host)
        try:
            status, body, _ = _plain(url, {"Accept": "application/dns-json"}, 10)
            if status != 200:
                continue
            payload = json.loads(body.decode("utf-8"))
            for answer in payload.get("Answer") or []:
                if answer.get("type") == 1 and answer.get("data"):
                    _doh_cache[host] = answer["data"]
                    return answer["data"]
        except Exception:
            continue
    return None


def fetch(url: str, headers: dict | None = None, timeout: float = 30) -> tuple[int, bytes, dict]:
    """GET a URL. Returns (status, body, headers). Raises NetError on failure."""
    headers = dict(headers or {})
    headers.setdefault("Accept-Encoding", "identity")
    host = urllib.parse.urlparse(url).hostname or ""

    if host in _bad_hosts and host in FALLBACK_HOSTS:
        alt = FALLBACK_HOSTS[host]
        return _fetch_host(_swap_host(url, host, alt), alt, headers, timeout)

    try:
        return _fetch_host(url, host, headers, timeout)
    except NetError:
        alt = FALLBACK_HOSTS.get(host)
        if not alt:
            raise
        _bad_hosts.add(host)
        return _fetch_host(_swap_host(url, host, alt), alt, headers, timeout)


def _swap_host(url: str, host: str, alt: str) -> str:
    return url.replace(f"//{host}", f"//{alt}", 1)


def _fetch_host(url: str, host: str, headers: dict, timeout: float) -> tuple[int, bytes, dict]:
    # Probe once per host: a poisoned resolver hands back an IP that silently
    # black-holes, which would otherwise cost a full request timeout.
    if host not in _probed:
        _probed.add(host)
        if not _reachable(host):
            ip = _doh(host)
            if ip:
                _pin_cache[host] = ip
                _poisoned.add(host)

    pinned = _pin_cache.get(host)
    if pinned:
        try:
            return _pinned(url, host, pinned, headers, timeout)
        except Exception:
            _pin_cache.pop(host, None)

    try:
        return _plain(url, headers, timeout)
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, ssl.SSLError, OSError) as first:
        ip = _doh(host)
        if not ip:
            raise NetError(f"network unreachable: {first}") from first
        _pin_cache[host] = ip
        _poisoned.add(host)
        try:
            return _pinned(url, host, ip, headers, timeout)
        except Exception as second:
            raise NetError(f"network unreachable: {second}") from second


def is_poisoned(host: str) -> bool:
    return host in _poisoned
