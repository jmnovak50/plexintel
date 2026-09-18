from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from app.config import Settings


class DestinationRejected(ValueError):
    pass


Resolver = Callable[[str, int], Awaitable[set[ipaddress.IPv4Address | ipaddress.IPv6Address]]]

_METADATA_HOSTS = frozenset({"metadata", "metadata.google.internal"})
_CATEGORICALLY_FORBIDDEN_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        "169.254.0.0/16",  # IPv4 link-local, including AWS/GCP/Azure metadata
        "fe80::/10",  # IPv6 link-local
        "fd00:ec2::254/128",  # AWS IMDS IPv6
        "fd20:ce::254/128",  # Google Cloud metadata IPv6
        "100.100.100.200/32",  # Alibaba Cloud metadata
        "168.63.129.16/32",  # Azure platform virtual IP/WireServer
    )
)


@dataclass(frozen=True)
class ValidatedDestination:
    base_url: str
    hostname: str
    port: int
    addresses: frozenset[ipaddress.IPv4Address | ipaddress.IPv6Address]


class DestinationPolicy:
    def __init__(self, settings: Settings, resolver: Resolver | None = None) -> None:
        self.settings = settings
        self._resolver = resolver or _resolve
        self._private_networks = [
            ipaddress.ip_network(value, strict=False) for value in settings.mealie_private_networks
        ]
        self._allowed_hosts = {value.lower().rstrip(".") for value in settings.mealie_allowed_hosts}

    async def validate(self, value: str) -> ValidatedDestination:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"}:
            raise DestinationRejected("Mealie URL must use http or https")
        if parsed.scheme == "http" and (
            self.settings.deployment_mode == "saas" or not self.settings.mealie_allow_http
        ):
            raise DestinationRejected("Mealie URL must use https")
        if parsed.username or parsed.password:
            raise DestinationRejected("Mealie URL must not contain credentials")
        if not parsed.hostname or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
            raise DestinationRejected("Mealie URL must be an origin without path, query, or fragment")
        hostname = parsed.hostname.lower().rstrip(".")
        if hostname in _METADATA_HOSTS:
            raise DestinationRejected("Mealie destination is a cloud metadata endpoint")
        if hostname == "localhost" and hostname not in self._allowed_hosts:
            raise DestinationRejected("localhost is not an allowed Mealie destination")
        try:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError as exc:
            raise DestinationRejected("Mealie URL has an invalid port") from exc
        addresses = await self._resolver(hostname, port)
        if not addresses:
            raise DestinationRejected("Mealie hostname did not resolve")
        for address in addresses:
            if self._forbidden(address, hostname):
                raise DestinationRejected("Mealie destination resolves to a forbidden address")
        netloc = f"[{hostname}]" if ":" in hostname else hostname
        default_port = 443 if parsed.scheme == "https" else 80
        if port != default_port:
            netloc += f":{port}"
        return ValidatedDestination(
            base_url=urlunsplit((parsed.scheme, netloc, "", "", "")),
            hostname=hostname,
            port=port,
            addresses=frozenset(addresses),
        )

    def _forbidden(self, address: ipaddress.IPv4Address | ipaddress.IPv6Address, hostname: str) -> bool:
        effective_address = (
            address.ipv4_mapped
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None
            else address
        )
        if any(
            effective_address.version == network.version and effective_address in network
            for network in _CATEGORICALLY_FORBIDDEN_NETWORKS
        ):
            return True
        if self.settings.deployment_mode == "saas":
            return not effective_address.is_global
        if (
            effective_address.is_unspecified
            or effective_address.is_multicast
            or effective_address.is_reserved
        ):
            return True
        if hostname in self._allowed_hosts:
            return False
        if effective_address.is_loopback or not effective_address.is_global:
            return not any(
                effective_address.version == network.version and effective_address in network
                for network in self._private_networks
            )
        return False


async def _resolve(hostname: str, port: int) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        literal = ipaddress.ip_address(hostname)
        return {literal}
    except ValueError:
        pass
    loop = asyncio.get_running_loop()
    try:
        results = await loop.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise DestinationRejected("Mealie hostname could not be resolved") from exc
    return {ipaddress.ip_address(item[4][0]) for item in results}
