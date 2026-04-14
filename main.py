from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
from bs4 import BeautifulSoup
import asyncio
import json
from datetime import datetime
import re

app = FastAPI(
    title="Turkey Real Estate API",
    description="Türkiye emlak verisi API'si - İlçe bazında fiyat trendleri",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

@app.get("/")
def root():
    return {
        "api": "Turkey Real Estate API",
        "version": "1.0.0",
        "endpoints": ["/listings", "/summary", "/districts"]
    }

@app.get("/listings")
async def get_listings(
    city: str = Query("istanbul", description="Şehir (istanbul, ankara, izmir)"),
    category: str = Query("satilik-daire", description="Kategori"),
    district: str = Query(None, description="İlçe (opsiyonel)"),
    limit: int = Query(20, description="Maksimum ilan sayısı")
):
    url = f"https://www.hepsiemlak.com/{city}-{category}"
    if district:
        url = f"https://www.hepsiemlak.com/{city}-{district}-{category}"

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
            response = await client.get(url)
            soup = BeautifulSoup(response.text, "html.parser")

        listings = []
        cards = soup.select(".listing-item, .searchResultsItem, [class*='listing']")[:limit]

        for card in cards:
            try:
                title = card.select_one("[class*='title'], h3, h2")
                price = card.select_one("[class*='price'], .fz24-text")
                location = card.select_one("[class*='location'], [class*='address']")
                detail = card.select_one("[class*='detail'], [class*='feature']")

                listings.append({
                    "title": title.get_text(strip=True) if title else None,
                    "price": price.get_text(strip=True) if price else None,
                    "location": location.get_text(strip=True) if location else None,
                    "details": detail.get_text(strip=True) if detail else None,
                })
            except:
                continue

        return {
            "status": "success",
            "city": city,
            "category": category,
            "district": district,
            "count": len(listings),
            "timestamp": datetime.now().isoformat(),
            "data": listings
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/districts")
def get_districts():
    return {
        "istanbul": ["kadikoy", "besiktas", "sisli", "uskudar", "maltepe", "pendik", "esenyurt", "bagcilar"],
        "ankara": ["cankaya", "kecioren", "mamak", "etimesgut", "sincan"],
        "izmir": ["konak", "bornova", "karsiyaka", "buca", "cigli"]
    }

@app.get("/summary")
async def get_summary(
    city: str = Query("istanbul", description="Şehir"),
    category: str = Query("satilik-daire", description="Kategori")
):
    url = f"https://www.hepsiemlak.com/{city}-{category}"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
            response = await client.get(url)
            soup = BeautifulSoup(response.text, "html.parser")

        prices = []
        for el in soup.select("[class*='price']"):
            text = el.get_text(strip=True).replace(".", "").replace("TL", "").replace(" ", "")
            nums = re.findall(r'\d+', text)
            if nums:
                try:
                    prices.append(int(nums[0]))
                except:
                    pass

        if prices:
            return {
                "status": "success",
                "city": city,
                "category": category,
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "min_price": min(prices),
                    "max_price": max(prices),
                    "avg_price": sum(prices) // len(prices),
                    "listing_count": len(prices)
                }
            }
        return {"status": "no_data", "message": "Veri bulunamadı"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
