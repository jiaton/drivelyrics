import pytest

from app.feed.netguard import UnsafeTarget, allow_list, is_public, parse_target, pick_address

NONE = frozenset()


def test_only_https_unless_allow_listed():
    assert parse_target("https://ha.example.com/api/webhook/x?y=1", NONE).path == "/api/webhook/x?y=1"
    with pytest.raises(UnsafeTarget):
        parse_target("http://ha.example.com/hook", NONE)
    local = parse_target("http://192.168.50.10:8123/api/webhook/x", allow_list("192.168.50.10, other"))
    assert local.allowlisted and local.host_header == "192.168.50.10:8123"


@pytest.mark.parametrize("url", ["https://user:pw@example.com/", "https:///nohost", "ftp://example.com/", "https://example.com:99999/"])
def test_malformed_or_credentialed_urls_are_refused(url):
    with pytest.raises(UnsafeTarget):
        parse_target(url, NONE)


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.5", "192.168.1.1", "172.20.0.1", "169.254.169.254", "100.64.0.1", "0.0.0.0", "::1", "fe80::1", "fd00::1", "::ffff:10.0.0.1", "224.0.0.1"],
)
def test_private_and_special_addresses_are_not_public(address):
    assert not is_public(address)


def test_every_resolved_address_must_be_public():
    target = parse_target("https://hook.example.com/", NONE)
    assert pick_address(target, ["93.184.216.34"]) == "93.184.216.34"
    with pytest.raises(UnsafeTarget):
        pick_address(target, ["93.184.216.34", "10.0.0.1"])  # one private answer is enough to refuse
    with pytest.raises(UnsafeTarget):
        pick_address(target, [])


def test_allow_listed_host_may_resolve_privately():
    target = parse_target("https://ha.lan/hook", allow_list("ha.lan"))
    assert pick_address(target, ["192.168.50.10"]) == "192.168.50.10"
