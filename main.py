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

HEADERS = {
    "key": TCMB_API_KEY
}

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

async def tcmb_getir(seri: str, baslangic: str, bitis: str):
    url = f"{TCMB_BASE}/series={seri}&startDate={baslangic}&endDate={bitis}&type=json"
    async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
        r = await client.get(url)
        return r.json()

@app.get("/konut-fiyat-endeksi")
async def konut_fiyat_endeksi(
    baslangic: str = Query("01-01-2023", description="Başlangıç tarihi (gg-aa-yyyy)"),
    bitis: str = Query("01-01-2025", description="Bitiş tarihi (gg-aa-yyyy)")
):
    try:
        data = await tcmb_getir("TP.HKFE01", baslangic, bitis)
        items = data.get("items", [])
        result = []
        for item in items:
            deger = item.get("TP_HKFE01")
            if deger and deger != "":
                result.append({
                    "tarih": item.get("Tarih"),
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
    try:
        data = await tcmb_getir("TP.HKFE03", baslangic, bitis)
        items = data.get("items", [])
        result = []
        for item in items:
            deger = item.get("TP_HKFE03")
            if deger and deger != "":
                result.append({
                    "tarih": item.get("Tarih"),
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
    try:
        data = await tcmb_getir("TP.AKONUTSAT01", baslangic, bitis)
        items = data.get("items", [])
        result = []
        for item in items:
            deger = item.get("TP_AKONUTSAT01")
            if deger and deger != "":
                result.append({
                    "tarih": item.get("Tarih"),
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
        d1 = await tcmb_getir("TP.HKFE01", "01-01-2024", "01-01-2025")
        d2 = await tcmb_getir("TP.HKFE03", "01-01-2024", "01-01-2025")
        d3 = await tcmb_getir("TP.AKONUTSAT01", "01-01-2024", "01-01-2025")

        i1 = d1.get("items", [])
        i2 = d2.get("items", [])
        i3 = d3.get("items", [])

        son_konut = i1[-1] if i1 else {}
        son_kira = i2[-1] if i2 else {}
        son_satis = i3[-1] if i3 else {}

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
