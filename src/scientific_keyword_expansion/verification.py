"""Optional academic metadata retrieval. Search hits are evidence candidates, not term proof."""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from .pipeline import normalize


def _abstract(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    positions = [(position, word) for word, offsets in index.items() for position in offsets]
    return " ".join(word for _, word in sorted(positions))


def _clean_html(value: str | None) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value or "")).split())


def _contains_phrase(corpus: str, phrase: str) -> bool:
    phrase = normalize(phrase)
    return bool(phrase) and f" {phrase} " in f" {corpus} "


class HttpClient:
    """Polite small-request client with versioned JSON cache and bounded backoff."""

    def __init__(self, cache_dir: str | Path | None = None, ttl_seconds: int = 86400,
                 timeout: float | None = None, retries: int | None = None, min_interval: float = 1.0,
                 proxy_url: str | None = None):
        self.cache_dir = Path(cache_dir or os.environ.get("SKE_CACHE_DIR", ".cache/scientific-keywords"))
        self.ttl_seconds = ttl_seconds
        self.timeout = float(timeout if timeout is not None else os.environ.get("SKE_HTTP_TIMEOUT", 12))
        self.retries = int(retries if retries is not None else os.environ.get("SKE_HTTP_RETRIES", 2))
        if not 0 < self.timeout <= 300 or not 0 <= self.retries <= 10:
            raise ValueError("timeout must be 0 < seconds <= 300 and retries must be 0..10")
        self.proxy_url = proxy_url if proxy_url is not None else os.environ.get("SKE_PROXY_URL")
        if self.proxy_url:
            parsed = urllib.parse.urlsplit(self.proxy_url)
            try:
                valid_port = parsed.port is None or 1 <= parsed.port <= 65535
            except ValueError:
                valid_port = False
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or not valid_port or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
                raise ValueError("proxy_url must be an HTTP(S) proxy URL such as http://host:port; SOCKS is unsupported by urllib")
            self.opener = urllib.request.build_opener(urllib.request.ProxyHandler(
                {"http": self.proxy_url, "https": self.proxy_url}))
        else:
            self.opener = None  # urlopen uses urllib's HTTP_PROXY/HTTPS_PROXY/NO_PROXY or Windows settings
        self.min_interval = min_interval
        self.last_request: dict[str, float] = {}
        self.last_retrieved_at: dict[str, float] = {}
        self.cache_errors: dict[str, str] = {}

    def get(self, provider: str, base_url: str, params: dict[str, Any], *, xml: bool = False,
            headers: dict[str, str] | None = None) -> Any:
        url = base_url + "?" + urllib.parse.urlencode(params)
        key = hashlib.sha256(url.encode()).hexdigest()
        path = self.cache_dir / f"{provider}-{key}.json"
        if path.exists():
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
                if cached["cache_version"] == 1 and time.time() - cached["retrieved_at"] < self.ttl_seconds:
                    self.last_retrieved_at[provider] = cached["retrieved_at"]
                    return cached["response"]
            except (ValueError, KeyError, OSError):
                pass
        for attempt in range(self.retries + 1):
            interval = max(self.min_interval, 3.0) if provider == "arxiv" else self.min_interval
            elapsed = time.monotonic() - self.last_request.get(provider, 0)
            if elapsed < interval:
                time.sleep(interval - elapsed)
            self.last_request[provider] = time.monotonic()
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "scientific-keyword-expansion/1.0 (research metadata)", **(headers or {})})
                opener = self.opener.open if self.opener else urllib.request.urlopen
                with opener(request, timeout=self.timeout) as response:
                    body = response.read(2_000_000)
                payload = body.decode("utf-8") if xml else json.loads(body)
                retrieved_at = time.time()
                self.last_retrieved_at[provider] = retrieved_at
                try:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    safe_params = {key: value for key, value in params.items() if key != "api_key"}
                    path.write_text(json.dumps({"query": safe_params, "provider": provider, "response": payload,
                                                "retrieved_at": retrieved_at, "cache_version": 1}, ensure_ascii=False), encoding="utf-8")
                except OSError as error:
                    self.cache_errors[provider] = str(error)
                return payload
            except urllib.error.HTTPError as error:
                retry_after = error.headers.get("Retry-After") if error.headers else None
                error.close()
                if error.code not in {429, 500, 502, 503, 504} or attempt == self.retries:
                    raise RequestFailure(provider, "http_status", f"HTTP {error.code}") from error
                try:
                    delay = min(30.0, max(1.0, float(retry_after))) if retry_after else min(2 ** attempt, 8)
                except ValueError:
                    delay = min(2 ** attempt, 8)
                time.sleep(delay)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
                if attempt == self.retries:
                    category = classify_network_error(error, proxy_used=bool(self.proxy_url or urllib.request.getproxies().get("https")))
                    raise RequestFailure(provider, category, str(error)) from error
                time.sleep(min(2 ** attempt, 4))
        raise AssertionError("unreachable")


class RequestFailure(RuntimeError):
    """A provider request failed; category is stable for diagnostics and logs."""

    def __init__(self, provider: str, category: str, detail: str):
        self.provider = provider
        self.category = category
        super().__init__(f"{provider} {category}: {detail}")


def classify_network_error(error: BaseException, *, proxy_used: bool = False) -> str:
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    if isinstance(reason, ssl.SSLCertVerificationError):
        return "tls_certificate"
    if isinstance(reason, ssl.SSLError):
        return "tls_error"
    if isinstance(reason, (json.JSONDecodeError, UnicodeDecodeError, ValueError)):
        return "response_decode"
    if isinstance(reason, socket.gaierror):
        return "proxy_dns" if proxy_used else "dns"
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(reason, ConnectionRefusedError):
        return "proxy_connection" if proxy_used else "connection_refused"
    if isinstance(reason, ConnectionResetError):
        return "connection_reset"
    return "network_error"


class Provider:
    name = "base"

    def search(self, phrase: str, client: HttpClient, limit: int = 5) -> list[dict[str, Any]]:
        raise NotImplementedError


class OpenAlex(Provider):
    name = "openalex"

    def search(self, phrase: str, client: HttpClient, limit: int = 5) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"search": phrase, "per_page": limit}
        if os.environ.get("OPENALEX_API_KEY"):
            params["api_key"] = os.environ["OPENALEX_API_KEY"]
        data = client.get(self.name, "https://api.openalex.org/works", params)
        return [{"title": row.get("display_name", ""), "authors": [a.get("author", {}).get("display_name", "") for a in row.get("authorships", [])],
                 "publication_year": row.get("publication_year"), "doi": row.get("doi"),
                 "source": self.name, "abstract": _abstract(row.get("abstract_inverted_index")),
                 "url": row.get("id", "")} for row in data.get("results", [])]


class SemanticScholar(Provider):
    name = "semantic_scholar"

    def search(self, phrase: str, client: HttpClient, limit: int = 5) -> list[dict[str, Any]]:
        headers = {"x-api-key": os.environ["SEMANTIC_SCHOLAR_API_KEY"]} if os.environ.get("SEMANTIC_SCHOLAR_API_KEY") else {}
        data = client.get(self.name, "https://api.semanticscholar.org/graph/v1/paper/search",
                          {"query": phrase, "limit": limit, "fields": "title,year,authors,abstract,url,externalIds"}, headers=headers)
        return [{"title": row.get("title", ""), "authors": [a.get("name", "") for a in row.get("authors", [])],
                 "publication_year": row.get("year"), "doi": (row.get("externalIds") or {}).get("DOI"),
                 "source": self.name, "abstract": row.get("abstract") or "", "url": row.get("url", "")}
                for row in data.get("data", [])]


class Crossref(Provider):
    name = "crossref"

    def search(self, phrase: str, client: HttpClient, limit: int = 5) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"query.title": phrase, "rows": limit}
        if os.environ.get("SKE_CONTACT_EMAIL"):
            params["mailto"] = os.environ["SKE_CONTACT_EMAIL"]
        data = client.get(self.name, "https://api.crossref.org/works", params)
        result = []
        for row in data.get("message", {}).get("items", []):
            parts = (row.get("published") or row.get("created") or {}).get("date-parts", [[]])
            result.append({"title": (row.get("title") or [""])[0],
                           "authors": [" ".join(filter(None, [a.get("given"), a.get("family")])) for a in row.get("author", [])],
                           "publication_year": parts[0][0] if parts and parts[0] else None,
                           "doi": row.get("DOI"), "source": self.name,
                           "abstract": _clean_html(row.get("abstract")), "url": row.get("URL", "")})
        return result


class Arxiv(Provider):
    name = "arxiv"

    def search(self, phrase: str, client: HttpClient, limit: int = 5) -> list[dict[str, Any]]:
        data = client.get(self.name, "https://export.arxiv.org/api/query",
                          {"search_query": f'all:"{phrase}"', "start": 0, "max_results": limit}, xml=True)
        root = ET.fromstring(data)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        result = []
        for entry in root.findall("a:entry", ns):
            published = entry.findtext("a:published", "", ns)
            result.append({"title": " ".join(entry.findtext("a:title", "", ns).split()),
                           "authors": [node.findtext("a:name", "", ns) for node in entry.findall("a:author", ns)],
                           "publication_year": int(published[:4]) if published[:4].isdigit() else None,
                           "doi": None, "source": self.name,
                           "abstract": " ".join(entry.findtext("a:summary", "", ns).split()),
                           "url": entry.findtext("a:id", "", ns)})
        return result


class Verifier:
    def __init__(self, providers: list[Provider] | None = None, client: HttpClient | None = None):
        self.providers = providers if providers is not None else [OpenAlex(), SemanticScholar(), Crossref(), Arxiv()]
        self.client = client or HttpClient()
        self.last_attempts: list[dict[str, str]] = []

    def verify(self, keyword: str, synonyms: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
        evidence: list[dict[str, Any]] = []
        errors: list[str] = []
        doi_indices: dict[str, int] = {}
        fallback_indices: dict[tuple[str, Any, str], int] = {}
        self.last_attempts = []
        for provider in self.providers:
            try:
                rows = provider.search(keyword, self.client)
            except Exception as error:
                errors.append(str(error))
                self.last_attempts.append({"provider": provider.name, "status": "failed", "error": str(error)})
                continue
            self.last_attempts.append({"provider": provider.name, "status": "success", "error": ""})
            cache_error = getattr(self.client, "cache_errors", {}).pop(provider.name, None)
            if cache_error:
                errors.append(f"{provider.name} cache write failed: {cache_error}")
            for row in rows:
                title_text = normalize(row.get("title", ""))
                abstract_text = normalize(row.get("abstract", ""))
                exact_title = _contains_phrase(title_text, keyword)
                exact_abstract = _contains_phrase(abstract_text, keyword)
                alias_title = any(_contains_phrase(title_text, term) for term in synonyms if len(normalize(term)) >= 3)
                alias_abstract = any(_contains_phrase(abstract_text, term) for term in synonyms if len(normalize(term)) >= 3)
                exact = exact_title or exact_abstract
                alias = alias_title or alias_abstract
                kind = "exact_phrase" if exact else "synonym" if alias else "related_topic"
                doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", (row.get("doi") or "").casefold()).strip()
                title = normalize(row.get("title", ""))
                if not title:
                    continue
                field = "title" if exact_title or alias_title else "abstract" if exact_abstract or alias_abstract else "search_result_only"
                retrieved = getattr(self.client, "last_retrieved_at", {}).get(provider.name)
                item = {**row, "matched_keyword": keyword, "match_type": kind,
                        "matched_field": field,
                        "sources": [provider.name], "context_assessment": "not_assessed",
                        "relevance_reason": "Phrase matched in metadata; target research context has not been reviewed." if kind != "related_topic" else
                                            "Returned by the provider search; no phrase match was found in sampled title or abstract.",
                        "retrieved_at": datetime.fromtimestamp(retrieved, timezone.utc).isoformat() if retrieved else datetime.now(timezone.utc).isoformat()}
                existing = doi_indices.get(doi) if doi else None
                author = normalize((row.get("authors") or [""])[0])
                fallback = (title, row.get("publication_year"), author)
                if existing is None:
                    candidate_index = fallback_indices.get(fallback)
                    if candidate_index is not None:
                        prior_doi = evidence[candidate_index].get("doi")
                        if not doi or not prior_doi:
                            existing = candidate_index
                if existing is not None:
                    ranking = {"related_topic": 0, "synonym": 1, "exact_phrase": 2}
                    sources = list(dict.fromkeys([*evidence[existing]["sources"], provider.name]))
                    if ranking[kind] > ranking[evidence[existing]["match_type"]]:
                        item["doi"] = item.get("doi") or evidence[existing].get("doi")
                        evidence[existing] = item
                    evidence[existing]["sources"] = sources
                    if doi:
                        doi_indices[doi] = existing
                    continue
                position = len(evidence)
                evidence.append(item)
                if doi:
                    doi_indices[doi] = position
                fallback_indices[fallback] = position
        return evidence, errors
