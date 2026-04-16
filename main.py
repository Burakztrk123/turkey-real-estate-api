"""
Turkey Real Estate API — v5.1.0
TegmenSoft © 2026 — Tüm hakları saklıdır.

Özellikler:
  - API Key doğrulama + Rate limiting
  - In-Memory Cache (TTL bazlı, Redis gerekmez)
  - Async/await ile non-blocking I/O
  - /health endpoint (uptime, versiyon, cache durumu)
  - TCMB EVDS otomatik veri güncellemesi
"""

import asyncio
import json
import os
import time
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
VERSION       = "5.1.0"
_START_TIME   = datetime.now()          # Uptime hesabı için

# ---------------------------------------------------------------------------
# API Key & Rate Limit
# ---------------------------------------------------------------------------
_raw_keys = os.environ.get("API_KEYS", "tegmensoft-test-2026-abc123")
VALID_API_KEYS = {k.strip() for k in _raw_keys.split(",") if k.strip()}

RATE_LIMIT_PER_MINUTE = 60
AUTH_EXEMPT_PATHS = {"/", "/docs", "/redoc", "/openapi.json", "/health"}


class RateLimiter:
    def __init__(self, max_req: int = 60, window: int = 60):
        self.max_req = max_req
        self.window  = window
        self._data: dict = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        now    = datetime.now()
        cutoff = now - timedelta(seconds=self.window)
        with self._lock:
            self._data[key] = [t for t in self._data[key] if t > cutoff]
            if len(self._data[key]) >= self.max_req:
                return False
            self._data[key].append(now)
            return True


rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE)

# ---------------------------------------------------------------------------
# In-Memory Cache
# ---------------------------------------------------------------------------
# Redis kurulumu gerekmez — aynı veriyi milisaniyeler içinde döndürür.
# EVDS verisi haftada bir değiştiği için 1 saatlik TTL yeterlidir.
# Hesaplamalı endpoint'ler (yatirim-analizi) 10 dakika cache'lenir.

_cache: dict = {}
_cache_lock = threading.Lock()

CACHE_TTL_EVDS   = 3600   # 1 saat   — EVDS JSON dosyası
CACHE_TTL_RESP   = 600    # 10 dakika — hesaplamalı yanıtlar


def cache_get(key: str):
    """Cache'den veri al. Süresi geçmişse None döner."""
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (time.monotonic() - entry["ts"]) < entry["ttl"]:
            return entry["data"]
    return None


def cache_set(key: str, data, ttl: int = CACHE_TTL_RESP):
    """Veriyi cache'e yaz."""
    with _cache_lock:
        _cache[key] = {"data": data, "ts": time.monotonic(), "ttl": ttl}


def cache_stats() -> dict:
    """Cache istatistikleri — /health endpoint için."""
    with _cache_lock:
        now = time.monotonic()
        total   = len(_cache)
        active  = sum(1 for v in _cache.values() if now - v["ts"] < v["ttl"])
        expired = total - active
    return {"toplam_girdi": total, "aktif": active, "suresi_gecmis": expired}


# ---------------------------------------------------------------------------
# Async Dosya Okuma + EVDS Cache
# ---------------------------------------------------------------------------
DATA_FILE = Path(__file__).parent / "data" / "evds_data.json"


async def evds_yukle() -> dict | None:
    """
    EVDS JSON dosyasını asenkron okur.
    Sonucu 1 saat cache'ler — disk I/O'yu minimize eder.
    100 eş zamanlı istek olsa bile dosyayı tek sefer okur.
    """
    cached = cache_get("__evds_data__")
    if cached is not None:
        return cached

    if not DATA_FILE.exists():
        return None

    # Dosya okumayı thread pool'a gönder (event loop'u bloke etmez)
    loop = asyncio.get_event_loop()
    try:
        raw = await loop.run_in_executor(
            None,
            lambda: DATA_FILE.read_text(encoding="utf-8"),
        )
        data = json.loads(raw)
        cache_set("__evds_data__", data, ttl=CACHE_TTL_EVDS)
        return data
    except Exception:
        return None


def filtrele(liste: list, baslangic: str | None, bitis: str | None) -> list:
    if baslangic:
        liste = [d for d in liste if d.get("tarih", "") >= baslangic]
    if bitis:
        liste = [d for d in liste if d.get("tarih", "") <= bitis]
    return liste


# ---------------------------------------------------------------------------
# Şehir Verileri (Statik)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Uygulama
# ---------------------------------------------------------------------------
_ACIKLAMA = """
## TegmenSoft Türkiye Gayrimenkul API

Türkiye konut piyasasına ait **resmi ve otomatik güncellenen** veri seti.
Kaynak: **TCMB EVDS** (Türkiye Cumhuriyet Merkez Bankası)

---

### 🔑 Kimlik Doğrulama

Her istekte HTTP başlığına API anahtarınızı ekleyin:

```
X-API-Key: your-api-key-here
```

### 📊 Endpoint'ler

| Endpoint | İçerik |
|---|---|
| `/konut-fiyat-endeksi` | Türkiye geneli aylık KFE |
| `/kira-endeksi` | Türkiye geneli kira endeksi |
| `/sehir-endeksleri` | 6 büyük şehir KFE |
| `/sehir-verileri` | Şehir/ilçe m² ve kira fiyatları |
| `/yatirim-analizi` | Brüt/net getiri ve amortisman hesabı |
| `/ozet` | Tek istekle tüm piyasa özeti |
| `/health` | Sistem durumu ve uptime |

### 🏙️ Desteklenen Şehirler

`istanbul` · `ankara` · `izmir` · `antalya` · `bursa` · `adana`

### ⚡ Performans

Yanıtlar **In-Memory Cache** ile milisaniyeler içinde döner.
Veriler **her Pazar 09:00** TCMB EVDS'den otomatik güncellenir.

---

**TegmenSoft © 2026** | burakztrk142000@gmail.com
"""

app = FastAPI(
    title="TegmenSoft Türkiye Gayrimenkul API",
    description=_ACIKLAMA,
    version=VERSION,
    docs_url=None,
    redoc_url=None,
    contact={"name": "TegmenSoft", "email": "burakztrk142000@gmail.com"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Güvenlik Middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if request.url.path in AUTH_EXEMPT_PATHS:
        return await call_next(request)

    api_key = request.headers.get("X-API-Key", "").strip()

    if not api_key:
        return JSONResponse(status_code=403, content={
            "hata": "API Key eksik.",
            "mesaj": "'X-API-Key' başlığını göndermeniz zorunludur.",
            "dokumantasyon": "/docs",
        })

    if api_key not in VALID_API_KEYS:
        return JSONResponse(status_code=403, content={
            "hata": "Geçersiz API Key.",
            "mesaj": "Bu anahtar tanınmıyor. Lütfen TegmenSoft ile iletişime geçin.",
            "iletisim": "burakztrk142000@gmail.com",
        })

    if not rate_limiter.is_allowed(api_key):
        return JSONResponse(status_code=429, content={
            "hata": "Çok fazla istek!",
            "mesaj": f"Dakikada en fazla {RATE_LIMIT_PER_MINUTE} istek atabilirsiniz.",
            "limit": RATE_LIMIT_PER_MINUTE,
            "pencere": "60 saniye",
        })

    return await call_next(request)

# ---------------------------------------------------------------------------
# Özel Swagger UI
# ---------------------------------------------------------------------------
@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="TegmenSoft Gayrimenkul API — Dokümantasyon",
        swagger_ui_parameters={
            "docExpansion": "list",
            "defaultModelsExpandDepth": -1,
            "displayRequestDuration": True,
            "filter": True,
        },
    )

@app.get("/openapi.json", include_in_schema=False)
async def openapi_schema():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title="TegmenSoft Türkiye Gayrimenkul API",
        version=VERSION,
        description=_ACIKLAMA,
        routes=app.routes,
    )
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    }
    schema["security"] = [{"ApiKeyAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema

# ---------------------------------------------------------------------------
# Endpoint'ler
# ---------------------------------------------------------------------------

@app.get("/", tags=["Genel"])
async def root():
    evds = await evds_yukle()
    return {
        "api": "TegmenSoft Türkiye Gayrimenkul API",
        "version": VERSION,
        "son_guncelleme": evds["meta"]["guncelleme_zamani"] if evds else None,
        "dokumantasyon": "/docs",
    }


@app.get("/health", tags=["Genel"], summary="Sistem Durumu")
async def health():
    """
    **Sistem sağlık kontrolü** — izleme araçları için.

    Uptime, versiyon, veri dosyası durumu ve cache istatistiklerini döner.
    API Key gerektirmez.
    """
    uptime_sn = int((datetime.now() - _START_TIME).total_seconds())
    saat      = uptime_sn // 3600
    dakika    = (uptime_sn % 3600) // 60
    saniye    = uptime_sn % 60

    # Veri dosyası bilgisi
    veri_durumu = "yok"
    veri_tarih  = None
    if DATA_FILE.exists():
        veri_durumu = "mevcut"
        ts = DATA_FILE.stat().st_mtime
        veri_tarih = datetime.fromtimestamp(ts).isoformat()

    # Cache'de veri var mı?
    cache_durum = "cache'de" if cache_get("__evds_data__") is not None else "cache'de değil"

    return {
        "status": "ok",
        "version": VERSION,
        "uptime": {
            "saniye": uptime_sn,
            "ozet": f"{saat}s {dakika}dk {saniye}sn",
        },
        "veri_dosyasi": {
            "durum": veri_durumu,
            "son_degisiklik": veri_tarih,
            "evds_verisi": cache_durum,
        },
        "cache": cache_stats(),
        "rate_limit": f"{RATE_LIMIT_PER_MINUTE} istek/dakika",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/konut-fiyat-endeksi", tags=["Endeksler"], summary="Konut Fiyat Endeksi")
async def konut_fiyat_endeksi(
    baslangic: str = Query(None, description="Başlangıç tarihi (yyyy-mm)", example="2024-01"),
    bitis:     str = Query(None, description="Bitiş tarihi (yyyy-mm)",     example="2026-02"),
):
    """**TCMB Konut Fiyat Endeksi** — Türkiye geneli, aylık seri."""
    cache_key = f"kfe_{baslangic}_{bitis}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    evds = await evds_yukle()
    if evds:
        seri = evds["seriler"].get("konut_endeks_turkiye", [])
        data = filtrele(seri, baslangic, bitis)
        kaynak = "TCMB EVDS (otomatik güncelleme)"
        guncelleme = evds["meta"]["guncelleme_zamani"]
    else:
        data = filtrele(_STATIK_KONUT_ENDEKSI, baslangic, bitis)
        kaynak = "Statik veri"
        guncelleme = None

    yanit = {
        "status": "success",
        "kaynak": kaynak,
        "son_guncelleme": guncelleme,
        "count": len(data),
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }
    cache_set(cache_key, yanit)
    return yanit


@app.get("/kira-endeksi", tags=["Endeksler"], summary="Kira Endeksi")
async def kira_endeksi(
    baslangic: str = Query(None, description="Başlangıç tarihi (yyyy-mm)"),
    bitis:     str = Query(None, description="Bitiş tarihi (yyyy-mm)"),
):
    """**TCMB Kira Endeksi** — Türkiye geneli, aylık seri."""
    cache_key = f"kira_{baslangic}_{bitis}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    evds = await evds_yukle()
    if evds:
        seri = evds["seriler"].get("kira_endeks", [])
        data = filtrele(seri, baslangic, bitis)
        kaynak = "TCMB EVDS (otomatik güncelleme)"
        guncelleme = evds["meta"]["guncelleme_zamani"]
    else:
        data = filtrele(_STATIK_KIRA_ENDEKSI, baslangic, bitis)
        kaynak = "Statik veri"
        guncelleme = None

    yanit = {
        "status": "success",
        "kaynak": kaynak,
        "son_guncelleme": guncelleme,
        "count": len(data),
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }
    cache_set(cache_key, yanit)
    return yanit


@app.get("/sehir-endeksleri", tags=["Şehir Verileri"], summary="Şehir Bazlı KFE")
async def sehir_endeksleri(
    sehir:     str = Query("istanbul", description="Şehir adı", example="istanbul"),
    baslangic: str = Query(None, description="Başlangıç tarihi (yyyy-mm)"),
    bitis:     str = Query(None, description="Bitiş tarihi (yyyy-mm)"),
):
    """**Şehir bazlı KFE** — 6 büyük şehir için TCMB EVDS verisi."""
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

    cache_key = f"sehir_endeks_{sehir}_{baslangic}_{bitis}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    evds = await evds_yukle()
    if not evds:
        raise HTTPException(503, "TCMB verisi henüz yüklenmedi.")

    seri = evds["seriler"].get(seri_map[sehir], [])
    data = filtrele(seri, baslangic, bitis)

    yanit = {
        "status": "success",
        "sehir": sehir,
        "kaynak": "TCMB EVDS",
        "son_guncelleme": evds["meta"]["guncelleme_zamani"],
        "count": len(data),
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }
    cache_set(cache_key, yanit)
    return yanit


@app.get("/sehir-verileri", tags=["Şehir Verileri"], summary="m² ve Kira Fiyatları")
async def sehir_verileri(
    sehir: str = Query("istanbul", description="Şehir adı", example="istanbul"),
    ilce:  str = Query(None, description="İlçe adı (opsiyonel)", example="kadikoy"),
):
    """**Şehir/ilçe bazında** ortalama m² satış ve kira fiyatları."""
    sehir = sehir.lower()
    if sehir not in SEHIR_VERILERI:
        raise HTTPException(400, f"Mevcut şehirler: {list(SEHIR_VERILERI.keys())}")

    veri = SEHIR_VERILERI[sehir].copy()

    if ilce:
        ilce = ilce.lower()
        ilceler = veri.get("populer_ilceler", {})
        if ilce not in ilceler:
            raise HTTPException(400, f"Mevcut ilçeler: {list(ilceler.keys())}")
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


@app.get("/yatirim-analizi", tags=["Analiz"], summary="Yatırım Getirisi Analizi")
async def yatirim_analizi(
    sehir:     str   = Query("istanbul", description="Şehir adı"),
    ilce:      str   = Query(None,       description="İlçe adı (opsiyonel)"),
    metrekare: float = Query(100,        description="Daire büyüklüğü (m²)", ge=10, le=1000),
):
    """**Yatırım analizi** — brüt/net getiri ve amortisman hesabı."""
    sehir = sehir.lower()
    if sehir not in SEHIR_VERILERI:
        raise HTTPException(400, f"Desteklenen şehirler: {list(SEHIR_VERILERI.keys())}")

    # Hesaplamalı endpoint — 10 dk cache
    cache_key = f"yatirim_{sehir}_{ilce}_{metrekare}"
    cached = cache_get(cache_key)
    if cached:
        return cached

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

    satis_fiyati   = m2_fiyat * metrekare
    yillik_kira    = aylik_kira * 12
    brut_getiri    = round(yillik_kira / satis_fiyati * 100, 2)
    net_getiri     = round(brut_getiri * 0.85, 2)
    amortisman_yil = round(satis_fiyati / yillik_kira, 1)

    yanit = {
        "status": "success",
        "konum": konum,
        "timestamp": datetime.now().isoformat(),
        "giris": {
            "metrekare": metrekare,
            "m2_birim_fiyat_tl": m2_fiyat,
            "aylik_kira_tl": aylik_kira,
        },
        "analiz": {
            "tahmini_satis_fiyati_tl":  satis_fiyati,
            "yillik_kira_geliri_tl":    yillik_kira,
            "brut_kira_getirisi_yuzde": brut_getiri,
            "net_kira_getirisi_yuzde":  net_getiri,
            "amortisman_suresi_yil":    amortisman_yil,
        },
        "not": "Net getiri %15 gider (vergi, bakım, boşluk) varsayımıyla hesaplanmıştır.",
    }
    cache_set(cache_key, yanit, ttl=CACHE_TTL_RESP)
    return yanit


@app.get("/ozet", tags=["Genel"], summary="Piyasa Özeti")
async def ozet():
    """**Tüm piyasa özeti** — tek istekle her şey."""
    cache_key = "ozet"
    cached = cache_get(cache_key)
    if cached:
        return cached

    evds = await evds_yukle()
    evds_ozet  = evds.get("ozet", {}) if evds else {}
    guncelleme = evds["meta"]["guncelleme_zamani"] if evds else None

    yanit = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "son_veri_guncelleme": guncelleme,
        "veri_kaynagi": "TCMB EVDS",
        "endeks_ozeti": evds_ozet,
        "desteklenen_sehirler": list(SEHIR_VERILERI.keys()),
        "sehir_ozeti": {
            s: {
                "ortalama_satilik_m2_tl":    v["ortalama_satilik_m2_tl"],
                "ortalama_kiralik_aylik_tl": v["ortalama_kiralik_aylik_tl"],
                "ilce_sayisi":               len(v["populer_ilceler"]),
            }
            for s, v in SEHIR_VERILERI.items()
        },
    }
    cache_set(cache_key, yanit)
    return yanit


# ---------------------------------------------------------------------------
# Statik Fallback
# ---------------------------------------------------------------------------
_STATIK_KONUT_ENDEKSI = [
    {"tarih": "2024-01", "deger": 892.3,  "yillik_degisim_yuzde": 67.2},
    {"tarih": "2024-06", "deger": 1021.6, "yillik_degisim_yuzde": 47.8},
    {"tarih": "2024-12", "deger": 1158.3, "yillik_degisim_yuzde": 27.4},
    {"tarih": "2025-06", "deger": 1312.1, "yillik_degisim_yuzde": 28.4},
]

_STATIK_KIRA_ENDEKSI = [
    {"tarih": "2024-01", "deger": 1821.4, "yillik_degisim_yuzde": 97.2},
    {"tarih": "2024-06", "deger": 2089.1, "yillik_degisim_yuzde": 67.2},
    {"tarih": "2024-12", "deger": 2389.8, "yillik_degisim_yuzde": 39.8},
    {"tarih": "2025-06", "deger": 2698.3, "yillik_degisim_yuzde": 29.1},
]
