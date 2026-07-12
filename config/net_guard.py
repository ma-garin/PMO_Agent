"""外向きリクエスト先URLのSSRF対策(F-13 / CWE-918)。

内部/メタデータ等の危険なアドレスを拒否する。IPリテラルは直接判定し、
ホスト名はDNS解決してプライベートIPに向いていないか確認する。
解決に失敗した場合(オフライン等)は「不明」として許可し、正当な外部URLの
登録を妨げない(本ガードは多層防御であり、正規性の唯一の判定ではない)。
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# 明示的に拒否する内部向けホスト名/サフィックス
_BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}
_BLOCKED_SUFFIXES = (".localhost", ".internal", ".local")


def _ip_is_dangerous(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def is_safe_external_url(url: str) -> bool:
    """外向き通信先として安全(=内部アドレスでない)なら True。"""
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    if not host:
        return False

    lowered = host.lower()
    if lowered in _BLOCKED_HOSTS or lowered.endswith(_BLOCKED_SUFFIXES):
        return False

    # IPリテラルは直接判定(DNS不要)
    try:
        ip = ipaddress.ip_address(host)
        return not _ip_is_dangerous(ip)
    except ValueError:
        pass  # ホスト名 → 下でDNS解決

    # ホスト名を解決し、いずれかがプライベートIPなら拒否。解決失敗は許可(不明扱い)。
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if _ip_is_dangerous(ip):
            return False
    return True
