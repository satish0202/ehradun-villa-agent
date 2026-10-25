import asyncio
import re
import requests
import os
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# Environment Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

TARGET_URLS = [
    "https://www.99acres.com/4-bhk-villas-in-rajpur-road-dehradun-ffid",
    "https://www.99acres.com/4-bhk-villas-in-sahastradhara-road-dehradun-ffid",
    "https://www.magicbricks.com/villa-for-sale-in-malsi-dehradun-pppfs"
]

def send_alert(title, price, plot, link):
    message = (
        f"🏠 *DAILY DEHRADUN VILLA UPDATE*\n\n"
        f"📍 *Property:* {title}\n"
        f"💰 *Price:* ₹{price} Cr\n"
        f"📐 *Plot Size:* {plot} SqYd\n"
        f"🔗 [View Listing]({link})"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})

async def run_daily_check():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        for url in TARGET_URLS:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(2000)
                content = await page.content()
                soup = BeautifulSoup(content, "html.parser")
                
                # Parsing logic for listings under 30 days
                cards = soup.find_all("div", class_=re.compile(r"tuple|card|srp"))
                for card in cards:
                    text = card.get_text(separator=" ").strip()
                    
                    # Check recency (posted in last 30 days)
                    if any(k in text.lower() for k in ["today", "yesterday", "days ago", "weeks ago", "1 month ago"]):
                        # Extract price <= 5 Cr
                        price_match = re.search(r"₹\s*([\d\.]+)\s*Cr", text, re.IGNORECASE)
                        if price_match and float(price_match.group(1)) <= 5.0:
                            send_alert("Dehradun Villa Match", price_match.group(1), "180", url)
                            
            except Exception as e:
                print(f"Error fetching {url}: {e}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_daily_check())
