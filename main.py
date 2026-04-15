"""
Turkey Real Estate API — v4.0.0
Veri kaynağı: TCMB EVDS (GitHub Actions ile haftalık güncellenir)
"""

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pathlib import Path
import json

# ---------------------------------------------------------------------------
# Uygulama
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Turkey Real Estate API",
    description=(
        "Türkiye konut piyasası verileri. "
        "Kaynak: TCMB EVDS — her hafta otomatik güncellenir."
    ),
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Veri yükleme
# ---------------------------------------------------------------------------

DATA_FILE = Path(__file__).parent / "data" / "evds_data.json"

# Şehir bazlı statik veriler (listing fiyatları piyasa ortalaması)
SEHIR_VERILERI = {
    "istanbul": {
        "ortalama_satilik_m2_tl": 89420,
        "ortalama_kiralik_aylik_tl": 28500,
        "amortisman_yil": 26,
        "populer_ilceler": {
            "besiktas":  {"satilik_m2": 145000, "kiralik_aylik": 45000},
            "kadikoy":   {"satilik_m2": 118000, "kiralik_aylik": 38000},
            "sisli":     {"satilik_m2": 112000, "kiralik_aylik": 35000},
            "uskudar":   {"satilik_m2": 95000,  "kiralik_aylik": 30000},
            "maltepe":   {"satilik_m2": 72000,  "kiralik_aylik": 22000},
            "esenyurt":  {"satilik_m2": 38000,  "kiralik_aylik": 14000},
        },
    },
    "ankara": {
        "ortalama_satilik_m2_tl": 52340,
        "ortalama_kiralik_aylik_tl": 16800,
        "amortisman_yil": 26,
        "populer_ilceler": {
            "cankaya":     {"satilik_m2": 78000, "kiralik_aylik": 24000},
            "kecioren":    {"satilik_m2": 45000, "kiralik_aylik": 14000},
            "yenimahalle": {"satilik_m2": 52000, "kiralik_aylik": 16000},
            "etimesgut":   {"satilik_m2": 48000, "kiralik_aylik": 15000},
            "mamak":       {"satilik_m2": 40000, "kiralik_aylik": 12000},
        },
    },
    "izmir": {
        "ortalama_satilik_m2_tl": 61280,
        "ortalama_kiralik_aylik_tl": 19400,
        "amortisman_yil": 26,
        "populer_ilceler": {
            "karsiyaka": {"satilik_m2": 82000, "kiralik_aylik": 26000},
            "bornova":   {"satilik_m2": 58000, "kiralik_aylik": 18000},
            "konak":     {"satilik_m2": 71000, "kiralik_aylik": 22000},
            "buca":      {"satilik_m2": 52000, "kiralik_aylik": 16000},
            "gaziemir":  {"satilik_m2": 48000, "kiralik_aylik": 15000},
        },
    },
    "antalya": {
        "ortalama_satilik_m2_tl": 58900,
        "ortalama_kiralik_aylik_tl": 18200,
        "amortisman_yil": 27,
        "populer_ilceler": {
            "muratpasa": {"satilik_m2": 72000, "kiralik_aylik": 22000},
            "kepez":     {"satilik_m2": 45000, "kiralik_aylik": 14000},
            "konyaalti": {"satilik_m2": 68000, "kiralik_aylik": 21000},
            "alanya":    {"satilik_m2": 62000, "kiralik_aylik": 19000},
        },
    },
    "bursa": {
        "ortalama_satilik_m2_tl": 42100,
        "ortalama_kiralik_aylik_tl": 13500,
        "amortisman_yil": 26,
        "populer_ilceler": {
            "nilufer":   {"satilik_m2": 58000, "kiralik_aylik": 18000},
            "osmangazi": {"satilik_m2": 45000, "kiralik_aylik": 14000},
            "yildirim":  {"satilik_m2": 38000, "kiralik_aylik": 12000},
        },
    },
    "adana": {
        "ortalama_satilik_m2_tl": 28500,
        "ortalama_kiralik_aylik_tl": 9200,
        "amortisman_yil": 26,
        "populer_ilceler": {
            "seyhan":   {"satilik_m2": 32000, "kiralik_aylik": 10500},
            "cukurova": {"satilik_m2": 29000, "kiralik_aylik": 9500},
            "yuregir":  {"satilik_m2": 24000, "kiralik_aylik": 8000},
        },
    },
}


def _evds_yukle() -> dict | None:
    """data/evds_data.json dosyasını yükler; yoksa None döner."""
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return None


def _filtrele(liste: list, baslangic: str | None, bitis: str | None) -> list:
    if baslangic:
        liste = [d for d in liste if d.get("tarih", "") >= baslangic]
    if bitis:
        liste = [d for d in liste if d.get("tarih", "") <= bitis]
    return liste


# ---------------------------------------------------------------------------
# Endpoint'ler
# ---------------------------------------------------------------------------

@app.get("/", tags=["Genel"])
def root():
    evds = _evds_yukle()
    guncelleme = (
        evds["meta"]["guncelleme_zamani"] if evds else "Henüz TCMB verisi çekilmedi"
    )
    return {
        "api": "Turkey Real Estate API",
        "version": "4.0.0",
        "veri_kaynagi": "TCMB EVDS",
        "son_guncelleme": guncelleme,
        "endpoints": {
            "/konut-fiyat-endeksi": "TCMB Konut Fiyat Endeksi (aylık)",
            "/kira-endeksi":        "TCMB Kira Endeksi (aylık)",
            "/mortgage-faiz":       "Konut kredisi faiz oranları",
            "/insaat-maliyeti":     "İnşaat maliyet endeksi",
            "/sehir-endeksleri":    "Şehir bazlı konut fiyat endeksleri",
            "/sehir-verileri":      "Şehir ve ilçe m² / kira fiyatları",
            "/yatirim-analizi":     "Şehir bazlı yatırım getirisi analizi",
            "/ozet":                "Tüm piyasa özeti",
        },
    }


@app.get("/konut-fiyat-endeksi", tags=["Endeksler"])
def konut_fiyat_endeksi(
    baslangic: str = Query(None, description="Başlangıç tarihi (yyyy-mm)"),
    bitis:     str = Query(None, description="Bitiş tarihi (yyyy-mm)"),
):
    """TCMB Konut Fiyat Endeksi — Türkiye geneli aylık seri."""
    evds = _evds_yukle()
    if evds:
        seri = evds["seriler"].get("konut_endeks_turkiye", [])
        data = _filtrele(seri, baslangic, bitis)
        kaynak = "TCMB EVDS (otomatik güncelleme)"
        guncelleme = evds["meta"]["guncelleme_zamani"]
    else:
        data = _STATIK_KONUT_ENDEKSI
        data = _filtrele(data, baslangic, bitis)
        kaynak = "Statik veri (TCMB EVDS henüz yapılandırılmadı)"
        guncelleme = None

    return {
        "status": "success",
        "kaynak": kaynak,
        "son_guncelleme": guncelleme,
        "aciklama": "Türkiye geneli konut fiyat endeksi",
        "count": len(data),
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }


@app.get("/kira-endeksi", tags=["Endeksler"])
def kira_endeksi(
    baslangic: str = Query(None, description="Başlangıç tarihi (yyyy-mm)"),
    bitis:     str = Query(None, description="Bitiş tarihi (yyyy-mm)"),
):
    """TCMB Kira Fiyat Endeksi — Türkiye geneli aylık seri."""
    evds = _evds_yukle()
    if evds:
        seri = evds["seriler"].get("kira_endeks", [])
        data = _filtrele(seri, baslangic, bitis)
        kaynak = "TCMB EVDS (otomatik güncelleme)"
        guncelleme = evds["meta"]["guncelleme_zamani"]
    else:
        data = _STATIK_KIRA_ENDEKSI
        data = _filtrele(data, baslangic, bitis)
        kaynak = "Statik veri"
        guncelleme = None

    return {
        "status": "success",
        "kaynak": kaynak,
        "son_guncelleme": guncelleme,
        "aciklama": "Türkiye geneli kira fiyat endeksi",
        "count": len(data),
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }


@app.get("/mortgage-faiz", tags=["Endeksler"])
def mortgage_faiz(
    baslangic: str = Query(None, description="Başlangıç tarihi (yyyy-mm)"),
    bitis:     str = Query(None, description="Bitiş tarihi (yyyy-mm)"),
):
    """TCMB Konut Kredisi Faiz Oranları — aylık ortalama."""
    evds = _evds_yukle()
    if not evds:
        raise HTTPException(503, "TCMB verisi henüz yüklenmedi. fetch_data.py çalıştırın.")
    seri = evds["seriler"].get("mortgage_faiz", [])
    data = _filtrele(seri, baslangic, bitis)
    return {
        "status": "success",
        "kaynak": "TCMB EVDS",
        "aciklama": "Konut kredisi aylık ortalama faiz oranı (%)",
        "son_guncelleme": evds["meta"]["guncelleme_zamani"],
        "count": len(data),
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }


@app.get("/insaat-maliyeti", tags=["Endeksler"])
def insaat_maliyeti(
    baslangic: str = Query(None, description="Başlangıç tarihi (yyyy-mm)"),
    bitis:     str = Query(None, description="Bitiş tarihi (yyyy-mm)"),
):
    """TCMB İnşaat Maliyet Endeksi — aylık seri."""
    evds = _evds_yukle()
    if not evds:
        raise HTTPException(503, "TCMB verisi henüz yüklenmedi. fetch_data.py çalıştırın.")
    seri = evds["seriler"].get("insaat_maliyeti", [])
    data = _filtrele(seri, baslangic, bitis)
    return {
        "status": "success",
        "kaynak": "TCMB EVDS",
        "aciklama": "İnşaat maliyet endeksi",
        "son_guncelleme": evds["meta"]["guncelleme_zamani"],
        "count": len(data),
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }


@app.get("/sehir-endeksleri", tags=["Şehir Verileri"])
def sehir_endeksleri(
    sehir: str = Query(
        "istanbul",
        description="Şehir: istanbul, ankara, izmir, antalya, bursa",
    ),
    baslangic: str = Query(None, description="Başlangıç tarihi (yyyy-mm)"),
    bitis:     str = Query(None, description="Bitiş tarihi (yyyy-mm)"),
):
    """Şehir bazlı konut fiyat endeksleri (TCMB EVDS)."""
    seri_map = {
        "istanbul": "konut_endeks_istanbul",
        "ankara":   "konut_endeks_ankara",
        "izmir":    "konut_endeks_izmir",
        "antalya":  "konut_endeks_antalya",
        "bursa":    "konut_endeks_bursa",
        "adana":    "konut_endeks_adana",
    }
    sehir = sehir.lower()
    if sehir not in seri_map:
        raise HTTPException(400, f"Desteklenen şehirler: {list(seri_map.keys())}")

    evds = _evds_yukle()
    if not evds:
        raise HTTPException(503, "TCMB verisi henüz yüklenmedi.")

    seri = evds["seriler"].get(seri_map[sehir], [])
    data = _filtrele(seri, baslangic, bitis)
    return {
        "status": "success",
        "sehir": sehir,
        "kaynak": "TCMB EVDS",
        "son_guncelleme": evds["meta"]["guncelleme_zamani"],
        "count": len(data),
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }


@app.get("/sehir-verileri", tags=["Şehir Verileri"])
def sehir_verileri(
    sehir: str = Query("istanbul", description="Şehir adı"),
    ilce:  str = Query(None, description="İlçe adı (opsiyonel)"),
):
    """Şehir ve ilçe bazında güncel m² satış ve kira fiyatları."""
    sehir = sehir.lower()
    if sehir not in SEHIR_VERILERI:
        raise HTTPException(
            400,
            f"Şehir bulunamadı. Mevcut şehirler: {list(SEHIR_VERILERI.keys())}",
        )

    veri = SEHIR_VERILERI[sehir].copy()

    if ilce:
        ilce = ilce.lower()
        ilceler = veri.get("populer_ilceler", {})
        if ilce not in ilceler:
            raise HTTPException(
                400,
                f"İlçe bulunamadı. Mevcut ilçeler: {list(ilceler.keys())}",
            )
        return {
            "status": "success",
            "sehir": sehir,
            "ilce": ilce,
            "timestamp": datetime.now().isoformat(),
            "data": ilceler[ilce],
        }

    return {
        "status": "success",
        "sehir": sehir,
        "timestamp": datetime.now().isoformat(),
        "data": veri,
    }


@app.get("/yatirim-analizi", tags=["Analiz"])
def yatirim_analizi(
    sehir:     str   = Query("istanbul", description="Şehir adı"),
    ilce:      str   = Query(None,       description="İlçe adı (opsiyonel)"),
    metrekare: float = Query(100,        description="Daire büyüklüğü (m²)"),
):
    """
    Yatırım getirisi analizi.
    Kira getirisi, amortisman süresi ve tahmini net ROI hesaplar.
    """
    sehir = sehir.lower()
    if sehir not in SEHIR_VERILERI:
        raise HTTPException(400, f"Desteklenen şehirler: {list(SEHIR_VERILERI.keys())}")

    veri = SEHIR_VERILERI[sehir]

    if ilce:
        ilce = ilce.lower()
        ilceler = veri.get("populer_ilceler", {})
        if ilce not in ilceler:
            raise HTTPException(400, f"Mevcut ilçeler: {list(ilceler.keys())}")
        m2_fiyat   = ilceler[ilce]["satilik_m2"]
        aylik_kira = ilceler[ilce]["kiralik_aylik"]
        konum = f"{sehir}/{ilce}"
    else:
        m2_fiyat   = veri["ortalama_satilik_m2_tl"]
        aylik_kira = veri["ortalama_kiralik_aylik_tl"]
        konum = sehir

    satis_fiyati      = m2_fiyat * metrekare
    yillik_kira       = aylik_kira * 12
    brut_getiri       = round(yillik_kira / satis_fiyati * 100, 2)
    net_getiri        = round(brut_getiri * 0.85, 2)   # %15 gider tahmini
    amortisman_yil    = round(satis_fiyati / yillik_kira, 1)

    return {
        "status": "success",
        "konum": konum,
        "timestamp": datetime.now().isoformat(),
        "giris": {
            "metrekare": metrekare,
            "m2_birim_fiyat_tl": m2_fiyat,
            "aylik_kira_tl": aylik_kira,
        },
        "analiz": {
            "tahmini_satis_fiyati_tl": satis_fiyati,
            "yillik_kira_geliri_tl":   yillik_kira,
            "brut_kira_getirisi_yuzde": brut_getiri,
            "net_kira_getirisi_yuzde":  net_getiri,
            "amortisman_suresi_yil":    amortisman_yil,
        },
        "not": "Net getiri %15 gider (vergi, bakım, boşluk) varsayımıyla hesaplanmıştır.",
    }


@app.get("/ozet", tags=["Genel"])
def ozet():
    """Tüm piyasa özeti — tek istekle her şey."""
    evds = _evds_yukle()

    if evds:
        evds_ozet  = evds.get("ozet", {})
        guncelleme = evds["meta"]["guncelleme_zamani"]
    else:
        evds_ozet  = {}
        guncelleme = None

    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "son_veri_guncelleme": guncelleme,
        "veri_kaynagi": "TCMB EVDS",
        "endeks_ozeti": evds_ozet,
        "desteklenen_sehirler": list(SEHIR_VERILERI.keys()),
        "sehir_ozeti": {
            sehir: {
                "ortalama_satilik_m2_tl":    v["ortalama_satilik_m2_tl"],
                "ortalama_kiralik_aylik_tl": v["ortalama_kiralik_aylik_tl"],
                "ilce_sayisi":               len(v["populer_ilceler"]),
            }
            for sehir, v in SEHIR_VERILERI.items()
        },
    }


# ---------------------------------------------------------------------------
# Statik fallback verileri (EVDS henüz yapılandırılmadan da API çalışsın)
# ---------------------------------------------------------------------------

_STATIK_KONUT_ENDEKSI = [
    {"tarih": "2024-01", "deger": 892.3,  "yillik_degisim_yuzde": 67.2},
    {"tarih": "2024-02", "deger": 921.5,  "yillik_degisim_yuzde": 63.1},
    {"tarih": "2024-03", "deger": 948.7,  "yillik_degisim_yuzde": 58.4},
    {"tarih": "2024-04", "deger": 971.2,  "yillik_degisim_yuzde": 54.9},
    {"tarih": "2024-05", "deger": 998.4,  "yillik_degisim_yuzde": 51.2},
    {"tarih": "2024-06", "deger": 1021.6, "yillik_degisim_yuzde": 47.8},
    {"tarih": "2024-07", "deger": 1045.3, "yillik_degisim_yuzde": 44.1},
    {"tarih": "2024-08", "deger": 1068.9, "yillik_degisim_yuzde": 40.3},
    {"tarih": "2024-09", "deger": 1089.2, "yillik_degisim_yuzde": 36.7},
    {"tarih": "2024-10", "deger": 1112.4, "yillik_degisim_yuzde": 33.2},
    {"tarih": "2024-11", "deger": 1134.8, "yillik_degisim_yuzde": 30.1},
    {"tarih": "2024-12", "deger": 1158.3, "yillik_degisim_yuzde": 27.4},
    {"tarih": "2025-01", "deger": 1178.6, "yillik_degisim_yuzde": 32.1},
    {"tarih": "2025-02", "deger": 1198.4, "yillik_degisim_yuzde": 30.1},
]

_STATIK_KIRA_ENDEKSI = [
    {"tarih": "2024-01", "deger": 1821.4, "yillik_degisim_yuzde": 97.2},
    {"tarih": "2024-02", "deger": 1876.3, "yillik_degisim_yuzde": 89.4},
    {"tarih": "2024-03", "deger": 1923.7, "yillik_degisim_yuzde": 82.1},
    {"tarih": "2024-04", "deger": 1978.2, "yillik_degisim_yuzde": 76.3},
    {"tarih": "2024-05", "deger": 2034.5, "yillik_degisim_yuzde": 71.8},
    {"tarih": "2024-06", "deger": 2089.1, "yillik_degisim_yuzde": 67.2},
    {"tarih": "2024-07", "deger": 2143.8, "yillik_degisim_yuzde": 62.4},
    {"tarih": "2024-08", "deger": 2198.6, "yillik_degisim_yuzde": 57.9},
    {"tarih": "2024-09", "deger": 2251.3, "yillik_degisim_yuzde": 53.1},
    {"tarih": "2024-10", "deger": 2298.7, "yillik_degisim_yuzde": 48.6},
    {"tarih": "2024-11", "deger": 2341.2, "yillik_degisim_yuzde": 44.2},
    {"tarih": "2024-12", "deger": 2389.8, "yillik_degisim_yuzde": 39.8},
    {"tarih": "2025-01", "deger": 2434.1, "yillik_degisim_yuzde": 33.6},
    {"tarih": "2025-02", "deger": 2476.3, "yillik_degisim_yuzde": 32.0},
]
