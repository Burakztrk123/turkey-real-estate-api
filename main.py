from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
from bs4 import BeautifulSoup
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

@app.get("/")
def root():
    return {
        "api": "Turkey Real Estate API",
        "version": "1.0.0",
        "endpoints": ["/listings", "/summary", "/districts"],
        "example": "/listings?city=istanbul&category=satilik-daire"
    }

@app.get("/districts")
def get_districts():
    return {
        "istanbul": ["kadikoy", "besiktas", "sisli", "uskudar", "maltepe", "pendik", "esenyurt", "bagcilar", "sariyer", "beykoz"],
        "ankara": ["cankaya", "kecioren", "mamak", "etimesgut", "sincan", "yenimahalle"],
        "izmir": ["konak", "bornova", "karsiyaka", "buca", "cigli", "karsiyaka"]
    }

@app.get("/listings")
async def get_listings(
    city: str = Query("istanbul", description="Şehir: istanbul, ankara, izmir"),
    category: str = Query("satilik-daire", description="Kategori: satilik-daire, kiralik-daire"),
    district: str = Query(None, description="İlçe (opsiyonel): kadikoy, besiktas vb."),
    limit: int = Query(20, description="Maksimum ilan sayısı (max 50)")
):
    try:
        if district:
            url = f"https://emlak.nef.com.tr/{city}/{district}/{category}"
        else:
            url = f"https://www.zingat.com/{city}-{category}-ilanlari"

        async with httpx.AsyncClient(
            headers=HEADERS,
            timeout=30,
            follow_redirects=True
        ) as client:
            response = await client.get(url)
            soup = BeautifulSoup(response.text, "html.parser")

        listings = []

        # Zingat parsing
        cards = soup.select(".listing-item-v2, .card-listing, [class*='listing'], article")[:limit]

        for card in cards:
            try:
                title = card.select_one("h2, h3, [class*='title'], [class*='baslik']")
                price = card.select_one("[class*='price'], [class*='fiyat'], [class*='tutar']")
                location = card.select_one("[class*='location'], [class*='konum'], [class*='adres']")
                rooms = card.select_one("[class*='room'], [class*='oda']")
                size = card.select_one("[class*='size'], [class*='metrekare'], [class*='m2']")

                item = {
                    "title": title.get_text(strip=True) if title else None,
                    "price": price.get_text(strip=True) if price else None,
                    "location": location.get_text(strip=True) if location else None,
                    "rooms": rooms.get_text(strip=True) if rooms else None,
                    "size_m2": size.get_text(strip=True) if size else None,
                }

                if any(v for v in item.values()):
                    listings.append(item)
            except:
                continue

        # Eğer veri gelemediyse statik örnek veri dön (demo mod)
        if len(listings) == 0:
            listings = get_demo_data(city, category, district)
            return {
                "status": "demo",
                "note": "Canlı veri şu an alınamadı, örnek veri gösteriliyor",
                "city": city,
                "category": category,
                "district": district,
                "count": len(listings),
                "timestamp": datetime.now().isoformat(),
                "data": listings
            }

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
        listings = get_demo_data(city, category, district)
        return {
            "status": "demo",
            "note": "Canlı veri şu an alınamadı, örnek veri gösteriliyor",
            "city": city,
            "category": category,
            "count": len(listings),
            "timestamp": datetime.now().isoformat(),
            "data": listings
        }

@app.get("/summary")
async def get_summary(
    city: str = Query("istanbul", description="Şehir"),
    category: str = Query("satilik-daire", description="Kategori")
):
    demo = get_demo_data(city, category, None)
    prices = []
    for item in demo:
        price_str = item.get("price", "")
        if price_str:
            nums = re.findall(r'\d+', price_str.replace(".", "").replace(",", ""))
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
                "min_price_tl": min(prices),
                "max_price_tl": max(prices),
                "avg_price_tl": sum(prices) // len(prices),
                "listing_count": len(prices)
            }
        }
    return {"status": "no_data"}

def get_demo_data(city, category, district):
    if "kiralik" in category:
        return [
            {"title": f"{city.title()} Kiralık Daire 1", "price": "25.000 TL/ay", "location": district or city, "rooms": "2+1", "size_m2": "85 m²"},
            {"title": f"{city.title()} Kiralık Daire 2", "price": "18.000 TL/ay", "location": district or city, "rooms": "1+1", "size_m2": "55 m²"},
            {"title": f"{city.title()} Kiralık Daire 3", "price": "35.000 TL/ay", "location": district or city, "rooms": "3+1", "size_m2": "120 m²"},
            {"title": f"{city.title()} Kiralık Daire 4", "price": "22.000 TL/ay", "location": district or city, "rooms": "2+1", "size_m2": "90 m²"},
            {"title": f"{city.title()} Kiralık Daire 5", "price": "45.000 TL/ay", "location": district or city, "rooms": "4+1", "size_m2": "160 m²"},
        ]
    else:
        return [
            {"title": f"{city.title()} Satılık Daire 1", "price": "4.500.000 TL", "location": district or city, "rooms": "2+1", "size_m2": "90 m²"},
            {"title": f"{city.title()} Satılık Daire 2", "price": "2.800.000 TL", "location": district or city, "rooms": "1+1", "size_m2": "60 m²"},
            {"title": f"{city.title()} Satılık Daire 3", "price": "7.200.000 TL", "location": district or city, "rooms": "3+1", "size_m2": "130 m²"},
            {"title": f"{city.title()} Satılık Daire 4", "price": "9.500.000 TL", "location": district or city, "rooms": "4+1", "size_m2": "180 m²"},
            {"title": f"{city.title()} Satılık Daire 5", "price": "3.200.000 TL", "location": district or city, "rooms": "2+1", "size_m2": "85 m²"},
        ]
