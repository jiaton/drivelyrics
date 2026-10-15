import hashlib
import hmac

import httpx

from app.feed.adapter import HttpWebhookSender


def resolver(*addresses):
    async def resolve(host, port):
        return list(addresses)

    return resolve


async def test_delivers_to_the_checked_address_with_host_and_signature():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["host"] = request.headers["host"]
        seen["sni"] = request.extensions.get("sni_hostname")
        seen["headers"] = request.headers
        seen["body"] = request.content
        return httpx.Response(200)

    sender = HttpWebhookSender(resolver("93.184.216.34"), httpx.MockTransport(handler))
    result = await sender.deliver("https://hook.example.com/api/webhook/abc", "s3cret", b'{"type":"fetch"}', "fetch")
    assert result.ok and result.detail == "HTTP 200"
    assert seen["url"] == "https://93.184.216.34/api/webhook/abc"
    assert seen["host"] == "hook.example.com" and seen["sni"] == "hook.example.com"
    ts = seen["headers"]["x-drivelyrics-timestamp"]
    expected = "sha256=" + hmac.new(b"s3cret", ts.encode() + b"." + seen["body"], hashlib.sha256).hexdigest()
    assert seen["headers"]["x-drivelyrics-signature"] == expected
    assert seen["headers"]["x-drivelyrics-event"] == "fetch"


async def test_private_targets_are_refused_without_sending():
    calls = []
    sender = HttpWebhookSender(resolver("10.0.0.7"), httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(200)))
    result = await sender.deliver("https://sneaky.example.com/", "s", b"{}", "fetch")
    assert not result.ok and "public" in result.detail
    assert calls == []
    assert await sender.check("https://sneaky.example.com/") is not None


async def test_redirects_are_not_followed_and_errors_are_results():
    sender = HttpWebhookSender(resolver("93.184.216.34"), httpx.MockTransport(lambda r: httpx.Response(302, headers={"location": "http://10.0.0.1/"})))
    result = await sender.deliver("https://hook.example.com/", "s", b"{}", "fetch")
    assert (result.ok, result.detail) == (False, "HTTP 302")

    def boom(request):
        raise httpx.ConnectTimeout("slow")

    result = await HttpWebhookSender(resolver("93.184.216.34"), httpx.MockTransport(boom)).deliver("https://hook.example.com/", "s", b"{}", "fetch")
    assert (result.ok, result.detail) == (False, "ConnectTimeout")
