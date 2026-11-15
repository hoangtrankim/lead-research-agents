import asyncio

import httpx
import pytest

from app import web

HTML = """<html><head><title>Acme Robots</title><style>p{}</style></head><body>
<nav><a href="/about">About us</a><a href="/blog/post">Blog</a><a href="https://other.test/about">Other</a>
<a href="/pricing#plans">Pricing</a><a href="/about">About again</a></nav>
<script>alert(1)</script><p>We build   robots.</p><p>For factories.</p></body></html>"""


def test_normalize_url():
    assert web.normalize_url(" acme.test ") == "https://acme.test"
    for bad in ["ftp://acme.test", "file:///etc/passwd", "https://"]:
        with pytest.raises(web.FetchError):
            web.normalize_url(bad)


def test_html_to_text_strips_noise():
    title, text = web.html_to_text(HTML)
    assert title == "Acme Robots"
    assert "alert" not in text and "p{}" not in text
    assert "We build   robots." in text and "For factories." in text


def test_pick_links_same_site_relevant_and_unique():
    assert web.pick_links(HTML, "https://acme.test/", 5) == ["https://acme.test/about", "https://acme.test/pricing"]
    assert web.pick_links(HTML, "https://acme.test/", 1) == ["https://acme.test/about"]


@pytest.mark.parametrize("host", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "::1", "192.168.1.1"])
def test_private_hosts_are_refused(host):
    with pytest.raises(web.FetchError):
        asyncio.run(web.assert_public_host(host))


def test_public_ip_is_allowed():
    asyncio.run(web.assert_public_host("8.8.8.8"))


def test_redirect_to_private_address_is_blocked():
    def handler(request):
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data"})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await web.fetch_html(client, "http://8.8.8.8/")

    with pytest.raises(web.FetchError, match="private network"):
        asyncio.run(go())


def test_fetch_html_returns_page():
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=HTML)

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await web.fetch_html(client, "http://8.8.8.8/")

    url, html = asyncio.run(go())
    assert url == "http://8.8.8.8/" and "Acme Robots" in html
