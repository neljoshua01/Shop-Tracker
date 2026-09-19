"""Read-only forensic capture for intermittent variation-selection failures.

This module records evidence only when VariationSelector reports a failure,
plus a state snapshot at the existing post-click observation point.
It does not change selectors, timing, retries, or browser state.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path


class VariationSelectionForensics:
    ROOT = Path("runtime/logs/variation_forensics")

    @classmethod
    def _write(cls, payload, timestamp, stage):
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
                                        aria_pressed: button.getAttribute("aria-pressed"),
                                        aria_checked: button.getAttribute("aria-checked"),
                                        role: button.getAttribute("role"),
                                        text: normalize(button.innerText || button.textContent || ""),
                                        disabled: !!button.disabled,
                                        class_name: button.className,
                                        data_attributes: Array.from(button.attributes)
                                            .filter((attribute) => attribute.name.startsWith("data-"))
                                            .reduce((result, attribute) => {
                                                result[attribute.name] = attribute.value;
                                                return result;
                                            }, {}),
                                        outer_html: button.outerHTML.slice(0, 4000),
                                    })
                                ),
                                outer_html: section.outerHTML.slice(0, 20000),
                            })
                        );

                        const resources = performance.getEntriesByType("resource")
                            .filter((entry) =>
                                /\\/api\\/v4\\/pdp\\/get_pc/i.test(entry.name)
                            )
                            .slice(-10)
                            .map((entry) => ({
                                name: entry.name,
                                start_time_ms: entry.startTime,
                                duration_ms: entry.duration,
                                response_end_ms: entry.responseEnd,
                                transfer_size: entry.transferSize,
                                encoded_body_size: entry.encodedBodySize,
                                decoded_body_size: entry.decodedBodySize,
                            }));

                        const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;

                        return {
                            captured_at_performance_ms: now,
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
                            connection: connection
                                ? {
                                    effective_type: connection.effectiveType || null,
                                    downlink_mbps: connection.downlink || null,
                                    rtt_ms: connection.rtt || null,
                                    save_data: !!connection.saveData,
                                }
                                : null,
                            get_pc_resources: resources,
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

        return cls._write(payload, timestamp, stage)

    @classmethod
    def capture_post_click(
        cls,
        browser,
        requested_title,
        resolved_title,
        requested_value,
        selected_button_value,
        click_started_monotonic_ns,
    ):
        """Capture UI/network state at the existing post-click observation point."""
        timestamp = datetime.now(timezone.utc)
        payload = {
            "schema_version": 1,
            "captured_at": timestamp.isoformat(),
            "unix_time_ms": int(timestamp.timestamp() * 1000),
            "stage": "post_click_state",
            "searched_selector": "button",
            "details": {
                "requested_title": requested_title,
                "resolved_title": resolved_title,
                "requested_value": requested_value,
                "selected_button_value": selected_button_value,
                "elapsed_since_click_ms": (
                    time.monotonic_ns() - click_started_monotonic_ns
                ) / 1_000_000,
            },
        }

        try:
            payload["page_url"] = browser.session.page.url
        except Exception as exc:
            payload["page_url_error"] = repr(exc)

        try:
            snapshot = browser._submit(
                browser.session.page.evaluate(
                    """(target) => {
                        const normalize = (value) =>
                            String(value || "").replace(/\\s+/g, " ").trim();

                        const matchingSections = Array.from(document.querySelectorAll("section"))
                            .filter((section) => {
                                const heading = Array.from(section.querySelectorAll("h2"))
                                    .map((node) => normalize(node.innerText || node.textContent || ""))
                                    .find((value) =>
                                        value.toLowerCase() === target.resolved_title.toLowerCase()
                                    );
                                return !!heading;
                            });

                        const buttonState = matchingSections.map((section, sectionIndex) => ({
                            section_index: sectionIndex,
                            heading: Array.from(section.querySelectorAll("h2"))
                                .map((node) => normalize(node.innerText || node.textContent || "")),
                            buttons: Array.from(section.querySelectorAll("button")).map(
                                (button, buttonIndex) => ({
                                    index: buttonIndex,
                                    aria_label: button.getAttribute("aria-label"),
                                    aria_pressed: button.getAttribute("aria-pressed"),
                                    aria_checked: button.getAttribute("aria-checked"),
                                    role: button.getAttribute("role"),
                                    text: normalize(button.innerText || button.textContent || ""),
                                    disabled: !!button.disabled,
                                    class_name: button.className,
                                    data_attributes: Array.from(button.attributes)
                                        .filter((attribute) => attribute.name.startsWith("data-"))
                                        .reduce((result, attribute) => {
                                            result[attribute.name] = attribute.value;
                                            return result;
                                        }, {}),
                                    outer_html: button.outerHTML.slice(0, 4000),
                                })
                            ),
                            outer_html: section.outerHTML.slice(0, 20000),
                        }));

                        const resources = performance.getEntriesByType("resource")
                            .filter((entry) =>
                                /\\/api\\/v4\\/pdp\\/get_pc/i.test(entry.name)
                            )
                            .slice(-10)
                            .map((entry) => ({
                                name: entry.name,
                                start_time_ms: entry.startTime,
                                duration_ms: entry.duration,
                                response_end_ms: entry.responseEnd,
                                transfer_size: entry.transferSize,
                                encoded_body_size: entry.encodedBodySize,
                                decoded_body_size: entry.decodedBodySize,
                            }));

                        const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;

                        return {
                            document_ready_state: document.readyState,
                            connection: connection
                                ? {
                                    effective_type: connection.effectiveType || null,
                                    downlink_mbps: connection.downlink || null,
                                    rtt_ms: connection.rtt || null,
                                    save_data: !!connection.saveData,
                                }
                                : null,
                            get_pc_resources: resources,
                            matching_sections: buttonState,
                        };
                    }""",
                    {
                        "resolved_title": resolved_title,
                    },
                ),
                timeout=15,
            )
            payload["dom"] = snapshot
        except Exception as exc:
            payload["dom_capture_error"] = repr(exc)

        return cls._write(payload, timestamp, "post_click_state")

