"""Read-only forensic capture for intermittent variation-selection failures.

This module records evidence only when VariationSelector reports a failure.
It does not change selectors, timing, retries, or browser state.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path


class VariationSelectionForensics:
    ROOT = Path("runtime/logs/variation_forensics")

    @classmethod
    def capture(cls, browser, stage, selector, details=None):
        timestamp = datetime.now(timezone.utc)
        payload = {
            "schema_version": 1,
            "captured_at": timestamp.isoformat(),
            "unix_time_ms": int(timestamp.timestamp() * 1000),
            "stage": stage,
            "searched_selector": selector,
            "details": details or {},
        }

        try:
            payload["page_url"] = browser.session.page.url
        except Exception as exc:
            payload["page_url_error"] = repr(exc)

        try:
            snapshot = browser._submit(
                browser.session.page.evaluate(
                    """() => {
                        const navigation = performance.getEntriesByType("navigation")[0];
                        const now = performance.now();
                        const navigationEnd = navigation
                            ? (navigation.domContentLoadedEventEnd || navigation.loadEventEnd || navigation.responseEnd || 0)
                            : 0;

                        const normalize = (value) =>
                            String(value || "").replace(/\\s+/g, " ").trim();

                        const sections = Array.from(document.querySelectorAll("section")).map(
                            (section, index) => ({
                                index,
                                text: normalize(section.innerText || section.textContent || ""),
                                h2: Array.from(section.querySelectorAll("h2")).map(
                                    (node) => normalize(node.innerText || node.textContent || "")
                                ),
                                buttons: Array.from(section.querySelectorAll("button")).map(
                                    (button, buttonIndex) => ({
                                        index: buttonIndex,
                                        aria_label: button.getAttribute("aria-label"),
                                        text: normalize(button.innerText || button.textContent || ""),
                                        disabled: !!button.disabled,
                                        outer_html: button.outerHTML.slice(0, 4000),
                                    })
                                ),
                                outer_html: section.outerHTML.slice(0, 20000),
                            })
                        );

                        return {
                            navigation_timing: navigation
                                ? {
                                    start_time_ms: navigation.startTime,
                                    dom_content_loaded_end_ms: navigation.domContentLoadedEventEnd,
                                    load_event_end_ms: navigation.loadEventEnd,
                                    response_end_ms: navigation.responseEnd,
                                }
                                : null,
                            elapsed_since_navigation_completion_ms:
                                navigationEnd > 0 ? Math.max(0, now - navigationEnd) : null,
                            document_ready_state: document.readyState,
                            section_count: sections.length,
                            sections,
                            variation_section_candidates: sections.filter(
                                (section) =>
                                    section.h2.length > 0 ||
                                    /color|capacity|storage|quantity/i.test(section.text)
                            ),
                        };
                    }"""
                ),
                timeout=15,
            )
            payload["dom"] = snapshot
        except Exception as exc:
            payload["dom_capture_error"] = repr(exc)

        try:
            cls.ROOT.mkdir(parents=True, exist_ok=True)
            filename = (
                f"{timestamp.strftime('%Y%m%dT%H%M%S.%fZ')}_"
                f"{int(time.time_ns() % 1000000):06d}_{stage}.json"
            )
            path = cls.ROOT / filename
            path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            payload["file"] = str(path)
        except Exception as exc:
            payload["file_write_error"] = repr(exc)

        return payload
