from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


class WebSearchError(RuntimeError):
    """Raised when the public web search provider cannot be reached."""


_EXPLICIT_SEARCH = re.compile(
    r"^\s*(?:please\s+)?(?:search(?:\s+the)?\s+web\s+(?:for|about)|look\s+up|find\s+online)\s*[:,-]?\s*",
    re.IGNORECASE,
)
_QUESTION_START = re.compile(
    r"^\s*(?:who|what|when|where|why|how|which|whom|whose|is|are|am|was|were|do|does|did|can|could|would|should|will|has|have|had|latest|current|recent|news|weather)\b",
    re.IGNORECASE,
)
_CURRENT_OR_LOCAL_LOOKUP = re.compile(
    r"\b(current(?:ly)?|latest|today|tonight|yesterday|recent|now|this\s+(?:week|month|year)|"
    r"breaking|news|weather|temperature|price|cost|forecast|stock|share price|exchange rate|"
    r"score|standings|schedule|traffic|opening hours|available now|who is the (?:current )?(?:president|prime minister|ceo))\b",
    re.IGNORECASE,
)


def web_query_for_message(text: str) -> str | None:
    """Return a web query for an explicit search or a time-sensitive question."""
    explicit = _EXPLICIT_SEARCH.match(text)
    if explicit:
        query = text[explicit.end():].strip()
        return query[:500] if query else text.strip()[:500]
    if _CURRENT_OR_LOCAL_LOOKUP.search(text) and (text.rstrip().endswith("?") or _QUESTION_START.match(text)):
        return text.strip()[:500]
    return None


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, object]] = []
        self._capture: tuple[str, str, dict[str, object]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            result: dict[str, object] = {"href": values.get("href") or "", "title_parts": []}
            self.results.append(result)
            self._capture = ("title_parts", "a", result)
        elif "result__snippet" in classes and tag in {"a", "div", "td"}:
            if self.results:
                result = self.results[-1]
                result.setdefault("snippet_parts", [])
                self._capture = ("snippet_parts", tag, result)

    def handle_endtag(self, tag: str) -> None:
        if self._capture and self._capture[1] == tag:
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self._capture:
            bucket = self._capture[2][self._capture[0]]
            if isinstance(bucket, list):
                bucket.append(data)


def _clean(value: object, limit: int) -> str:
    if not isinstance(value, list):
        return ""
    text = re.sub(r"\s+", " ", " ".join(str(part) for part in value)).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"\s*-\s*", "-", text)[:limit]


def _result_url(href: str) -> str:
    candidate = urljoin("https://html.duckduckgo.com", href.strip())
    parts = urlsplit(candidate)
    if parts.hostname in {"duckduckgo.com", "www.duckduckgo.com", "html.duckduckgo.com"}:
        target = parse_qs(parts.query).get("uddg", [""])[0]
        if target:
            candidate = target
            parts = urlsplit(candidate)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        return ""
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def _parse_results(page: str, max_results: int) -> list[SearchResult]:
    parser = _DuckDuckGoParser()
    parser.feed(page)
    output: list[SearchResult] = []
    seen: set[str] = set()
    for row in parser.results:
        title = _clean(row.get("title_parts"), 240)
        snippet = _clean(row.get("snippet_parts"), 700)
        url = _result_url(str(row.get("href", "")))
        if title and url and url not in seen:
            output.append(SearchResult(title=title, url=url, snippet=snippet))
            seen.add(url)
            if len(output) >= max_results:
                break
    return output


def _search_sync(query: str, max_results: int, timeout_seconds: float) -> list[SearchResult]:
    url = "https://html.duckduckgo.com/html/?" + urlencode({"q": query})
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-GB,en;q=0.9",
    })
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            if response.status != 200:
                raise WebSearchError(f"Search provider returned HTTP {response.status}")
            page = response.read(1_000_001)[:1_000_000].decode(
                response.headers.get_content_charset() or "utf-8", errors="replace"
            )
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise WebSearchError("Unable to reach the web search provider") from exc
    return _parse_results(page, max_results)


async def search_web(query: str, max_results: int = 5, timeout_seconds: float = 8.0) -> list[SearchResult]:
    cleaned = " ".join(query.split())
    if not cleaned or len(cleaned) > 500:
        raise ValueError("Search query must contain 1 to 500 characters")
    if not 1 <= max_results <= 10:
        raise ValueError("max_results must be between 1 and 10")
    return await asyncio.to_thread(_search_sync, cleaned, max_results, timeout_seconds)


def result_payload(result: SearchResult) -> dict[str, str]:
    return asdict(result)


def best_answer_excerpt(query: str, results: list[SearchResult], limit: int = 420) -> str:
    """Choose a short, query-relevant sentence from search snippets without inventing facts."""
    stop_words = {"what", "when", "where", "which", "who", "whom", "whose", "how", "the", "and", "for",
                  "from", "with", "does", "are", "was", "were", "is", "a", "an", "of", "to", "in", "on"}
    terms = {token.casefold() for token in re.findall(r"[\w'-]+", query) if len(token) > 2}
    terms -= stop_words
    candidates: list[tuple[float, int, str]] = []
    for result_index, result in enumerate(results):
        text = result.snippet or result.title
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        for sentence in sentences or [text]:
            lowered = sentence.casefold()
            overlap = sum(1 for term in terms if term in lowered)
            if overlap:
                score = overlap * 100 - min(len(sentence), 1000) / 20 - result_index * 0.01
                candidates.append((score, -result_index, sentence))
    selected = max(candidates)[2] if candidates else (results[0].snippet or results[0].title if results else "")
    selected = selected.strip()
    if len(selected) > limit:
        clipped = selected[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-")
        selected = clipped + "…"
    return selected
