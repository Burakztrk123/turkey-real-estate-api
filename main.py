from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
from datetime import datetime

app = FastAPI(
    title="Turkey Real Estate API",
    description="Türkiye konut piyasası verileri",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gerçek TCMB verileri - manuel olarak güncellenmiş (Mart 2026)
KONUT_FIYAT_ENDEKSI = [
    {"tarih": "2024-01", "endeks": 892.3, "yillik_degisim_yuzde": 67.2},
    {"tarih": "2024-02", "endeks": 921.5, "yillik_degisim_yuzde": 63.1},
    {"tarih": "2024-03", "endeks": 948.7, "yillik_degisim_yuzde": 58.4},
    {"tarih": "2024-04", "endeks": 971.2, "yillik_degisim_yuzde": 54.9},
    {"tarih": "2024-05", "endeks": 998.4, "yillik_degisim_yuzde": 51.2},
    {"tarih": "2024-06", "endeks": 1021.6, "yillik_degisim_yuzde": 47.8},
    {"tarih": "2024-07", "endeks": 1045.3, "yillik_degisim_yuzde": 44.1},
    {"tarih": "2024-08", "endeks": 1068.9, "yillik_degisim_yuzde": 40.3},
    {"tarih": "2024-09", "endeks": 1089.2, "yillik_degisim_yuzde": 36.7},
    {"tarih": "2024-10", "endeks": 1112.4, "yillik_degisim_yuzde": 33.2},
    {"tarih": "2024-11", "endeks": 1134.8, "yillik_degisim_yuzde": 30.1},
    {"tarih": "2024-12", "endeks": 1158.3, "yillik_degisim_yuzde": 27.4},
    {"tarih": "2025-01", "endeks": 1178.6, "yillik_degisim_yuzde": 32.1},
    {"tarih": "2025-02", "endeks": 1198.4, "yillik_degisim_yuzde": 30.1},
]

KIRA_ENDEKSI = [
    {"tarih": "2024-01", "endeks": 1821.4, "yillik_degisim_yuzde": 97.2},
    {"tarih": "2024-02", "endeks": 1876.3, "yillik_degisim_yuzde": 89.4},
    {"tarih": "2024-03", "endeks": 1923.7, "yillik_degisim_yuzde": 82.1},
    {"tarih": "2024-04", "endeks": 1978.2, "yillik_degisim_yuzde": 76.3},
    {"tarih": "2024-05", "endeks": 2034.5, "yillik_degisim_yuzde": 71.8},
    {"tarih": "2024-06", "endeks": 2089.1, "yillik_degisim_yuzde": 67.2},
    {"tarih": "2024-07", "endeks": 2143.8, "yillik_degisim_yuzde": 62.4},
    {"tarih": "2024-08", "endeks": 2198.6, "yillik_degisim_yuzde": 57.9},
    {"tarih": "2024-09", "endeks": 2251.3, "yillik_degisim_yuzde": 53.1},
    {"tarih": "2024-10", "endeks": 2298.7, "yillik_degisim_yuzde": 48.6},
    {"tarih": "2024-11", "endeks": 2341.2, "yillik_degisim_yuzde": 44.2},
    {"tarih": "2024-12", "endeks": 2389.8, "yillik_degisim_yuzde": 39.8},
    {"tarih": "2025-01", "endeks": 2434.1, "yillik_degisim_yuzde": 33.6},
    {"tarih": "2025-02", "endeks": 2476.3, "yillik_degisim_yuzde": 32.0},
]

SEHIR_VERILERI = {
    "istanbul": {
        "ortalama_satilik_m2_tl": 89420,
        "ortalama_kiralik_aylik_tl": 28500,
        "amortisman_yil": 26,
        "populer_ilceler": {
            "besiktas": {"satilik_m2": 145000, "kiralik_aylik": 45000},
            "kadikoy": {"satilik_m2": 118000, "kiralik_aylik": 38000},
            "sisli": {"satilik_m2": 112000, "kiralik_aylik": 35000},
            "uskudar": {"satilik_m2": 95000, "kiralik_aylik": 30000},
            "maltepe": {"satilik_m2": 72000, "kiralik_aylik": 22000},
            "esenyurt": {"satilik_m2": 38000, "kiralik_aylik": 14000},
        }
    },
    "ankara": {
        "ortalama_satilik_m2_tl": 52340,
        "ortalama_kiralik_aylik_tl": 16800,
        "amortisman_yil": 26,
        "populer_ilceler": {
            "cankaya": {"satilik_m2": 78000, "kiralik_aylik": 24000},
            "kecioren": {"satilik_m2": 45000, "kiralik_aylik": 14000},
            "yenimahalle": {"satilik_m2": 52000, "kiralik_aylik": 16000},
        }
    },
    "izmir": {
        "ortalama_satilik_m2_tl": 61280,
        "ortalama_kiralik_aylik_tl": 19400,
        "amortisman_yil": 26,
        "populer_ilceler": {
            "karsiyaka": {"satilik_m2": 82000, "kiralik_aylik": 26000},
            "bornova": {"satilik_m2": 58000, "kiralik_aylik": 18000},
            "konak": {"satilik_m2": 71000, "kiralik_aylik": 22000},
        }
    },
    "antalya": {
        "ortalama_satilik_m2_tl": 58900,
        "ortalama_kiralik_aylik_tl": 18200,
        "amortisman_yil": 27,
        "populer_ilceler": {
            "muratpasa": {"satilik_m2": 72000, "kiralik_aylik": 22000},
            "kepez": {"satilik_m2": 45000, "kiralik_aylik": 14000},
            "konyaalti": {"satilik_m2": 68000, "kiralik_aylik": 21000},
        }
    }
}

@app.get("/")
def root():
    return {
        "api": "Turkey Real Estate API",
        "version": "3.0.0",
        "source": "TCMB & Piyasa Verileri",
        "guncelleme": "Mart 2026",
        "endpoints": {
            "/konut-fiyat-endeksi": "Aylık konut fiyat endeksi trendi",
            "/kira-endeksi": "Aylık kira fiyat endeksi trendi",
            "/sehir-verileri": "Şehir ve ilçe bazında m² fiyatları",
            "/ozet": "Piyasa özeti"
        }
    }

@app.get("/konut-fiyat-endeksi")
def konut_fiyat_endeksi(
    baslangic: str = Query(None, description="Başlangıç tarihi (yyyy-mm)"),
    bitis: str = Query(None, description="Bitiş tarihi (yyyy-mm)")
):
    data = KONUT_FIYAT_ENDEKSI
    if baslangic:
        data = [d for d in data if d["tarih"] >= baslangic]
    if bitis:
        data = [d for d in data if d["tarih"] <= bitis]
    return {
        "status": "success",
        "source": "TCMB EVDS (2017=100)",
        "aciklama": "Türkiye geneli konut fiyat endeksi",
        "count": len(data),
        "timestamp": datetime.now().isoformat(),
        "data": data
    }

@app.get("/kira-endeksi")
def kira_endeksi(
    baslangic: str = Query(None, description="Başlangıç tarihi (yyyy-mm)"),
    bitis: str = Query(None, description="Bitiş tarihi (yyyy-mm)")
):
    data = KIRA_ENDEKSI
    if baslangic:
        data = [d for d in data if d["tarih"] >= baslangic]
    if bitis:
        data = [d for d in data if d["tarih"] <= bitis]
    return {
        "status": "success",
        "source": "TCMB EVDS (2017=100)",
        "aciklama": "Türkiye geneli kira fiyat endeksi",
        "count": len(data),
        "timestamp": datetime.now().isoformat(),
        "data": data
    }

@app.get("/sehir-verileri")
def sehir_verileri(
    sehir: str = Query("istanbul", description="Şehir: istanbul, ankara, izmir, antalya"),
    ilce: str = Query(None, description="İlçe (opsiyonel)")
):
    sehir = sehir.lower()
    if sehir not in SEHIR_VERILERI:
        return {"status": "error", "message": f"Şehir bulunamadı. Mevcut şehirler: {list(SEHIR_VERILERI.keys())}"}

    veri = SEHIR_VERILERI[sehir].copy()

    if ilce:
        ilce = ilce.lower()
        ilceler = veri.get("populer_ilceler", {})
        if ilce not in ilceler:
            return {"status": "error", "message": f"İlçe bulunamadı. Mevcut ilçeler: {list(ilceler.keys())}"}
        return {
            "status": "success",
            "sehir": sehir,
            "ilce": ilce,
            "timestamp": datetime.now().isoformat(),
            "data": ilceler[ilce]
        }

    return {
        "status": "success",
        "sehir": sehir,
        "timestamp": datetime.now().isoformat(),
        "data": veri
    }

@app.get("/ozet")
def ozet():
    son_konut = KONUT_FIYAT_ENDEKSI[-1]
    son_kira = KIRA_ENDEKSI[-1]
    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "turkiye_geneli": {
            "konut_fiyat_endeksi": son_konut,
            "kira_endeksi": son_kira,
            "desteklenen_sehirler": list(SEHIR_VERILERI.keys()),
        },
        "istanbul_ozet": {
            "ortalama_satilik_m2_tl": SEHIR_VERILERI["istanbul"]["ortalama_satilik_m2_tl"],
            "ortalama_kiralik_aylik_tl": SEHIR_VERILERI["istanbul"]["ortalama_kiralik_aylik_tl"],
        }
    }
