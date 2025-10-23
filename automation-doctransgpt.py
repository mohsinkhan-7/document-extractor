import asyncio
from playwright.async_api import async_playwright
import os, re, time
from pathlib import Path

# Configuration
username = "AWIYL@mbrl.ae"
password = "@MBRLWorld2024"
login_url = "https://doctransgpt.com/signin"

# Input and output
DOC_FILE = r"/Users/dell/PycharmProjects/document-extractor/_كتاب العبرات (1).pdf"
OUTPUT_DIR = r"/Users/dell/PycharmProjects/document-extractor/translated"


async def click_translate_arrow(page):
    try:
        btn = page.locator("#translate-document-button button").first
        await btn.wait_for(state="visible", timeout=10000)
        await btn.scroll_into_view_if_needed()
        await btn.click(force=True, timeout=3000)
        print("✅ Translate button clicked successfully")
        return
    except Exception:
        pass

    try:
        anchor = page.locator("#translate-document-button").first
        await anchor.wait_for(state="visible", timeout=5000)
        box = await anchor.bounding_box()
        if box:
            await page.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
            print("⚠️ Fallback: clicked anchor center")
            return
    except Exception:
        pass

    raise RuntimeError("❌ Translate arrow button not found")


async def go_to_documents(page):
    print("➡️ Navigating to Documents tab...")
    await page.wait_for_load_state("domcontentloaded")

    for loc in [
        page.get_by_role("link", name=re.compile(r"^\s*Documents?\s*$", re.I)).first,
        page.get_by_role("tab", name=re.compile(r"^\s*Documents?\s*$", re.I)).first,
        page.locator("a:has-text('Documents'), button:has-text('Documents')").first,
    ]:
        try:
            await loc.wait_for(state="visible", timeout=5000)
            await loc.click()
            print("✅ Clicked Documents tab")
            break
        except Exception as e:
            print(f"⚠️ Documents locator failed: {e}")

    try:
        await page.wait_for_url(re.compile(r"/documents/?$", re.I), timeout=8000)
    except Exception:
        print("⚠️ Direct navigation to /documents")
        await page.goto("https://doctransgpt.com/documents", wait_until="domcontentloaded")

    await page.get_by_text(re.compile(r"click to upload", re.I)).first.wait_for(state="visible", timeout=15000)
    print("✅ Documents tab ready")


async def upload_single_document(page, filepath):
    if not Path(filepath).exists():
        raise FileNotFoundError(f"❌ File not found: {filepath}")

    dropzone = page.get_by_text(re.compile(r"click to upload", re.I)).first
    dz_input = dropzone.locator('input[type="file"]')
    file_input = dz_input.first if await dz_input.count() > 0 else page.locator('input[type="file"]').first
    await file_input.wait_for(state="attached", timeout=10000)

    name = Path(filepath).name
    print(f"📤 Uploading: {name}")
    await file_input.set_input_files(filepath)

    try:
        await page.locator(f"span:has-text('{name[:20]}')").first.wait_for(state="visible", timeout=15000)
        print(f"✅ Upload confirmed for {name}")
    except Exception:
        try:
            await page.locator("div:has-text('.docx')").first.wait_for(state="visible", timeout=15000)
            print(f"⚠️ Upload detected (generic) for {name}")
        except Exception:
            print(f"❌ Could not confirm upload of {name}, continuing anyway")


async def go_to_history(page):
    print("➡️ Navigating to History tab...")
    for loc in [
        page.get_by_role("link", name=re.compile(r"^\s*History\s*$", re.I)).first,
        page.get_by_role("tab", name=re.compile(r"^\s*History\s*$", re.I)).first,
        page.locator("a:has-text('History'), button:has-text('History')").first,
    ]:
        try:
            await loc.click(timeout=2000)
            print("✅ Clicked History tab")
            break
        except Exception:
            pass

    try:
        await page.wait_for_url(re.compile(r"/history/?$", re.I), timeout=8000)
    except Exception:
        await page.goto("https://doctransgpt.com/history", wait_until="domcontentloaded")

    await page.wait_for_load_state("domcontentloaded")
    print("📜 Navigated to History tab")


async def wait_for_completion_and_download(page, filename: str, download_dir: str,
                                           timeout_sec: int = 1800, refresh_sec: int = 30):
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    orig_name = Path(filename).stem  # filename without extension
    ext = Path(filename).suffix

    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            btn = page.locator("a:has-text('Download translation')").first
            if await btn.count() > 0:
                await btn.wait_for(state="visible", timeout=10000)
                print("✅ Found 'Download translation' link, waiting 2s for stability...")
                await page.wait_for_timeout(2000)
                async with page.expect_download(timeout=60000) as dli:
                    await btn.click()
                dl = await dli.value

                # Rename the file
                dest = Path(download_dir) / f"{orig_name}_translated{ext}"
                await dl.save_as(str(dest))
                print(f"📥 Downloaded and saved as: {dest}")
                return str(dest)
            else:
                print("⏳ Still waiting: no download link yet")
        except Exception as e:
            print(f"⚠️ Still waiting... {e}")

        await page.wait_for_timeout(refresh_sec * 1000)
        try:
            if await page.locator("a:has-text('Download translation')").count() == 0:
                print("🔄 Refreshing page to check again...")
                await page.reload(wait_until="domcontentloaded")
        except Exception:
            pass

    raise TimeoutError("Timed out waiting for 'Download translation' link.")


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="msedge", headless=False)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        # === Login ===
        await page.goto(login_url, wait_until="domcontentloaded")
        await page.wait_for_selector('input[type="email"], input[name*="mail" i]', timeout=20000)
        print("✅ Login page loaded")

        email_sel = 'input[type="email"], input[name*="mail" i], input[id*="mail" i], input[placeholder*="mail" i]'
        pwd_sel = 'input[type="password"], input[name*="pass" i], input[id*="pass" i], input[placeholder*="pass" i]'

        email_input = page.locator(email_sel).first
        pwd_input = page.locator(pwd_sel).first

        await email_input.wait_for(state="visible", timeout=20000)
        await email_input.fill(username)
        print("✅ Email entered")

        await pwd_input.fill(password)
        print("✅ Password entered")

        try:
            await page.get_by_role("button", name=re.compile(r"(sign\s*in|log\s*in)", re.I)).click(timeout=5000)
            print("✅ Clicked sign in button")
        except Exception:
            print("⚠️ Falling back: pressing Enter")
            await pwd_input.press("Enter")

        # Upload only DOC_FILE
        await go_to_documents(page)
        await upload_single_document(page, DOC_FILE)
        await click_translate_arrow(page)

        # Go to History and download result
        await go_to_history(page)
        await wait_for_completion_and_download(page, Path(DOC_FILE).name, OUTPUT_DIR)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
