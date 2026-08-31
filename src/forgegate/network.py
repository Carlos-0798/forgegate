from __future__ import annotations

import ipaddress


def validated_loopback_host(host: str) -> str:
    normalized = host.strip().lower()
    if normalized == "localhost":
        return normalized
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError as exc:
        raise ValueError("host must be localhost or a loopback IP address") from exc
    if not address.is_loopback:
        raise ValueError("host must be localhost or a loopback IP address")
    return normalized


def is_loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    try:
        validated_loopback_host(host)
    except ValueError:
        return False
    return True


__all__ = ["is_loopback_host", "validated_loopback_host"]
