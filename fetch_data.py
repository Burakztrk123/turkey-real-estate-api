"""
TCMB EVDS veri çekme scripti.
GitHub Actions tarafından günlük çalıştırılır ve data/ klasörüne JSON yazar.

Kullanım:
    TCMB_API_KEY=your_key python fetch_data.py

TCMB EVDS API key almak için: https://evds2.tcmb.gov.tr/index.php?/evds/login
"""

import httpx
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

# --- Konfigürasyon ---
API_KEY = os.environ.get("TCMB_API_KEY", "")
BASE_URL = "https://evds2.tcmb.gov.tr/service/evds"
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Kaç aylık veri çekelim (geri dönük)
GECMIS_AY = 36  # 3 yıl

# TCMB seri kodları
SERILER = {
    # Konut Fiyat Endeksi (2010=100 bazlı)
    "konut_endeks_genel":    "TP.HKFE01",
    "konut_endeks_istanbul": "TP.HKFE.A01",
    "konut_endeks_ankara":   "TP.HKFE.A02",
    "konut_endeks_izmir":    "TP.HKFE.A03",
    "konut_endeks_antalya":  "TP.HKFE.A04",
    "konut_endeks_bursa":    "TP.HKFE.A05",
    # Yeni konut fiyat endeksi (2017=100)
    "konut_endeks_yeni":     "TP.KFE.GENEL",
    # Kira endeksi
    "kira_endeks":           "TP.FG.J0",
    # Mortgage faiz oranları (konut kredisi)
    "mortgage_faiz":         "TP.KKB.MK.TBL.MK",
    # İnşaat maliyet endeksi
    "insaat_maliyeti":       "TP.IMALAT05",
}


def tarih_aralik():
    """Son GECMIS_AY aylık tarih aralığı döndürür (TCMB formatında)."""
    bitis = datetime.now()
    baslangic = bitis - timedelta(days=GECMIS_AY * 30)
    return baslangic.strftime("%d-%m-%Y"), bitis.strftime("%d-%m-%Y")


def evds_cek(seri_kodu: str, baslangic: str, bitis: str) -> list[dict]:
    """Tek bir seri için EVDS'den veri çeker."""
    params = {
        "series": seri_kodu,
        "startDate": baslangic,
        "endDate": bitis,
        "type": "json",
        "key": API_KEY,
        "frequency": "5",   # 5 = aylık
        "formulas": "0",    # 0 = seviye (değişim değil)
        "aggregationTypes": "avg",
    }
    try:
        r = httpx.get(f"{BASE_URL}/series", params=params, timeout=30)
        r.raise_for_status()
        raw = r.json()
        items = raw.get("items", [])
        result = []
        for item in items:
            tarih = item.get("Tarih", "")
            deger = item.get(seri_kodu)
            if tarih and deger is not None:
                try:
                    result.append({
                        "tarih": _tcmb_tarih_cevir(tarih),
                        "deger": float(deger),
                    })
                except (ValueError, TypeError):
                    pass
        return sorted(result, key=lambda x: x["tarih"])
    except Exception as e:
        print(f"  HATA [{seri_kodu}]: {e}")
        return []


def _tcmb_tarih_cevir(tarih_str: str) -> str:
    """TCMB 'YYYY-MM' formatına çevirir."""
    # TCMB formatları: "2024-01" veya "2024-01-01"
    parts = tarih_str.strip().split("-")
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1].zfill(2)}"
    return tarih_str


def son_deger_al(liste: list[dict]) -> dict | None:
    if not liste:
        return None
    return liste[-1]


def yillik_degisim_hesapla(liste: list[dict]) -> list[dict]:
    """Her veri noktası için yıllık değişim yüzdesini ekler."""
    tarih_map = {d["tarih"]: d["deger"] for d in liste}
    sonuc = []
    for item in liste:
        tarih = item["tarih"]
        yil, ay = tarih.split("-")
        gecen_yil_tarih = f"{int(yil)-1}-{ay}"
        gecen_yil_deger = tarih_map.get(gecen_yil_tarih)
        yillik_degisim = None
        if gecen_yil_deger and gecen_yil_deger != 0:
            yillik_degisim = round(
                (item["deger"] - gecen_yil_deger) / gecen_yil_deger * 100, 2
            )
        sonuc.append({**item, "yillik_degisim_yuzde": yillik_degisim})
    return sonuc


def main():
    if not API_KEY:
        print("HATA: TCMB_API_KEY ortam değişkeni ayarlanmamış!")
        print("Alış: https://evds2.tcmb.gov.tr/index.php?/evds/login")
        raise SystemExit(1)

    baslangic, bitis = tarih_aralik()
    print(f"Tarih aralığı: {baslangic} → {bitis}")
    print(f"API key: {API_KEY[:6]}***")

    tum_veri = {}

    # Her seriyi çek
    for isim, kod in SERILER.items():
        print(f"Çekiliyor: {isim} ({kod})...")
        veri = evds_cek(kod, baslangic, bitis)
        veri = yillik_degisim_hesapla(veri)
        tum_veri[isim] = veri
        print(f"  → {len(veri)} kayıt")

    # Özet istatistikler
    ozet = {}
    for isim, veri in tum_veri.items():
        son = son_deger_al(veri)
        if son:
            ozet[isim] = {
                "son_tarih": son["tarih"],
                "son_deger": son["deger"],
                "yillik_degisim_yuzde": son.get("yillik_degisim_yuzde"),
            }

    # data/evds_data.json dosyasına yaz
    cikti = {
        "meta": {
            "guncelleme_zamani": datetime.now().isoformat(),
            "veri_kaynagi": "TCMB EVDS",
            "kaynak_url": "https://evds2.tcmb.gov.tr",
            "donem": f"{baslangic} - {bitis}",
        },
        "ozet": ozet,
        "seriler": tum_veri,
    }

    cikti_dosya = DATA_DIR / "evds_data.json"
    with open(cikti_dosya, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Veri kaydedildi: {cikti_dosya}")
    print(f"   Toplam {sum(len(v) for v in tum_veri.values())} kayıt")


if __name__ == "__main__":
    main()
