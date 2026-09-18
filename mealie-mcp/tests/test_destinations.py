from __future__ import annotations

import ipaddress

import pytest

from app.security.destinations import DestinationPolicy, DestinationRejected


def resolver_for(address: str):
    async def resolve(hostname: str, port: int):
        return {ipaddress.ip_address(address)}

    return resolve


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url,address",
    [
        ("https://127.0.0.1", "127.0.0.1"),
        ("https://localhost", "127.0.0.1"),
        ("https://[::1]", "::1"),
        ("https://metadata.example", "169.254.169.254"),
        ("https://private.example", "10.10.1.3"),
        ("https://private.example", "172.16.4.2"),
        ("https://private.example", "192.168.2.4"),
        ("https://carrier-nat.example", "100.64.0.8"),
        ("https://private.example", "fd00::10"),
    ],
)
async def test_saas_rejects_special_and_private_destinations(settings, url, address):
    policy = DestinationPolicy(settings, resolver_for(address))
    with pytest.raises(DestinationRejected):
        await policy.validate(url)


@pytest.mark.asyncio
async def test_hostname_is_rejected_if_any_dns_answer_is_private(settings):
    async def mixed(hostname: str, port: int):
        return {ipaddress.ip_address("8.8.8.8"), ipaddress.ip_address("10.0.0.4")}

    with pytest.raises(DestinationRejected):
        await DestinationPolicy(settings, mixed).validate("https://rebind.example")


@pytest.mark.asyncio
async def test_self_hosted_explicit_private_network_is_allowed(settings):
    local = settings.model_copy(
        update={
            "deployment_mode": "self_hosted",
            "mealie_allow_http": True,
            "mealie_private_networks": ["192.168.50.0/24"],
        }
    )
    value = await DestinationPolicy(local, resolver_for("192.168.50.8")).validate("http://mealie.home:9000")
    assert value.base_url == "http://mealie.home:9000"


@pytest.mark.asyncio
async def test_url_credentials_paths_queries_and_http_are_rejected(settings):
    policy = DestinationPolicy(settings, resolver_for("8.8.8.8"))
    for url in [
        "http://public.example",
        "https://user:pass@public.example",
        "https://public.example/api",
        "https://public.example?next=http://169.254.169.254",
    ]:
        with pytest.raises(DestinationRejected):
            await policy.validate(url)
