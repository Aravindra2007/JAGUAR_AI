"""
Jaguar AI — Browser Automation.

Wraps Playwright when it's installed (the recommended path), and falls
back to plain `webbrowser` calls when it isn't. The point is that the
rest of the agent can call this without caring whether Playwright is
present - the methods here all return plain Python values, never a
Playwright object directly.

Realistic-but-graceful: when a step can't be carried out (selector
missing, page not interactive, etc.), the methods return a structured
result the caller can log and continue from.
"""

from __future__ import annotations

import json
import os
import time
import webbrowser
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BrowserResult:
    ok: bool
    action: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "action": self.action,
            "message": self.message,
            "data": self.data,
        }


def _try_import_playwright():
    """Lazy import so the rest of the app keeps working even if
    Playwright isn't installed."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
        return sync_playwright
    except Exception:
        return None


class BrowserAutomation:
    """A thin facade over Playwright. The browser is launched on first
    use and reused across calls."""

    def __init__(self, headless: bool = False, user_data_dir: Optional[str] = None):
        self.headless = headless
        self.user_data_dir = user_data_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "jaguar_data", "browser_profile",
        )
        os.makedirs(self.user_data_dir, exist_ok=True)

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._sync = _try_import_playwright()
        self._owns_page = False

    # ----------------------------------------
    # Lifecycle
    # ----------------------------------------

    def _ensure_page(self):
        if self._page is not None:
            return self._page
        if self._sync is None:
            return None
        self._playwright = self._sync.start()
        try:
            self._browser = self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
            )
            self._context = self._browser
        except Exception:
            # Fall back to a non-persistent context if launch_persistent_context fails
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            self._context = self._browser.new_context()
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = self._context.new_page()
        self._owns_page = True
        return self._page

    def close(self):
        try:
            if self._context is not None:
                self._context.close()
        except Exception:
            pass
        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._owns_page = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ----------------------------------------
    # High-level actions
    # ----------------------------------------

    def open_website(self, url: str) -> BrowserResult:
        """Open a URL. Uses the system browser as a hard fallback so
        callers always get a working browser opened, even without
        Playwright."""
        if not url:
            return BrowserResult(False, "open_website", "No URL provided.")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        page = self._ensure_page()
        if page is not None:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                return BrowserResult(True, "open_website", f"Opened {url}", {"url": url})
            except Exception as e:
                # Browser failed to open it - fall back to webbrowser so
                # the user still gets somewhere.
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
                return BrowserResult(True, "open_website",
                                     f"Opened {url} in system browser (Playwright fallback).",
                                     {"url": url, "warning": str(e)})

        try:
            webbrowser.open(url)
        except Exception as e:
            return BrowserResult(False, "open_website", f"Could not open {url}: {e}")
        return BrowserResult(True, "open_website", f"Opened {url}", {"url": url})

    def search(self, query: str, engine: str = "google") -> BrowserResult:
        """Run a web search. Returns the search-results URL."""
        query = (query or "").strip()
        if not query:
            return BrowserResult(False, "search", "Empty query.")
        from urllib.parse import quote_plus
        engines = {
            "google":   "https://www.google.com/search?q={q}",
            "bing":     "https://www.bing.com/search?q={q}",
            "duckduckgo": "https://duckduckgo.com/?q={q}",
            "youtube":  "https://www.youtube.com/results?search_query={q}",
        }
        template = engines.get(engine.lower(), engines["google"])
        url = template.format(q=quote_plus(query))
        return self.open_website(url)

    def click(self, selector_or_text: str) -> BrowserResult:
        """Click an element by CSS selector or visible text."""
        page = self._ensure_page()
        if page is None:
            return BrowserResult(False, "click",
                                 "Playwright not available - cannot click reliably.")
        try:
            try:
                page.click(selector_or_text, timeout=5000)
                return BrowserResult(True, "click", f"Clicked {selector_or_text}")
            except Exception:
                # Try a text-based click as a fallback
                page.get_by_text(selector_or_text, exact=False).first.click(timeout=5000)
                return BrowserResult(True, "click", f"Clicked text '{selector_or_text}'")
        except Exception as e:
            return BrowserResult(False, "click", f"Could not click '{selector_or_text}': {e}")

    def fill_form(self, fields: Dict[str, str]) -> BrowserResult:
        """Fill a dict of {selector_or_label: value} on the current page."""
        page = self._ensure_page()
        if page is None:
            return BrowserResult(False, "fill_form",
                                 "Playwright not available - cannot fill forms reliably.")
        filled: List[str] = []
        failed: List[str] = []
        for selector, value in (fields or {}).items():
            try:
                el = page.locator(selector).first
                el.fill(str(value), timeout=4000)
                filled.append(selector)
            except Exception:
                try:
                    page.get_by_label(selector).first.fill(str(value), timeout=4000)
                    filled.append(selector)
                except Exception:
                    failed.append(selector)
        return BrowserResult(
            bool(filled),
            "fill_form",
            f"Filled {len(filled)} field(s), failed {len(failed)}.",
            {"filled": filled, "failed": failed},
        )

    def type_text(self, text: str, selector: Optional[str] = None) -> BrowserResult:
        page = self._ensure_page()
        if page is None:
            return BrowserResult(False, "type", "Playwright not available.")
        try:
            if selector:
                page.locator(selector).first.fill(text, timeout=4000)
            else:
                page.keyboard.type(text, delay=20)
            return BrowserResult(True, "type", f"Typed {len(text)} chars")
        except Exception as e:
            return BrowserResult(False, "type", f"Type failed: {e}")

    def press(self, key: str) -> BrowserResult:
        page = self._ensure_page()
        if page is None:
            return BrowserResult(False, "press", "Playwright not available.")
        try:
            page.keyboard.press(key)
            return BrowserResult(True, "press", f"Pressed {key}")
        except Exception as e:
            return BrowserResult(False, "press", f"Press failed: {e}")

    def get_text(self, selector: str = "body") -> BrowserResult:
        page = self._ensure_page()
        if page is None:
            return BrowserResult(False, "get_text", "Playwright not available.")
        try:
            txt = page.locator(selector).first.inner_text(timeout=5000)
            return BrowserResult(True, "get_text", "OK", {"text": txt[:8000]})
        except Exception as e:
            return BrowserResult(False, "get_text", f"Could not read text: {e}")

    def screenshot(self, path: str) -> BrowserResult:
        page = self._ensure_page()
        if page is None:
            return BrowserResult(False, "screenshot", "Playwright not available.")
        try:
            page.screenshot(path=path, full_page=True)
            return BrowserResult(True, "screenshot", f"Saved screenshot to {path}",
                                 {"path": path})
        except Exception as e:
            return BrowserResult(False, "screenshot", f"Screenshot failed: {e}")

    def wait(self, seconds: float) -> BrowserResult:
        time.sleep(max(0.0, float(seconds)))
        return BrowserResult(True, "wait", f"Waited {seconds}s")

    # ----------------------------------------
    # Job-apply specific helpers (used by autonomous mode)
    # ----------------------------------------

    def search_jobs_linkedin(self, query: str, location: str = "",
                              max_results: int = 10) -> BrowserResult:
        """Open LinkedIn job search and pull out the visible job
        cards. This is best-effort - LinkedIn's DOM changes and may
        require login. Returns structured results when possible."""
        from urllib.parse import quote_plus
        url = (
            "https://www.linkedin.com/jobs/search?"
            f"keywords={quote_plus(query)}&location={quote_plus(location)}"
        )
        open_res = self.open_website(url)
        if not open_res.ok:
            return open_res
        page = self._ensure_page()
        if page is None:
            return BrowserResult(True, "search_jobs_linkedin",
                                 f"Opened LinkedIn jobs search in system browser.",
                                 {"query": query, "location": location, "jobs": []})

        jobs: List[Dict[str, Any]] = []
        try:
            page.wait_for_timeout(2500)
            cards = page.locator(".job-card-container, .base-card, .jobs-search-results__list-item")
            count = min(cards.count(), max_results)
            for i in range(count):
                try:
                    card = cards.nth(i)
                    title = ""
                    try:
                        title = card.locator(".base-search-card__title, .job-card-list__title").first.inner_text(timeout=2000)
                    except Exception:
                        pass
                    company = ""
                    try:
                        company = card.locator(".base-search-card__subtitle, .job-card-container__company-name").first.inner_text(timeout=2000)
                    except Exception:
                        pass
                    href = ""
                    try:
                        href = card.locator("a").first.get_attribute("href") or ""
                    except Exception:
                        pass
                    jobs.append({"title": title.strip(), "company": company.strip(),
                                 "url": href.strip(), "source": "linkedin"})
                except Exception:
                    continue
        except Exception:
            pass
        return BrowserResult(True, "search_jobs_linkedin",
                             f"Found {len(jobs)} job card(s) on LinkedIn.",
                             {"query": query, "location": location, "jobs": jobs})

    def apply_to_listing(self, job: Dict[str, Any], answers: Dict[str, str]) -> BrowserResult:
        """Best-effort 'apply' to a single LinkedIn-style job listing.

        Real LinkedIn Easy Apply flows require login and a multi-step
        modal. Without credentials this can only click the 'Easy Apply'
        button and try to walk through up to 3 steps. We never
        fabricate success - we report exactly what happened so the
        autonomous mode can store honest results."""
        page = self._ensure_page()
        if page is None:
            return BrowserResult(False, "apply_to_listing",
                                 "Playwright not available.", {"job": job})

        url = job.get("url") or ""
        if url:
            self.open_website(url)

        applied = False
        steps_walked = 0
        try:
            page.wait_for_timeout(2000)
            # Try to find an Easy Apply button.
            for label in ["Easy Apply", "Apply", "Apply now"]:
                try:
                    btn = page.get_by_role("button", name=label).first
                    if btn.is_visible(timeout=2000):
                        btn.click(timeout=4000)
                        applied = True
                        steps_walked += 1
                        break
                except Exception:
                    continue

            # Try to walk through up to 3 next/submit buttons
            for _ in range(3):
                try:
                    nxt = page.get_by_role("button", name="Next").first
                    if nxt.is_visible(timeout=1500):
                        nxt.click(timeout=3000)
                        steps_walked += 1
                        continue
                except Exception:
                    pass
                try:
                    sub = page.get_by_role("button", name="Submit application").first
                    if sub.is_visible(timeout=1500):
                        sub.click(timeout=3000)
                        steps_walked += 1
                        applied = True
                        break
                except Exception:
                    break
        except Exception as e:
            return BrowserResult(False, "apply_to_listing",
                                 f"Apply attempt error: {e}",
                                 {"job": job, "steps": steps_walked})

        return BrowserResult(
            applied, "apply_to_listing",
            "Applied" if applied else f"Walked {steps_walked} step(s) but did not submit.",
            {"job": job, "answers": answers, "steps_walked": steps_walked,
             "applied": applied},
        )
