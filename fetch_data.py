"""
TCMB EVDS3 veri çekme scripti.
Doğru endpoint: POST https://evds3.tcmb.gov.tr/igmevdsms-dis/fe

Kullanım:
    TCMB_API_KEY=your_key python fetch_data.py

API key almak için: https://evds3.tcmb.gov.tr
"""

import httpx
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# --- Konfigürasyon ---
API_KEY = os.environ.get("TCMB_API_KEY", "")
BASE_URL = "https://evds3.tcmb.gov.tr/igmevdsms-dis"
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

GECMIS_AY = 36  # 3 yıl geriye

# EVDS3 doğrulanmış seri kodları (KFE datagroup: bie_kfe)
SEHIR_SERI_KODLARI = {
    "turkiye":  "TP.KFE.TR",    # Türkiye geneli
    "istanbul": "TP.KFE.TR10",  # NUTS-2: TR10 = İstanbul
    "ankara":   "TP.KFE.TR51",  # NUTS-2: TR51 = Ankara
    "izmir":    "TP.KFE.TR31",  # NUTS-2: TR31 = İzmir
    "antalya":  "TP.KFE.TR61",  # NUTS-2: TR61 = Antalya-Isparta-Burdur
    "bursa":    "TP.KFE.TR41",  # NUTS-2: TR41 = Bursa-Eskişehir-Bilecik
    "adana":    "TP.KFE.TR62",  # NUTS-2: TR62 = Adana-Mersin
}

# Diğer seri grupları (EVDS3'te doğrulanmış kodlar)
DIGER_SERILER = {
    "kira_endeks":  "TP.FG.J0",    # Kira endeksi (TÜFE - Kira alt kalemi)
    # "mortgage_faiz":   "TP.KKB08",  # TODO: EVDS3'te doğru kodu bul
    # "insaat_maliyeti": "TP.YBU01",  # TODO: EVDS3'te doğru kodu bul
}


def tarih_aralik():
    """Son GECMIS_AY aylık tarih aralığı (DD-MM-YYYY formatında)."""
    bitis = datetime.now()
    baslangic = bitis - timedelta(days=GECMIS_AY * 30)
    return baslangic.strftime("%d-%m-%Y"), bitis.strftime("%d-%m-%Y")


def evds3_post(seri_kodlari: list, baslangic: str, bitis: str, formul: str = "0") -> dict:
    """
    TCMB EVDS3 POST /fe endpoint'ine istek atar.

    Birden fazla seri için: seri_kodlari = ["TP.KFE.TR", "TP.KFE.TR10", ...]

    Payload formatı (Network sekmesinden yakalandı - 200 OK):
    - series: "-" ile birleştirilmiş seri kodları
    - aggregationTypes: her seri için "avg-avg-avg"
    - formulas: her seri için "0-0-0" (0=seviye, 1=yüzde değ, 3=yıllık değ)
    - frequency: "5" (string, aylık)
    - decimal: "2" (string)
    - dateFormat: "0" (ZORUNLU, eksik olunca 500 hatası)
    - isRaporSayfasi: true (ZORUNLU, eksik olunca 500 hatası)
    - groupSeperator: true
    - lang: "tr" (küçük harf)
    """
    n = len(seri_kodlari)
    series_str = "-".join(seri_kodlari)
    aggregation_str = "-".join(["avg"] * n)
    formulas_str = "-".join([formul] * n)

    body = {
        "type": "json",
        "series": series_str,
        "aggregationTypes": aggregation_str,
        "formulas": formulas_str,
        "startDate": baslangic,
        "endDate": bitis,
        "frequency": "5",           # string, aylık
        "decimal": "2",             # string
        "decimalSeperator": ".",
        "dateFormat": "0",          # KRİTİK: eksik olunca 500 hatası
        "groupSeperator": True,
        "isRaporSayfasi": True,     # KRİTİK: eksik olunca 500 hatası
        "lang": "tr",               # küçük harf
        "ozelFormuller": [],
    }

    headers = {
        "Content-Type": "application/json",
        "key": API_KEY,
    }

    url = f"{BASE_URL}/fe"
    try:
        r = httpx.post(
            url,
            json=body,
            headers=headers,
            timeout=30,
            follow_redirects=True,
        )
        print(f"  HTTP {r.status_code} | Content-Type: {r.headers.get('content-type', '?')}")
        print(f"  Yanıt (ilk 400 karakter): {r.text[:400]}")

        if r.status_code != 200:
            print(f"  HATA: Sunucu {r.status_code} döndürdü")
            return {}

        if not r.text.strip():
            print("  Boş yanıt!")
            return {}

        return r.json()

    except Exception as e:
        print(f"  HATA: {type(e).__name__}: {e}")
        return {}


def parse_seri(raw_json: dict, seri_kodu: str) -> list:
    """
    EVDS3 yanıtından belirli bir serinin verilerini çeker.
    ÖNEMLİ: EVDS3 yanıtta nokta yerine alt çizgi kullanır!
    Örnek: "TP.KFE.TR" → "TP_KFE_TR" (key adı değişiyor)
    Yanıt: {"items": [{"Tarih": "2024-01", "TP_KFE_TR": "123.45", ...}]}
    """
    # EVDS3 response: noktalar alt çizgiye dönüşüyor
    key = seri_kodu.replace(".", "_")
    items = raw_json.get("items", [])
    if not items:
        return []

    result = []
    for item in items:
        tarih = item.get("Tarih", "")
        deger_raw = item.get(key)
        if tarih and deger_raw is not None:
            try:
                # Binlik ayırıcı virgülü kaldır: "1,300.60" → 1300.60
                deger_str = str(deger_raw).replace(",", "")
                deger = float(deger_str)
                result.append({
                    "tarih": _normalize_tarih(tarih),
                    "deger": deger,
                })
            except (ValueError, TypeError):
                pass

    return sorted(result, key=lambda x: x["tarih"])


def _normalize_tarih(tarih_str: str) -> str:
    """TCMB tarih formatını 'YYYY-MM' formatına çevirir."""
    tarih_str = tarih_str.strip()
    parts = tarih_str.split("-")
    if len(parts) == 2:
        if len(parts[0]) == 4:
            return f"{parts[0]}-{parts[1].zfill(2)}"
        else:
            return f"{parts[1]}-{parts[0].zfill(2)}"
    elif len(parts) >= 3:
        return f"{parts[0]}-{parts[1].zfill(2)}"
    return tarih_str


def yillik_degisim_ekle(liste: list) -> list:
    """Her kayda yıllık değişim yüzdesi ekler."""
    tarih_map = {d["tarih"]: d["deger"] for d in liste}
    sonuc = []
    for item in liste:
        try:
            yil, ay = item["tarih"].split("-")
            gecen_yil = f"{int(yil)-1}-{ay}"
            gecen_deger = tarih_map.get(gecen_yil)
            if gecen_deger and gecen_deger != 0:
                degisim = round((item["deger"] - gecen_deger) / gecen_deger * 100, 2)
            else:
                degisim = None
        except Exception:
            degisim = None
        sonuc.append({**item, "yillik_degisim_yuzde": degisim})
    return sonuc


def main():
    if not API_KEY:
        print("HATA: TCMB_API_KEY ortam değişkeni ayarlanmamış!")
        raise SystemExit(1)

    baslangic, bitis = tarih_aralik()
    print(f"Tarih aralığı: {baslangic} → {bitis}")
    print(f"API key: {API_KEY[:4]}***\n")

    tum_veri = {}
    ozet = {}

    # --- 1. Konut Fiyat Endeksi (tüm şehirler, tek POST) ---
    print("=" * 50)
    print("Konut Fiyat Endeksi çekiliyor (tüm şehirler)...")
    sehir_kodlari = list(SEHIR_SERI_KODLARI.values())
    kfe_raw = evds3_post(sehir_kodlari, baslangic, bitis, formul="0")

    for sehir_adi, seri_kodu in SEHIR_SERI_KODLARI.items():
        veri = parse_seri(kfe_raw, seri_kodu)
        veri = yillik_degisim_ekle(veri)
        isim = f"konut_endeks_{sehir_adi}"
        tum_veri[isim] = veri
        print(f"  {sehir_adi}: {len(veri)} kayıt")
        if veri:
            son = veri[-1]
            ozet[isim] = {
                "son_tarih": son["tarih"],
                "son_deger": son["deger"],
                "yillik_degisim_yuzde": son.get("yillik_degisim_yuzde"),
            }
    print()

    # --- 2. Diğer seriler (her biri ayrı POST) ---
    for isim, seri_kodu in DIGER_SERILER.items():
        print(f"Çekiliyor: {isim} ({seri_kodu})...")
        raw = evds3_post([seri_kodu], baslangic, bitis, formul="0")
        veri = parse_seri(raw, seri_kodu)
        veri = yillik_degisim_ekle(veri)
        tum_veri[isim] = veri
        print(f"  → {len(veri)} kayıt\n")
        if veri:
            son = veri[-1]
            ozet[isim] = {
                "son_tarih": son["tarih"],
                "son_deger": son["deger"],
                "yillik_degisim_yuzde": son.get("yillik_degisim_yuzde"),
            }

    # --- Çıktı ---
    cikti = {
        "meta": {
            "guncelleme_zamani": datetime.now().isoformat(),
            "veri_kaynagi": "TCMB EVDS3",
            "kaynak_url": "https://evds3.tcmb.gov.tr",
            "donem": f"{baslangic} - {bitis}",
        },
        "ozet": ozet,
        "seriler": tum_veri,
    }

    cikti_dosya = DATA_DIR / "evds_data.json"
    with open(cikti_dosya, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=2)

    toplam = sum(len(v) for v in tum_veri.values())
    basarili = len([v for v in tum_veri.values() if v])
    print(f"\n{'=' * 50}")
    print(f"✅ Kaydedildi: {cikti_dosya}")
    print(f"   Toplam {toplam} kayıt, {basarili}/{len(tum_veri)} seri başarılı")

    if toplam == 0:
        print("\n⚠️  Hiç veri gelmedi! API key veya seri kodlarını kontrol et.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
