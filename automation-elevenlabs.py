import asyncio
from playwright.async_api import async_playwright
import time, re, os
from pathlib import Path

# === Configuration ===
username = "ahmad.alzarooni@mbrl.ae"
password = "Q9UxnB8r?Yi$65M"
login_url = "https://elevenlabs.io/app/sign-in"
doc_file = r"C:\Users\Mohsin\Downloads\translated\chapters_e488a414c7cc4efc8f579083d92a275f_english_translated.docx"
AUDIO_OUTPUT_DIR = r"C:\Users\Mohsin\Downloads\elevenlabs-exports"


async def dismiss_popovers(page):
    for _ in range(3):
        closed = False
        for sel in [
            page.get_by_role("button", name=re.compile(r"^\s*Got it\s*$", re.I)).first,
            page.get_by_role("button", name=re.compile(r"^\s*Close\s*$", re.I)).first,
            page.locator('[aria-label="Close"], [data-testid*="close"]').first,
        ]:
            try:
                if await sel.count():
                    await sel.click(timeout=800)
                    closed = True
            except Exception:
                pass
        if not closed:
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            break


async def go_to_studio(page):
    await dismiss_popovers(page)
    if re.search(r"/app/studio", page.url, re.I):
        return
    try:
        await page.goto("https://elevenlabs.io/app/studio", wait_until="domcontentloaded")
    except Exception:
        pass
    await dismiss_popovers(page)


async def click_new_audiobook(page):
    await dismiss_popovers(page)
    btn = page.locator("button:has-text('New audiobook'), a:has-text('New audiobook')").first
    await btn.wait_for(state="visible", timeout=10000)
    await btn.click()
    print("✅ Clicked New audiobook")


async def upload_doc_and_create_project(page, file_path: str):
    await dismiss_popovers(page)
    file_input = page.locator('input[type="file"]').first
    await file_input.wait_for(state="attached", timeout=15000)
    await file_input.set_input_files(file_path)
    print(f"📤 Uploaded: {os.path.basename(file_path)}")

    create_btn = page.locator("button:has-text('Create project'), button:has-text('Create Project')").first
    try:
        await create_btn.wait_for(state="visible", timeout=30000)
        await create_btn.scroll_into_view_if_needed()
        await create_btn.click()
        print("✅ Clicked Create project")
    except Exception:
        print("➡️ Editor might have opened automatically after upload")


async def _has_export_status(page, wait_ms=0):
    patt = re.compile(r"\bExport status\b", re.I)
    dlg = page.get_by_role("dialog").filter(has_text=patt).last
    if wait_ms:
        try:
            await dlg.wait_for(state="visible", timeout=wait_ms)
            return True
        except Exception:
            return False
    return await dlg.count() > 0


async def click_view_exports(page):
    """Click 'View exports' in the Export status popover."""
    # popover is a dialog with 'Export status'
    pop = page.get_by_role("dialog").filter(has_text=re.compile(r"\bExport status\b", re.I)).last
    try:
        await pop.wait_for(state="visible", timeout=15000)
    except Exception:
        return False

    btn = pop.locator("xpath=.//*[self::button or self::a or @role='button'][contains(normalize-space(.),'View exports')]").first
    try:
        if await btn.count():
            await btn.scroll_into_view_if_needed()
            await btn.click(force=True, timeout=2000)
            return True
    except Exception:
        pass
    return False


# --- replace both old click_export defs with this single tolerant version ---
async def click_export(page):
    """Open the export panel (if needed). If export already started, just return."""
    await dismiss_popovers(page)

    # If export already started (toast visible), do not try to click again.
    if await _has_export_status(page):
        print("ℹ️ Export already in progress.")
        return True

    # Ensure export panel (with File structure/Audio format) is open
    dialog = page.get_by_role("dialog").filter(
        has_text=re.compile(r"(File structure|Audio format)", re.I)
    ).first

    try:
        await dialog.wait_for(state="visible", timeout=8000)
    except Exception:
        header_export = page.get_by_role("button", name=re.compile(r"^\s*Export\s*$", re.I)).first
        await header_export.wait_for(state="visible", timeout=15000)
        await header_export.scroll_into_view_if_needed()
        try:
            await header_export.click(timeout=3000)
        except Exception:
            h = await header_export.element_handle()
            if h:
                await page.evaluate("(el)=>el.click()", h)
        await dialog.wait_for(state="visible", timeout=15000)

    # Click the big black "Export" button
    bottom_export = dialog.get_by_role("button", name=re.compile(r"^\s*Export\s*$", re.I)).first
    try:
        await bottom_export.wait_for(state="visible", timeout=15000)
        await bottom_export.scroll_into_view_if_needed()
        await bottom_export.click(timeout=4000)
        print("✅ Clicked Export (panel)")
    except Exception:
        # JS fallback
        try:
            h = await bottom_export.element_handle()
            if h:
                await page.evaluate("(el)=>el.click()", h)
                print("✅ Clicked Export via JS fallback")
        except Exception:
            pass

    # Consider success if the Export status toast appears shortly after
    if await _has_export_status(page, wait_ms=15000):
        print("✅ Export started (toast detected).")
        return True

    # If no toast appears, do not fail hard; continue so caller can retry/alternate path
    print("⚠️ Export toast not detected; continuing.")
    return False


async def open_exports_drawer(page):
    """Ensure the right-side Exports drawer is open."""
    await dismiss_popovers(page)
    clicked = await click_view_exports(page)
    if not clicked:
        if "exports=open" not in page.url:
            new_url = page.url + ("&" if "?" in page.url else "?") + "exports=open"
            await page.goto(new_url, wait_until="domcontentloaded")

    drawer = page.locator("div[role='dialog'], aside[role='dialog']").filter(
        has_text=re.compile(r"(Exports?|% completed|MP3|WAV|kbps)", re.I)
    ).first
    await drawer.wait_for(state="visible", timeout=20000)
    return drawer


async def wait_for_export_status_and_download(page, out_dir=AUDIO_OUTPUT_DIR, timeout_sec=1800):
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    # optional info
    print(f"⏳ Waiting for export to finish (timeout {timeout_sec//60} min)...")

    try:
        await page.get_by_text(re.compile(r"^\s*Export status\s*$", re.I)).wait_for(timeout=20000)
    except Exception:
        pass

    drawer = await open_exports_drawer(page)

    deadline = time.time() + timeout_sec
    last_status = None

    while time.time() < deadline:
        await dismiss_popovers(page)

        btn = drawer.locator("button", has_text=re.compile(r"^\s*Download\s*$", re.I)).first
        if btn and await btn.count():
            try:
                if await btn.is_enabled():
                    await btn.scroll_into_view_if_needed()
                    async with page.expect_download(timeout=60000) as dli:
                        await btn.click()
                    dl = await dli.value
                    dest = str(Path(out_dir) / dl.suggested_filename)
                    await dl.save_as(dest)
                    print(f"📥 Downloaded: {dest}")
                    return dest
            except Exception:
                pass

        try:
            percent = drawer.locator("text=/\\b\\d+%\\s+completed\\b/i").last
            if await percent.count():
                txt = await percent.inner_text()
                if txt != last_status:
                    print(f"Export status: {txt}")
                    last_status = txt
        except Exception:
            pass

        await page.wait_for_timeout(2000)

    raise TimeoutError("Timed out waiting for the Download button to enable.")


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        # Login
        await page.goto(login_url, wait_until="domcontentloaded")
        await page.locator('input[type="email"]').fill(username)
        await page.locator('input[type="password"]').fill(password)
        try:
            await page.get_by_role("button", name=re.compile(r"(sign\s*in|log\s*in)", re.I)).click(timeout=5000)
        except Exception:
            await page.locator('input[type="password"]').press("Enter")

        try:
            await page.wait_for_url(re.compile(r"/app", re.I), timeout=20000)
        except Exception:
            await page.wait_for_selector("nav >> text=Studio", timeout=30000)

        # Studio → New audiobook → Upload → Create project → Export
        await go_to_studio(page)
        await click_new_audiobook(page)
        await upload_doc_and_create_project(page, doc_file)

        # Start export (tolerant: won’t raise if already started)
        await click_export(page)

        # Open exports drawer and wait for Download
        await wait_for_export_status_and_download(page, AUDIO_OUTPUT_DIR)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
