import puppeteer from 'puppeteer-core';
import path from 'path';

const EDGE_PATH = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE_URL = 'http://localhost:5173';
const API_BASE = 'http://127.0.0.1:8000/api/v1';
const ARTIFACT_DIR = 'C:\\Users\\saleh\\.gemini\\antigravity-ide\\brain\\9763cabc-3bfd-42e9-9e71-aea76446f9fa';
const WORKSPACE_DIR = 'f:\\New folder';

async function getAuthToken(email, password = 'Sales123!') {
  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const data = await resp.json();
  return data.access_token;
}

async function run() {
  const browser = await puppeteer.launch({
    executablePath: EDGE_PATH,
    headless: 'new',
    defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 1.25 },
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
  });

  try {
    const token = await getAuthToken('saleh@alphapromena.com', 'Sales123!');
    const page = await browser.newPage();
    await page.setCookie({
      name: 'access_token',
      value: token,
      domain: 'localhost',
      path: '/',
      httpOnly: true,
    });

    await page.goto(`${BASE_URL}/contacts`, { waitUntil: 'networkidle0' });
    await new Promise((r) => setTimeout(r, 2000));

    // Select 'Re Call' on the attempt dropdown in table body
    await page.waitForSelector('table tbody tr select');
    await page.evaluate(() => {
      const select = document.querySelector('table tbody tr select');
      if (select) {
        select.value = 'Re Call';
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });

    await new Promise((r) => setTimeout(r, 1500));
    await page.screenshot({ path: path.join(ARTIFACT_DIR, '8_recall_scheduling.png') });
    await page.screenshot({ path: path.join(WORKSPACE_DIR, '8_recall_scheduling.png') });
    console.log('Saved open recall modal screenshot!');
    await page.close();
  } finally {
    await browser.close();
  }
}

run().catch(console.error);
