from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.parse
from collections import Counter
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from hashlib import md5
from pathlib import Path
from typing import Any, Iterable, Optional

import requests
import trafilatura
from cachetools import TTLCache
from duckduckgo_search import DDGS
from mcp.server.fastmcp import FastMCP
from rapidfuzz import fuzz

LOGGER = logging.getLogger("search_mcp")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    stream=sys.stderr,
)

APP_NAME = "search-mcp"
APP_VERSION = "1.0.0"
DEFAULT_TIMEOUT = float(os.getenv("SEARCH_TIMEOUT_SECONDS", "12"))
DEFAULT_MAX_RESULTS = int(os.getenv("SEARCH_DEFAULT_MAX_RESULTS", "6"))
DEFAULT_FETCH_MAX_CHUNKS = int(os.getenv("SEARCH_FETCH_MAX_CHUNKS", "5"))
DEFAULT_FETCH_MAX_CHARS = int(os.getenv("SEARCH_FETCH_MAX_CHARS", "1800"))
CACHE_TTL_SECONDS = int(os.getenv("SEARCH_CACHE_TTL_SECONDS", "1800"))
USER_AGENT = os.getenv(
    "SEARCH_USER_AGENT",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
)

BLOCKLIST_PATTERNS = [
    r"/login",
    r"/signin",
    r"/signup",
    r"/register",
    r"/account",
    r"/search\?",
    r"/tag/",
    r"/tags/",
    r"/category/",
    r"/categories/",
    r"/archive",
    r"/feed",
    r"/privacy",
    r"/terms",
]

LOW_QUALITY_DOMAINS = {
    "pinterest.com",
    "facebook.com",
    "m.facebook.com",
    "instagram.com",
    "tiktok.com",
    "quora.com",
}

DOMAIN_WEIGHT_DEFAULTS = {
    "docs.anthropic.com": 1.0,
    "modelcontextprotocol.io": 0.98,
    "github.com": 0.88,
    "kingdee.com": 0.95,
    "kdcloud.com": 0.95,
    "developer.mozilla.org": 0.95,
    "python.org": 0.94,
}

STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "for", "on", "with", "and", "or", "is", "are", "be", "by",
    "怎么", "如何", "以及", "一个", "这个", "那个", "是否", "可以", "使用", "通过", "相关", "问题",
    "what", "how", "when", "where", "which", "who", "why",
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})
SEARCH_CACHE: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=256, ttl=CACHE_TTL_SECONDS)
FETCH_CACHE: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=256, ttl=CACHE_TTL_SECONDS)
LOCAL_DOC_CACHE: TTLCache[str, list[dict[str, Any]]] = TTLCache(maxsize=8, ttl=300)


def _safe_log(message: str, *args: Any) -> None:
    LOGGER.info(message, *args)


def env_list(name: str) -> list[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    source: str
    domain: str
    score: float = 0.0
    rank_signals: dict[str, float] = field(default_factory=dict)
    published: Optional[str] = None
    query_variant: Optional[str] = None

    def compact(self, include_signals: bool = False) -> dict[str, Any]:
        data = {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "domain": self.domain,
            "score": round(self.score, 4),
        }
        if self.published:
            data["published"] = self.published
        if include_signals:
            data["rank_signals"] = {k: round(v, 4) for k, v in self.rank_signals.items()}
        return data


@dataclass
class SearchConfig:
    timeout_seconds: float = DEFAULT_TIMEOUT
    default_max_results: int = DEFAULT_MAX_RESULTS
    default_fetch_max_chunks: int = DEFAULT_FETCH_MAX_CHUNKS
    default_fetch_max_chars: int = DEFAULT_FETCH_MAX_CHARS
    prefer_domains: list[str] = field(default_factory=lambda: env_list("SEARCH_PREFER_DOMAINS"))
    block_domains: list[str] = field(default_factory=lambda: env_list("SEARCH_BLOCK_DOMAINS"))
    local_docs_dir: Optional[str] = os.getenv("SEARCH_LOCAL_DOCS_DIR") or None
    use_local_docs: bool = os.getenv("SEARCH_ENABLE_LOCAL_DOCS", "false").lower() in {"1", "true", "yes"}
    searxng_url: Optional[str] = os.getenv("SEARCH_SEARXNG_URL") or None
    use_searxng: bool = os.getenv("SEARCH_ENABLE_SEARXNG", "false").lower() in {"1", "true", "yes"}
    domain_weights: dict[str, float] = field(default_factory=lambda: dict(DOMAIN_WEIGHT_DEFAULTS))


CONFIG = SearchConfig()


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


@lru_cache(maxsize=2048)
def normalize_for_key(text: str) -> str:
    text = (text or "").strip().lower()
    return normalize_space(text)


def trim_text(text: str, max_chars: int) -> str:
    text = normalize_space(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def parse_csv_or_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [normalize_space(x) for x in value if normalize_space(x)]
    return [normalize_space(x) for x in value.split(",") if normalize_space(x)]


@lru_cache(maxsize=4096)
def canonicalize_url(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception:
        return url
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered_query = [(k, v) for k, v in query if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid", "spm"}]
    clean = parsed._replace(
        query=urllib.parse.urlencode(filtered_query, doseq=True),
        fragment="",
    )
    path = clean.path.rstrip("/") or "/"
    clean = clean._replace(path=path)
    return urllib.parse.urlunsplit(clean)


@lru_cache(maxsize=4096)
def extract_domain(url: str) -> str:
    try:
        host = urllib.parse.urlsplit(url).netloc.lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def tokenize(text: str) -> list[str]:
    text = normalize_for_key(text)
    if not text:
        return []
    ascii_tokens = re.findall(r"[a-z0-9_\-.]{2,}", text)
    cjk_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    tokens = list(ascii_tokens)
    for chunk in cjk_chunks:
        tokens.append(chunk)
        if len(chunk) >= 2:
            tokens.extend(chunk[i : i + 2] for i in range(len(chunk) - 1))
        if len(chunk) >= 3:
            tokens.extend(chunk[i : i + 3] for i in range(len(chunk) - 2))
    return [t for t in tokens if t and t not in STOPWORDS]


@lru_cache(maxsize=2048)
def token_counter(text: str) -> Counter:
    return Counter(tokenize(text))


@lru_cache(maxsize=2048)
def md5_text(text: str) -> str:
    return md5(text.encode("utf-8", errors="ignore")).hexdigest()


def jaccard_score(query: str, text: str) -> float:
    q = set(tokenize(query))
    t = set(tokenize(text))
    if not q or not t:
        return 0.0
    return len(q & t) / max(1, len(q | t))


@lru_cache(maxsize=4096)
def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def query_variants(query: str) -> list[str]:
    query = normalize_space(query)
    variants = [query]
    lowered = query.lower()
    if contains_cjk(query):
        compact = re.sub(r"\s+", "", query)
        if compact != query:
            variants.append(compact)
    else:
        variants.append(lowered)
    words = [w for w in tokenize(query) if len(w) >= 2]
    if len(words) >= 2:
        variants.append(" ".join(words[: min(6, len(words))]))
    # 去掉常见问句语气，尽量保留高语义核心词
    stripped = re.sub(r"^(怎么|如何|请问|what|how|why|where|when)\s+", "", query, flags=re.I)
    stripped = normalize_space(stripped)
    if stripped and stripped not in variants:
        variants.append(stripped)
    deduped = []
    seen = set()
    for item in variants:
        key = normalize_for_key(item)
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:4]


class SearchService:
    def __init__(self, config: SearchConfig):
        self.config = config

    def search(
        self,
        query: str,
        max_results: int | None = None,
        sites: list[str] | None = None,
        prefer_domains: list[str] | None = None,
        block_domains: list[str] | None = None,
        include_local_docs: bool | None = None,
        include_debug: bool = False,
    ) -> dict[str, Any]:
        query = normalize_space(query)
        if not query:
            raise ValueError("query 不能为空")

        max_results = max(1, min(max_results or self.config.default_max_results, 12))
        sites = parse_csv_or_list(sites)
        prefer_domains = parse_csv_or_list(prefer_domains) or self.config.prefer_domains
        block_domains = parse_csv_or_list(block_domains) or self.config.block_domains
        include_local_docs = self.config.use_local_docs if include_local_docs is None else include_local_docs

        cache_key = md5_text(json.dumps({
            "query": query,
            "max_results": max_results,
            "sites": sites,
            "prefer_domains": prefer_domains,
            "block_domains": block_domains,
            "include_local_docs": include_local_docs,
        }, ensure_ascii=False, sort_keys=True))
        if cache_key in SEARCH_CACHE:
            cached = SEARCH_CACHE[cache_key]
            return cached

        variants = query_variants(query)
        raw_hits: list[SearchHit] = []

        for variant in variants:
            raw_hits.extend(self._search_duckduckgo(variant, max_results=max_results * 2, sites=sites))
            if self.config.use_searxng and self.config.searxng_url:
                raw_hits.extend(self._search_searxng(variant, max_results=max_results * 2, sites=sites))
            if include_local_docs and self.config.local_docs_dir:
                raw_hits.extend(self._search_local_docs(variant, max_results=max_results * 2))

        cleaned = self._clean_hits(raw_hits, block_domains=block_domains)
        ranked = self._rank_hits(
            query=query,
            hits=cleaned,
            prefer_domains=prefer_domains,
            sites=sites,
        )[:max_results]

        payload = {
            "query": query,
            "variants": variants,
            "results": [hit.compact(include_signals=include_debug) for hit in ranked],
            "meta": {
                "count": len(ranked),
                "sources": sorted({h.source for h in ranked}),
                "sites": sites,
                "prefer_domains": prefer_domains,
            },
        }
        SEARCH_CACHE[cache_key] = payload
        return payload

    def fetch_page(
        self,
        url: str,
        query: str = "",
        max_chunks: int | None = None,
        max_chars: int | None = None,
    ) -> dict[str, Any]:
        url = canonicalize_url(url)
        query = normalize_space(query)
        max_chunks = max(1, min(max_chunks or self.config.default_fetch_max_chunks, 8))
        max_chars = max(300, min(max_chars or self.config.default_fetch_max_chars, 4000))

        cache_key = md5_text(json.dumps({
            "url": url,
            "query": query,
            "max_chunks": max_chunks,
            "max_chars": max_chars,
        }, ensure_ascii=False, sort_keys=True))
        if cache_key in FETCH_CACHE:
            return FETCH_CACHE[cache_key]

        html = self._download_html(url)
        if not html:
            raise RuntimeError(f"抓取失败: {url}")

        extracted = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_images=False,
            include_links=False,
            output_format="txt",
            favor_precision=True,
            deduplicate=True,
        ) or ""

        if not extracted.strip():
            raise RuntimeError(f"正文提取失败: {url}")

        title = self._extract_title(html) or url
        chunks = sentence_chunks(extracted)
        ranked_chunks = rank_chunks(query or title, chunks)
        chosen = ranked_chunks[:max_chunks]

        evidence = []
        remaining = max_chars
        for chunk, score in chosen:
            piece = trim_text(chunk, min(remaining, 450))
            if not piece:
                continue
            evidence.append({"text": piece, "score": round(score, 4)})
            remaining -= len(piece)
            if remaining <= 0:
                break

        payload = {
            "url": url,
            "title": trim_text(title, 220),
            "query": query,
            "summary": trim_text(" ".join(item["text"] for item in evidence), max_chars),
            "evidence": evidence,
            "meta": {
                "chunks_examined": len(chunks),
                "chunks_returned": len(evidence),
                "domain": extract_domain(url),
            },
        }
        FETCH_CACHE[cache_key] = payload
        return payload

    def build_prompt_pack(
        self,
        question: str,
        results: Optional[dict[str, Any]] = None,
        max_results: int | None = None,
        sites: list[str] | None = None,
        prefer_domains: list[str] | None = None,
    ) -> dict[str, Any]:
        question = normalize_space(question)
        if not question:
            raise ValueError("question 不能为空")
        if results is None:
            results = self.search(question, max_results=max_results, sites=sites, prefer_domains=prefer_domains)

        lines = [
            "你是严谨的技术检索助手。",
            "要求：只基于下面提供的检索证据回答；证据不足时必须明确说不确定；优先使用更高分、域名更可信的结果。",
            "",
            f"用户问题：{question}",
            "",
            "检索证据：",
        ]
        for idx, item in enumerate(results.get("results", []), start=1):
            lines.append(f"[{idx}] 标题: {item['title']}")
            lines.append(f"    URL: {item['url']}")
            lines.append(f"    域名: {item['domain']} | 来源: {item['source']} | 分数: {item['score']}")
            lines.append(f"    摘要: {item['snippet']}")
            lines.append("")
        lines.extend([
            "输出要求：",
            "1. 先给结论，再给依据。",
            "2. 明确区分已证实信息与推断。",
            "3. 不要声称自己已经查看了未提供的页面正文。",
        ])
        prompt_pack = "\n".join(lines).strip()
        return {
            "question": question,
            "prompt_pack": prompt_pack,
            "meta": {
                "result_count": len(results.get("results", [])),
                "sites": parse_csv_or_list(sites),
                "prefer_domains": parse_csv_or_list(prefer_domains) or self.config.prefer_domains,
            },
        }

    def _search_duckduckgo(self, query: str, max_results: int, sites: list[str]) -> list[SearchHit]:
        decorated = query
        if sites:
            site_query = " OR ".join(f"site:{site}" for site in sites)
            decorated = f"{query} ({site_query})"
        hits: list[SearchHit] = []
        try:
            with DDGS(timeout=self.config.timeout_seconds) as ddgs:
                for row in ddgs.text(decorated, max_results=max_results):
                    url = canonicalize_url(row.get("href") or row.get("url") or "")
                    if not url:
                        continue
                    title = trim_text(row.get("title") or url, 180)
                    snippet = trim_text(row.get("body") or row.get("snippet") or "", 260)
                    hits.append(
                        SearchHit(
                            title=title,
                            url=url,
                            snippet=snippet,
                            source="duckduckgo",
                            domain=extract_domain(url),
                            published=row.get("date") or None,
                            query_variant=query,
                        )
                    )
        except Exception as exc:
            LOGGER.warning("DuckDuckGo 搜索失败: %s", exc)
        return hits

    def _search_searxng(self, query: str, max_results: int, sites: list[str]) -> list[SearchHit]:
        if not self.config.searxng_url:
            return []
        decorated = query
        if sites:
            decorated = f"{query} " + " ".join(f"site:{site}" for site in sites)
        hits: list[SearchHit] = []
        try:
            resp = SESSION.get(
                self.config.searxng_url.rstrip("/") + "/search",
                params={
                    "q": decorated,
                    "format": "json",
                    "categories": "general",
                    "language": "auto",
                },
                timeout=self.config.timeout_seconds,
            )
            resp.raise_for_status()
            payload = resp.json()
            for row in (payload.get("results") or [])[:max_results]:
                url = canonicalize_url(row.get("url") or "")
                if not url:
                    continue
                title = trim_text(row.get("title") or url, 180)
                snippet = trim_text(row.get("content") or "", 260)
                hits.append(
                    SearchHit(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source="searxng",
                        domain=extract_domain(url),
                        published=row.get("publishedDate") or None,
                        query_variant=query,
                    )
                )
        except Exception as exc:
            LOGGER.warning("SearXNG 搜索失败: %s", exc)
        return hits

    def _search_local_docs(self, query: str, max_results: int) -> list[SearchHit]:
        docs_dir = Path(self.config.local_docs_dir or "")
        if not docs_dir.exists() or not docs_dir.is_dir():
            return []
        cache_key = f"local::{docs_dir.resolve()}"
        docs = LOCAL_DOC_CACHE.get(cache_key)
        if docs is None:
            docs = []
            for path in docs_dir.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in {".md", ".txt", ".rst", ".json", ".yaml", ".yml"}:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                docs.append({
                    "path": str(path),
                    "title": path.name,
                    "text": text,
                    "domain": "local-file",
                })
            LOCAL_DOC_CACHE[cache_key] = docs
        ranked: list[tuple[float, dict[str, Any]]] = []
        for doc in docs:
            score = 0.55 * jaccard_score(query, doc["title"] + " " + doc["text"][:5000])
            score += 0.45 * (fuzz.token_set_ratio(query, doc["title"] + " " + doc["text"][:1200]) / 100.0)
            if score <= 0.18:
                continue
            ranked.append((score, doc))
        ranked.sort(key=lambda x: x[0], reverse=True)
        hits = []
        for score, doc in ranked[:max_results]:
            snippet = best_excerpt(query, doc["text"], max_chars=260)
            hits.append(
                SearchHit(
                    title=doc["title"],
                    url=f"file://{doc['path']}",
                    snippet=snippet,
                    source="local",
                    domain="local-file",
                    score=score,
                    query_variant=query,
                )
            )
        return hits

    def _clean_hits(self, hits: list[SearchHit], block_domains: list[str]) -> list[SearchHit]:
        cleaned: list[SearchHit] = []
        seen = set()
        blocked = set(block_domains) | LOW_QUALITY_DOMAINS
        for hit in hits:
            if not hit.url or not hit.title:
                continue
            hit.url = canonicalize_url(hit.url)
            hit.domain = extract_domain(hit.url)
            if not hit.domain:
                continue
            if any(hit.domain == domain or hit.domain.endswith("." + domain) for domain in blocked):
                continue
            if any(re.search(pat, hit.url, flags=re.I) for pat in BLOCKLIST_PATTERNS):
                continue
            if len(hit.title) < 3:
                continue
            key = (hit.domain, normalize_for_key(hit.title), hit.url)
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(hit)
        return self._dedupe_near_duplicates(cleaned)

    def _dedupe_near_duplicates(self, hits: list[SearchHit]) -> list[SearchHit]:
        output: list[SearchHit] = []
        signatures = set()
        for hit in hits:
            signature = (hit.domain, md5_text(normalize_for_key(hit.title)[:120] + "|" + normalize_for_key(hit.snippet)[:160]))
            if signature in signatures:
                continue
            signatures.add(signature)
            output.append(hit)
        return output

    def _rank_hits(self, query: str, hits: list[SearchHit], prefer_domains: list[str], sites: list[str]) -> list[SearchHit]:
        prefer_domains = parse_csv_or_list(prefer_domains)
        query_tokens = set(tokenize(query))
        variants = query_variants(query)

        for hit in hits:
            title = hit.title
            snippet = hit.snippet
            joined = f"{title} {snippet} {hit.domain}"

            title_fuzzy = fuzz.token_set_ratio(query, title) / 100.0
            body_fuzzy = fuzz.token_set_ratio(query, joined) / 100.0
            overlap = jaccard_score(query, joined)
            exact_phrase = 1.0 if normalize_for_key(query) in normalize_for_key(joined) else 0.0
            token_coverage = len(query_tokens & set(tokenize(joined))) / max(1, len(query_tokens))
            site_bonus = 0.0
            if sites and any(hit.domain == s or hit.domain.endswith("." + s) for s in sites):
                site_bonus = 0.12
            prefer_bonus = 0.0
            if prefer_domains and any(hit.domain == d or hit.domain.endswith("." + d) for d in prefer_domains):
                prefer_bonus = 0.14
            trust = self._domain_trust(hit.domain)
            variant_bonus = 0.0
            if hit.query_variant and normalize_for_key(hit.query_variant) != normalize_for_key(query):
                variant_bonus = 0.03
            low_quality_penalty = 0.0
            if len(snippet) < 30:
                low_quality_penalty += 0.05
            if len(title) < 8:
                low_quality_penalty += 0.03

            score = (
                0.28 * title_fuzzy
                + 0.18 * body_fuzzy
                + 0.18 * overlap
                + 0.12 * token_coverage
                + 0.10 * exact_phrase
                + 0.08 * trust
                + site_bonus
                + prefer_bonus
                + variant_bonus
                - low_quality_penalty
            )
            hit.score = max(0.0, min(score, 1.5))
            hit.rank_signals = {
                "title_fuzzy": title_fuzzy,
                "body_fuzzy": body_fuzzy,
                "overlap": overlap,
                "token_coverage": token_coverage,
                "exact_phrase": exact_phrase,
                "trust": trust,
                "site_bonus": site_bonus,
                "prefer_bonus": prefer_bonus,
                "variant_bonus": variant_bonus,
                "penalty": low_quality_penalty,
            }
            hit.snippet = trim_text(hit.snippet, 220)
            hit.title = trim_text(hit.title, 180)

        hits.sort(key=lambda item: (item.score, item.rank_signals.get("trust", 0.0), item.rank_signals.get("title_fuzzy", 0.0)), reverse=True)
        return hits

    def _domain_trust(self, domain: str) -> float:
        if domain in self.config.domain_weights:
            return self.config.domain_weights[domain]
        for known, weight in self.config.domain_weights.items():
            if domain.endswith("." + known):
                return max(weight - 0.03, 0.0)
        if domain.endswith(".gov") or domain.endswith(".edu"):
            return 0.92
        if domain.endswith(".org"):
            return 0.78
        if domain.endswith(".io"):
            return 0.72
        return 0.60

    def _download_html(self, url: str) -> Optional[str]:
        try:
            resp = SESSION.get(url, timeout=self.config.timeout_seconds)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                if resp.text:
                    return resp.text
            return resp.text
        except Exception as exc:
            LOGGER.warning("下载页面失败 %s: %s", url, exc)
            return None

    def _extract_title(self, html: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
        if not match:
            return ""
        title = re.sub(r"<[^>]+>", "", match.group(1))
        return normalize_space(title)


SERVICE = SearchService(CONFIG)
MCP = FastMCP(APP_NAME, stateless_http=True, json_response=True)


@MCP.tool()
def search_web(
    query: str,
    sites: list[str] | None = None,
    prefer_domains: list[str] | None = None,
    block_domains: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
    include_local_docs: bool = False,
    include_debug: bool = False,
) -> dict[str, Any]:
    """执行高语义、低噪声的网页检索。默认只返回精简结果，适合节省上下文 token。

    使用建议：
    1. 先调用本工具获取候选结果。
    2. 若需正文证据，再对单个 URL 调用 fetch_page。
    3. 若需要给模型继续推理，可调用 build_prompt_pack 生成压缩证据包。
    """
    return SERVICE.search(
        query=query,
        max_results=max_results,
        sites=sites,
        prefer_domains=prefer_domains,
        block_domains=block_domains,
        include_local_docs=include_local_docs,
        include_debug=include_debug,
    )


@MCP.tool()
def fetch_page(
    url: str,
    query: str = "",
    max_chunks: int = DEFAULT_FETCH_MAX_CHUNKS,
    max_chars: int = DEFAULT_FETCH_MAX_CHARS,
) -> dict[str, Any]:
    """抓取并压缩单个页面正文，只返回与 query 最相关的证据片段。适合二阶段检索，减少 token。"""
    return SERVICE.fetch_page(url=url, query=query, max_chunks=max_chunks, max_chars=max_chars)


@MCP.tool()
def build_prompt_pack(
    question: str,
    sites: list[str] | None = None,
    prefer_domains: list[str] | None = None,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> dict[str, Any]:
    """根据检索结果生成紧凑型 Prompt Pack，适合继续交给 Claude Code 推理。"""
    return SERVICE.build_prompt_pack(
        question=question,
        max_results=max_results,
        sites=sites,
        prefer_domains=prefer_domains,
    )


def best_excerpt(query: str, text: str, max_chars: int = 260) -> str:
    chunks = sentence_chunks(text)
    ranked = rank_chunks(query, chunks)
    return trim_text(" ".join(chunk for chunk, _ in ranked[:2]), max_chars)


def sentence_chunks(text: str) -> list[str]:
    text = normalize_space(text)
    if not text:
        return []
    parts = re.split(r"(?<=[。！？.!?])\s+|\n+", text)
    chunks: list[str] = []
    buffer = ""
    for part in parts:
        part = normalize_space(part)
        if not part:
            continue
        if len(buffer) + len(part) <= 280:
            buffer = f"{buffer} {part}".strip()
        else:
            if buffer:
                chunks.append(buffer)
            buffer = part
    if buffer:
        chunks.append(buffer)
    return chunks


def rank_chunks(query: str, chunks: list[str]) -> list[tuple[str, float]]:
    ranked = []
    for chunk in chunks:
        score = 0.55 * jaccard_score(query, chunk)
        score += 0.35 * (fuzz.token_set_ratio(query, chunk) / 100.0)
        if normalize_for_key(query) and normalize_for_key(query) in normalize_for_key(chunk):
            score += 0.1
        if len(chunk) < 40:
            score -= 0.04
        ranked.append((chunk, score))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search MCP Server")
    sub = parser.add_subparsers(dest="mode")

    stdio = sub.add_parser("stdio", help="run stdio MCP server")
    stdio.set_defaults(mode="stdio")

    http = sub.add_parser("http", help="run streamable-http MCP server")
    http.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    http.add_argument("--port", type=int, default=int(os.getenv("PORT", "9000")))
    http.set_defaults(mode="http")

    sub.add_parser("doctor", help="print current config")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.mode == "doctor":
        doctor = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "config": asdict(CONFIG),
            "env": {
                "SEARCH_SEARXNG_URL": os.getenv("SEARCH_SEARXNG_URL"),
                "SEARCH_ENABLE_SEARXNG": os.getenv("SEARCH_ENABLE_SEARXNG"),
                "SEARCH_LOCAL_DOCS_DIR": os.getenv("SEARCH_LOCAL_DOCS_DIR"),
                "SEARCH_ENABLE_LOCAL_DOCS": os.getenv("SEARCH_ENABLE_LOCAL_DOCS"),
            },
        }
        json.dump(doctor, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    if args.mode == "http":
        os.environ.setdefault("FASTMCP_HOST", args.host)
        os.environ.setdefault("FASTMCP_PORT", str(args.port))
        _safe_log("starting http MCP server on %s:%s", args.host, args.port)
        MCP.run(transport="streamable-http")
        return

    _safe_log("starting stdio MCP server")
    MCP.run()


if __name__ == "__main__":
    main()
