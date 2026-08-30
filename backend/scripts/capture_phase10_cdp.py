import asyncio
import json
import os
import subprocess
import time
import urllib.request
import websockets
import base64

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9230
ARTIFACTS_DIR = r"C:\Users\saleh\.gemini\antigravity-ide\brain\9763cabc-3bfd-42e9-9e71-aea76446f9fa"

async def send_cdp(ws, method, params=None):
    msg_id = int(time.time() * 1000) % 1000000
    payload = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(payload))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == msg_id:
            return data.get("result", {})

async def capture_screen(ws, filename):
    res = await send_cdp(ws, "Page.captureScreenshot", {"format": "png"})
    img_data = base64.b64decode(res["data"])
    filepath = os.path.join(ARTIFACTS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(img_data)
    print(f"Captured {filename} ({len(img_data)} bytes)", flush=True)

async def run():
    print("Starting Edge on port 9230...", flush=True)
    edge_proc = subprocess.Popen([
        EDGE_PATH,
        f"--remote-debugging-port={PORT}",
        "--headless=new",
        "--disable-gpu",
        "--window-size=1440,900",
        "http://localhost:5173/login"
    ])
    time.sleep(3)

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json") as resp:
            targets = json.loads(resp.read().decode())
            ws_url = targets[0]["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, ping_interval=None) as ws:
            await send_cdp(ws, "Page.enable")
            await send_cdp(ws, "Runtime.enable")
            await send_cdp(ws, "DOM.enable")

            # 1. Login as Saleh
            print("1. Logging in as Saleh...", flush=True)
            await asyncio.sleep(2)
            await send_cdp(ws, "Runtime.evaluate", {"expression": """
                const emailInput = document.querySelector('#login-email');
                const passInput = document.querySelector('#login-password');
                const submitBtn = document.querySelector('#login-submit');
                if (emailInput && passInput && submitBtn) {
                    emailInput.value = 'saleh@alphapromena.com';
                    emailInput.dispatchEvent(new Event('input', { bubbles: true }));
                    passInput.value = 'Sales123!';
                    passInput.dispatchEvent(new Event('input', { bubbles: true }));
                    submitBtn.click();
                }
            """})
            await asyncio.sleep(3)

            # 2. Click Contacts in Sidebar (client-side SPA navigation)
            print("2. Clicking Contacts in Sidebar...", flush=True)
            await send_cdp(ws, "Runtime.evaluate", {"expression": """
                const contactsLink = document.querySelector('a[href="/contacts"]');
                if (contactsLink) contactsLink.click();
            """})
            await asyncio.sleep(3)
            await capture_screen(ws, "phase10_saleh_contacts_attempts.png")

            # 3. Filter STC Bank
            print("3. Filtering for STC Bank...", flush=True)
            await send_cdp(ws, "Runtime.evaluate", {"expression": """
                const input = document.querySelector('input[type="text"], input[type="search"]');
                if (input) {
                    input.value = 'stc Bank';
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            """})
            await asyncio.sleep(3)
            await capture_screen(ws, "phase10_stc_bank_attempts.png")

            print("[OK] Saleh screenshots captured successfully!", flush=True)

    finally:
        edge_proc.terminate()

if __name__ == "__main__":
    asyncio.run(run())
