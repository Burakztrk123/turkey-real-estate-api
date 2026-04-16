"""
Turkey Real Estate API — v5.0.0
TegmenSoft © 2026 — Tüm hakları saklıdır.

Özellikler:
  - API Key doğrulama (X-API-Key başlığı)
  - Rate limiting (60 istek/dakika per key)
  - Türkçe kurumsal Swagger dokümantasyonu
  - TCMB EVDS otomatik veri güncellemesi
"""

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import threading
import json
import os

# ---------------------------------------------------------------------------
# API Key Konfigürasyonu
# ---------------------------------------------------------------------------
# Render'da Environment Variables → API_KEYS = key1,key2,key3 şeklinde ekle
# Birden fazla müşteri için virgülle ayır
_raw_keys = os.environ.get("API_KEYS", "tegmensoft-test-2026-abc123")
VALID_API_KEYS = {k.strip() for k in _raw_keys.split(",") if k.strip()}

# Kimlik doğrulamadan muaf URL'ler
AUTH_EXEMPT_PATHS = {"/", "/docs", "/redoc", "/openapi.json", "/health"}

# Rate limit: dakikada kaç istek
RATE_LIMIT_PER_MINUTE = 60


# ---------------------------------------------------------------------------
# Bellek İçi Rate Limiter
# ---------------------------------------------------------------------------
class RateLimiter:
    """API key başına dakikada max istek sınırı uygular."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._data: dict = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.window)
        with self._lock:
            self._data[key] = [t for t in self._data[key] if t > cutoff]
            if len(self._data[key]) >= self.max_requests:
                return False
            self._data[key].append(now)
            return True


rate_limiter = RateLimiter(RATE_LIMIT_PER_MINUTE)

# ---------------------------------------------------------------------------
# FastAPI Uygulaması
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

### 📊 Mevcut Veri Setleri

| Endpoint | İçerik |
|---|---|
| `/konut-fiyat-endeksi` | Türkiye geneli aylık KFE |
| `/kira-endeksi` | Türkiye geneli kira endeksi |
| `/sehir-endeksleri` | 6 büyük şehir KFE |
| `/sehir-verileri` | Şehir/ilçe m² ve kira fiyatları |
| `/yatirim-analizi` | Brüt/net getiri ve amortisman hesabı |
| `/ozet` | Tek istekle tüm piyasa özeti |

### 🏙️ Desteklenen Şehirler

`istanbul` · `ankara` · `izmir` · `antalya` · `bursa` · `adana`

### 🔄 Güncelleme Sıklığı

Veriler **her Pazar 09:00** TCMB EVDS'den otomatik çekilir.

---

**İletişim:** burakztrk142000@gmail.com | **TegmenSoft © 2026**
"""

app = FastAPI(
    title="TegmenSoft Türkiye Gayrimenkul API",
    description=_ACIKLAMA,
    version="5.0.0",
    docs_url=None,    # Özel Swagger sayfası kullanıyoruz
    redoc_url=None,   # Özel ReDoc sayfası kullanıyoruz
    contact={
        "name": "TegmenSoft Destek",
        "email": "burakztrk142000@gmail.com",
    },
    license_info={
        "name": "Ticari Lisans — Yetkisiz kullanım yasaktır.",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Güvenlik Middleware — API Key + Rate Limit
# ---------------------------------------------------------------------------
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Her istekte API Key kontrolü ve rate limit uygular."""

    # Muaf URL'leri geç
    if request.url.path in AUTH_EXEMPT_PATHS:
        return await call_next(request)

    # 1) API Key kontrolü
    api_key = request.headers.get("X-API-Key", "").strip()
    if not api_key:
        return JSONResponse(
            status_code=403,
            content={
                "hata": "API Key eksik.",
                "mesaj": "İsteklerde 'X-API-Key' başlığını göndermeniz zorunludur.",
                "dokumantasyon": "/docs",
            },
        )
    if api_key not in VALID_API_KEYS:
        return JSONResponse(
            status_code=403,
            content={
                "hata": "Geçersiz API Key.",
                "mesaj": "Bu API anahtarı tanınmıyor. Lütfen TegmenSoft ile iletişime geçin.",
                "iletisim": "burakztrk142000@gmail.com",
            },
        )

    # 2) Rate limit kontrolü
    if not rate_limiter.is_allowed(api_key):
        return JSONResponse(
            status_code=429,
            content={
                "hata": "Çok fazla istek!",
                "mesaj": f"Dakikada en fazla {RATE_LIMIT_PER_MINUTE} istek atabilirsiniz. Lütfen 1 dakika bekleyin.",
                "limit": RATE_LIMIT_PER_MINUTE,
                "pencere": "60 saniye",
            },
        )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Özel Swagger UI (TegmenSoft Temalı)
# ---------------------------------------------------------------------------
@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    """TegmenSoft temalı Swagger dokümantasyon sayfası."""
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="TegmenSoft Gayrimenkul API — Dokümantasyon",
        swagger_ui_parameters={
            "docExpansion": "list",
            "defaultModelsExpandDepth": -1,
            "displayRequestDuration": True,
            "filter": True,
            "tryItOutEnabled": True,
        },
    )


@app.get("/openapi.json", include_in_schema=False)
async def openapi_schema():
    """OpenAPI şeması — API Key güvenlik tanımını içerir."""
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title="TegmenSoft Türkiye Gayrimenkul API",
        version="5.0.0",
        description=_ACIKLAMA,
        routes=app.routes,
    )

    # Swagger'da 🔒 kilit ikonu ve "Authorize" butonu için güvenlik şeması
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "TegmenSoft tarafından verilen API anahtarınızı buraya girin.",
        }
    }
    # Tüm endpoint'lere global olarak uygula
    schema["security"] = [{"ApiKeyAuth": []}]

    app.openapi_schema = schema
    return app.openapi_schema


# ---------------------------------------------------------------------------
# Veri Yükleme
# ---------------------------------------------------------------------------
DATA_FILE = Path(__file__).parent / "data" / "evds_data.json"

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

@app.get("/", tags=["Genel"], summary="API Bilgisi")
def root():
    """API hakkında genel bilgi ve endpoint listesi."""
    evds = _evds_yukle()
    guncelleme = evds["meta"]["guncelleme_zamani"] if evds else "Henüz TCMB verisi çekilmedi"
    return {
        "api": "TegmenSoft Türkiye Gayrimenkul API",
        "version": "5.0.0",
        "veri_kaynagi": "TCMB EVDS",
        "son_guncelleme": guncelleme,
        "dokumantasyon": "/docs",
        "endpoints": {
            "/konut-fiyat-endeksi": "TCMB Konut Fiyat Endeksi (aylık)",
            "/kira-endeksi":        "TCMB Kira Endeksi (aylık)",
            "/sehir-endeksleri":    "Şehir bazlı konut fiyat endeksleri",
            "/sehir-verileri":      "Şehir ve ilçe m² / kira fiyatları",
            "/yatirim-analizi":     "Şehir bazlı yatırım getirisi analizi",
            "/ozet":                "Tüm piyasa özeti",
        },
    }


@app.get("/health", tags=["Genel"], summary="Sistem Durumu")
def health():
    """Sistem sağlık kontrolü."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/konut-fiyat-endeksi", tags=["Endeksler"], summary="Konut Fiyat Endeksi")
def konut_fiyat_endeksi(
    baslangic: str = Query(None, description="Başlangıç tarihi (yyyy-mm)", example="2024-01"),
    bitis:     str = Query(None, description="Bitiş tarihi (yyyy-mm)",     example="2026-02"),
):
    """
    **TCMB Konut Fiyat Endeksi** — Türkiye geneli aylık seri.

    Her kayıt: tarih, endeks değeri, yıllık değişim yüzdesi içerir.
    """
    evds = _evds_yukle()
    if evds:
        seri = evds["seriler"].get("konut_endeks_turkiye", [])
        data = _filtrele(seri, baslangic, bitis)
        kaynak = "TCMB EVDS (otomatik güncelleme)"
        guncelleme = evds["meta"]["guncelleme_zamani"]
    else:
        data = _STATIK_KONUT_ENDEKSI
        data = _filtrele(data, baslangic, bitis)
        kaynak = "Statik veri"
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


@app.get("/kira-endeksi", tags=["Endeksler"], summary="Kira Endeksi")
def kira_endeksi(
    baslangic: str = Query(None, description="Başlangıç tarihi (yyyy-mm)"),
    bitis:     str = Query(None, description="Bitiş tarihi (yyyy-mm)"),
):
    """
    **TCMB Kira Endeksi** — Türkiye geneli aylık seri.

    TÜFE kira alt kalemi bazında hesaplanmış resmi endeks.
    """
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
        "aciklama": "Türkiye geneli kira endeksi",
        "count": len(data),
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }


@app.get("/sehir-endeksleri", tags=["Şehir Verileri"], summary="Şehir Bazlı KFE")
def sehir_endeksleri(
    sehir: str = Query(
        "istanbul",
        description="Şehir adı",
        example="istanbul",
    ),
    baslangic: str = Query(None, description="Başlangıç tarihi (yyyy-mm)"),
    bitis:     str = Query(None, description="Bitiş tarihi (yyyy-mm)"),
):
    """
    **Şehir bazlı Konut Fiyat Endeksi** — TCMB EVDS NUTS-2 bölge verileri.

    Desteklenen şehirler: `istanbul`, `ankara`, `izmir`, `antalya`, `bursa`, `adana`
    """
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


@app.get("/sehir-verileri", tags=["Şehir Verileri"], summary="m² ve Kira Fiyatları")
def sehir_verileri(
    sehir: str = Query("istanbul", description="Şehir adı", example="istanbul"),
    ilce:  str = Query(None,        description="İlçe adı (opsiyonel)", example="kadikoy"),
):
    """
    **Şehir ve ilçe bazında** ortalama m² satış fiyatı ve aylık kira fiyatı.

    İlçe parametresi girilmezse tüm şehrin özeti döner.
    """
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
def yatirim_analizi(
    sehir:     str   = Query("istanbul", description="Şehir adı"),
    ilce:      str   = Query(None,       description="İlçe adı (opsiyonel)"),
    metrekare: float = Query(100,        description="Daire büyüklüğü (m²)", ge=10, le=1000),
):
    """
    **Yatırım getirisi analizi** — kira getirisi, amortisman ve net ROI hesabı.

    Verilen şehir/ilçe ve metrekareye göre:
    - Tahmini satış fiyatı
    - Yıllık kira geliri
    - Brüt ve net kira getiri yüzdesi (%15 gider varsayımı)
    - Amortisman süresi (yıl)
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

    satis_fiyati   = m2_fiyat * metrekare
    yillik_kira    = aylik_kira * 12
    brut_getiri    = round(yillik_kira / satis_fiyati * 100, 2)
    net_getiri     = round(brut_getiri * 0.85, 2)
    amortisman_yil = round(satis_fiyati / yillik_kira, 1)

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
            "tahmini_satis_fiyati_tl":  satis_fiyati,
            "yillik_kira_geliri_tl":    yillik_kira,
            "brut_kira_getirisi_yuzde": brut_getiri,
            "net_kira_getirisi_yuzde":  net_getiri,
            "amortisman_suresi_yil":    amortisman_yil,
        },
        "not": "Net getiri %15 gider (vergi, bakım, boşluk) varsayımıyla hesaplanmıştır.",
    }


@app.get("/ozet", tags=["Genel"], summary="Piyasa Özeti")
def ozet():
    """
    **Tüm piyasa özeti** — tek istekle tüm veriler.

    TCMB endeks özetleri + şehir bazlı fiyat bilgileri.
    """
    evds = _evds_yukle()
    evds_ozet  = evds.get("ozet", {}) if evds else {}
    guncelleme = evds["meta"]["guncelleme_zamani"] if evds else None

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
# Statik Fallback Verisi
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
