"""Real browser test for MC-WORKBENCH-01: click Open Workbench in the sidebar."""

import re
import sys

from playwright.sync_api import expect, sync_playwright

MC_URL = "http://127.0.0.1:8790"
WB_URL = "http://127.0.0.1:7420/"


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        try:
            context = browser.new_context(viewport={"width": 1360, "height": 900})
            page = context.new_page()
            page.goto(MC_URL, wait_until="networkidle", timeout=30000)

            button = page.get_by_role("button", name=re.compile(r"Open Workbench"))
            button.wait_for(timeout=20000)
            print("sidebar button visible:", button.text_content().strip().replace("\n", " | "))

            engines = page.locator(".nav-group", has_text="Engines")
            first_action = engines.locator("button, a").first.text_content()
            print("first item in Engines:", (first_action or "").strip().replace("\n", " | "))
            assert "Open Workbench" in (first_action or ""), "Open Workbench is not first in Engines"

            with page.expect_popup(timeout=45000) as popup_info:
                button.click()
            popup = popup_info.value
            popup.wait_for_load_state("domcontentloaded", timeout=30000)
            expect(popup).to_have_title(re.compile("Workbench"), timeout=30000)
            print("popup url:", popup.url)
            print("popup title:", popup.title())
            assert popup.url.startswith(WB_URL.rstrip("/")), popup.url
            assert "Workbench" in popup.title()

            # Mission Control tab is still available.
            assert page.url.startswith(MC_URL), page.url
            print("mission control tab intact:", page.url)

            # Toast confirmation inside Mission Control.
            page.get_by_text("Workbench ready", exact=False).wait_for(timeout=15000)
            print("toast confirmed: Workbench ready")

            # Mobile viewport: hamburger menu exposes the same action.
            mobile = context.new_page()
            mobile.set_viewport_size({"width": 375, "height": 800})
            mobile.goto(MC_URL, wait_until="networkidle", timeout=30000)
            mobile.get_by_role("button", name="Open navigation").click()
            mobile_button = mobile.get_by_role("button", name=re.compile(r"Open Workbench"))
            mobile_button.wait_for(timeout=20000)
            print("mobile sidebar action visible")
            with mobile.expect_popup(timeout=45000) as mobile_popup:
                mobile_button.click()
            mpop = mobile_popup.value
            mpop.wait_for_load_state("domcontentloaded", timeout=30000)
            expect(mpop).to_have_title(re.compile("Workbench"), timeout=30000)
            print("mobile popup url:", mpop.url)
            assert mpop.url.startswith(WB_URL.rstrip("/")), mpop.url
        finally:
            browser.close()
    print("BROWSER TEST PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
