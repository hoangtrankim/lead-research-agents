"""Website reader for the researcher agent, with protection against internal-network URLs."""

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; lead-research-agent/1.0)"
MAX_BYTES = 2_000_000
MAX_REDIRECTS = 3
INTERESTING = ("about", "product", "solution", "service", "pricing", "customer", "company")


class FetchError(Exception):
    pass


def normalize_url(url: str) -> str:
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise FetchError("Enter a valid website address, like https://example.com")
    return url


async def assert_public_host(host: str) -> None:
    """Refuse hosts that resolve to private, loopback or link-local addresses (SSRF guard)."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError(f"Could not find the website {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise FetchError("That address points to a private network and cannot be fetched.")


async def fetch_html(client: httpx.AsyncClient, url: str) -> tuple[str, str]:
    """Return (final_url, html). Redirects are followed manually so each hop is checked."""
    for _ in range(MAX_REDIRECTS + 1):
        await assert_public_host(urlparse(url).hostname or "")
        try:
            async with client.stream("GET", url, headers={"User-Agent": USER_AGENT}) as res:
                if res.is_redirect:
                    url = urljoin(url, res.headers.get("location", ""))
                    if urlparse(url).scheme not in ("http", "https"):
                        raise FetchError("The website redirected to an unsupported address.")
                    continue
                if res.status_code >= 400:
                    raise FetchError(f"The website returned an error ({res.status_code}).")
                if "html" not in res.headers.get("content-type", "html"):
                    raise FetchError("That address is not a web page.")
                chunks, size = [], 0
                async for chunk in res.aiter_bytes():
                    size += len(chunk)
                    chunks.append(chunk)
                    if size > MAX_BYTES:
                        break
                encoding = res.encoding or "utf-8"
                return url, b"".join(chunks).decode(encoding, errors="replace")
        except httpx.HTTPError as exc:
            raise FetchError(f"Could not load {url}") from exc
    raise FetchError("The website redirected too many times.")


def html_to_text(html: str) -> tuple[str, str]:
    """Return (title, readable text) with scripts, styles and navigation noise removed."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    for tag in soup(["script", "style", "noscript", "svg", "iframe", "form"]):
        tag.decompose()
    lines = [line.strip() for line in soup.get_text("\n").splitlines()]
    return title, "\n".join(line for line in lines if line)


def pick_links(html: str, base_url: str, limit: int) -> list[str]:
    """Choose same-site links that are likely to describe the company."""
    host = urlparse(base_url).hostname
    seen, picked = {base_url.rstrip("/")}, []
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        url = urljoin(base_url, a["href"]).split("#")[0].rstrip("/")
        parsed = urlparse(url)
        if parsed.hostname != host or parsed.scheme not in ("http", "https") or url in seen:
            continue
        haystack = (parsed.path + " " + a.get_text(" ", strip=True)).lower()
        if any(word in haystack for word in INTERESTING):
            seen.add(url)
            picked.append(url)
            if len(picked) >= limit:
                break
    return picked


async def read_site(url: str, *, max_pages: int, max_chars: int, timeout: float) -> list[dict]:
    """Fetch the homepage plus a few relevant pages. Returns [{url, title, text}]."""
    url = normalize_url(url)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        final_url, html = await fetch_html(client, url)
        targets = pick_links(html, final_url, max_pages - 1)
        results = await asyncio.gather(
            *(fetch_html(client, t) for t in targets), return_exceptions=True
        )
    pages = []
    for page_url, page_html in [(final_url, html)] + [r for r in results if not isinstance(r, BaseException)]:
        title, text = html_to_text(page_html)
        if text:
            pages.append({"url": page_url, "title": title, "text": text[:max_chars]})
    if not pages:
        raise FetchError("No readable text was found on that website.")
    return pages
