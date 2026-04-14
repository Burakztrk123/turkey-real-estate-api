from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
from datetime import datetime

app = FastAPI(
    title="Turkey Real Estate API",
    description="Türkiye konut fiyat endeksi - TCMB resmi verileri",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TCMB_API_KEY = "38kL5GlwuQ"
TCMB_BASE = "https://evds2.tcmb.gov.tr/service/evds"

@app.get("/")
def root():
    return {
        "api": "Turkey Real Estate API",
        "version": "2.0.0",
        "source": "TCMB - Türkiye Cumhuriyet Merkez Bankası",
        "endpoints": {
            "/konut-fiyat-endeksi": "Aylık konut fiyat endeksi",
            "/kira-endeksi": "Kira fiyat endeksi",
            "/konut-satis": "Konut satış istatistikleri",
            "/ozet": "Tüm verilerin özeti"
        }
    }

@app.get("/konut-fiyat-endeksi")
async def konut_fiyat_endeksi(
    baslangic: str = Query("01-01-2023", description="Başlangıç tarihi (gg-aa-yyyy)"),
    bitis: str = Query("01-01-2025", description="Bitiş tarihi (gg-aa-yyyy)")
):
    url = f"{TCMB_BASE}/series=TP.HKFE01&startDate={baslangic}&endDate={bitis}&type=json&key={TCMB_API_KEY}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            data = r.json()

        items = data.get("items", [])
        result = []
        for item in items:
            tarih = item.get("Tarih", "")
            deger = item.get("TP_HKFE01", None)
            if deger:
                result.append({
                    "tarih": tarih,
                    "konut_fiyat_endeksi": float(deger)
                })

        return {
            "status": "success",
            "source": "TCMB EVDS",
            "aciklama": "Türkiye geneli konut fiyat endeksi (2017=100)",
            "count": len(result),
            "timestamp": datetime.now().isoformat(),
            "data": result
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/kira-endeksi")
async def kira_endeksi(
    baslangic: str = Query("01-01-2023", description="Başlangıç tarihi"),
    bitis: str = Query("01-01-2025", description="Bitiş tarihi")
):
    url = f"{TCMB_BASE}/series=TP.HKFE03&startDate={baslangic}&endDate={bitis}&type=json&key={TCMB_API_KEY}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            data = r.json()

        items = data.get("items", [])
        result = []
        for item in items:
            tarih = item.get("Tarih", "")
            deger = item.get("TP_HKFE03", None)
            if deger:
                result.append({
                    "tarih": tarih,
                    "kira_endeksi": float(deger)
                })

        return {
            "status": "success",
            "source": "TCMB EVDS",
            "aciklama": "Türkiye geneli kira fiyat endeksi (2017=100)",
            "count": len(result),
            "timestamp": datetime.now().isoformat(),
            "data": result
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/konut-satis")
async def konut_satis(
    baslangic: str = Query("01-01-2023", description="Başlangıç tarihi"),
    bitis: str = Query("01-01-2025", description="Bitiş tarihi")
):
    url = f"{TCMB_BASE}/series=TP.AKONUTSAT01&startDate={baslangic}&endDate={bitis}&type=json&key={TCMB_API_KEY}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
            data = r.json()

        items = data.get("items", [])
        result = []
        for item in items:
            tarih = item.get("Tarih", "")
            deger = item.get("TP_AKONUTSAT01", None)
            if deger:
                result.append({
                    "tarih": tarih,
                    "konut_satis_adedi": int(float(deger))
                })

        return {
            "status": "success",
            "source": "TCMB EVDS",
            "aciklama": "Türkiye geneli aylık konut satış adedi",
            "count": len(result),
            "timestamp": datetime.now().isoformat(),
            "data": result
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/ozet")
async def ozet():
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url1 = f"{TCMB_BASE}/series=TP.HKFE01&startDate=01-01-2024&endDate=01-01-2025&type=json&key={TCMB_API_KEY}"
            url2 = f"{TCMB_BASE}/series=TP.HKFE03&startDate=01-01-2024&endDate=01-01-2025&type=json&key={TCMB_API_KEY}"
            url3 = f"{TCMB_BASE}/series=TP.AKONUTSAT01&startDate=01-01-2024&endDate=01-01-2025&type=json&key={TCMB_API_KEY}"

            r1 = await client.get(url1)
            r2 = await client.get(url2)
            r3 = await client.get(url3)

        d1 = r1.json().get("items", [])
        d2 = r2.json().get("items", [])
        d3 = r3.json().get("items", [])

        son_konut = d1[-1] if d1 else {}
        son_kira = d2[-1] if d2 else {}
        son_satis = d3[-1] if d3 else {}

        return {
            "status": "success",
            "source": "TCMB EVDS",
            "timestamp": datetime.now().isoformat(),
            "son_veriler": {
                "konut_fiyat_endeksi": {
                    "tarih": son_konut.get("Tarih"),
                    "deger": son_konut.get("TP_HKFE01")
                },
                "kira_endeksi": {
                    "tarih": son_kira.get("Tarih"),
                    "deger": son_kira.get("TP_HKFE03")
                },
                "konut_satis": {
                    "tarih": son_satis.get("Tarih"),
                    "deger": son_satis.get("TP_AKONUTSAT01")
                }
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
