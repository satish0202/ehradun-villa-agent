import asyncio
import re
import os
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from twilio.rest import Client

# Criteria & Thresholds
MAX_BUDGET_CR = 5.0
MAX_PLOT_SQM = 250.0
MAX_PLOT_SQYD = 298.99

TARGET_URLS = [
    "https://www.99acres.com/4-bhk-villas-in-rajpur-road-dehradun-ffid",
    "https://www.99acres.com/4-bhk-villas-in-sahastradhara-road-dehradun-ffid",
    "https://www.magicbricks.com/villa-for-sale-in-malsi-dehradun-pppfs"
]

# Twilio WhatsApp Credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER") # e.g. whatsapp:+14155238886
YOUR_PHONE_NUMBER = os.getenv("YOUR_PHONE_NUMBER")           # e.g. whatsapp:+919876543210

def is_listed_within_30_days(text: str) -> bool:
    """Ensures listing was posted within the last 30 days."""
    text_lower = text.lower()
    recent_keywords = ["today", "yesterday", "days ago", "weeks ago", "1 month ago", "1mo ago"]
    if any(keyword in text_lower for keyword in recent_keywords):
        weeks_match = re.search(r"(\d+)\s*w\s*ago", text_lower)
        if weeks_match and int(weeks_match.group(1)) > 4:
            return False
        return True
    return False

def send_whatsapp_alert(title: str, price: float, plot_sqyd: float, url: str):
    """Sends immediate WhatsApp notification via Twilio."""
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER, YOUR_PHONE_NUMBER]):
        print("[Warning] WhatsApp Twilio secrets missing. Skipping alert.")
        return

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message_body = (
            f"🏡 *NEW DEHRADUN VILLA MATCH FOUND* 🏡\n\n"
            f"📍 *Listing:* {title}\n"
            f"💰 *Price:* ₹{price} Cr\n"
            f"📐 *Plot Size:* ~{plot_sqyd} SqYd (<= 250 SqM)\n"
            f"🏡 *Gated Community:* Yes | *Private Garden:* Yes\n"
            f"⏰ *Recency:* Posted within last 30 days\n\n"
            f"🔗 *Link:* {url}"
        )

        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=YOUR_PHONE_NUMBER,
            body=message_body
        )
        print(f"[WhatsApp Alert Sent] Message SID: {message.sid}")
    except Exception as e:
        print(f"[WhatsApp Error] Failed to send message: {e}")

async def run_scraper():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_user_agent(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        for url in TARGET_URLS:
            print(f"[Agent] Scraping: {url}")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
                content = await page.content()
                soup = BeautifulSoup(content, "html.parser")
                
                cards = soup.find_all("div", class_=re.compile(r"tuple|card|srp"))
                for card in cards:
                    card_text = card.get_text(separator=" ").strip()

                    # 1. Recency Check
                    if not is_listed_within_30_days(card_text):
                        continue

                    # 2. Price Check <= 5 Cr
                    price_match = re.search(r"₹\s*([\d\.]+)\s*(Cr|Lakh|L)", card_text, re.IGNORECASE)
                    price_cr = 0.0
                    if price_match:
                        val = float(price_match.group(1))
                        unit = price_match.group(2).lower()
                        price_cr = val if "cr" in unit else val / 100.0

                    if price_cr == 0.0 or price_cr > MAX_BUDGET_CR:
                        continue

                    # 3. Plot Area Check <= 250 SqM / 298 SqYd
                    sqyd_match = re.search(r"(\d+)\s*(sqyd|sq.yd|sq yards)", card_text, re.IGNORECASE)
                    plot_sqyd = float(sqyd_match.group(1)) if sqyd_match else 180.0

                    if plot_sqyd > MAX_PLOT_SQYD:
                        continue

                    # 4. Gated & Garden Check
                    is_gated = bool(re.search(r"gated|society|enclave|colony", card_text, re.IGNORECASE))
                    has_garden = bool(re.search(r"garden|lawn|park|green", card_text, re.IGNORECASE))

                    if is_gated and has_garden:
                        title_clean = card_text[:70].replace("\n", " ") + "..."
                        send_whatsapp_alert(title_clean, price_cr, plot_sqyd, url)

            except Exception as e:
                print(f"[Scraper Error] Failed on {url}: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_scraper())
