"""
TCMB EVDS veri çekme scripti.
GitHub Actions tarafından haftalık çalıştırılır ve data/ klasörüne JSON yazar.

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

GECMIS_AY = 36  # 3 yıl geriye

# TCMB EVDS seri kodları (doğrulanmış)
SERILER = {
    "konut_endeks_genel":    "TP.HKFE01",   # Konut Fiyat Endeksi - Türkiye
    "konut_endeks_istanbul": "TP.HKFE02",   # KFE - İstanbul
    "konut_endeks_ankara":   "TP.HKFE03",   # KFE - Ankara
    "konut_endeks_izmir":    "TP.HKFE04",   # KFE - İzmir
    "kira_endeks":           "TP.FG.J0",    # Kira endeksi (TÜFE alt kalemi)
    "mortgage_faiz":         "TP.KKB08",    # Konut kredisi faiz oranı
    "insaat_maliyeti":       "TP.YBU01",    # Yurt içi üretici fiyat endeksi (inşaat)
}


def tarih_aralik():
    """Son GECMIS_AY aylık tarih aralığı (DD-MM-YYYY formatında)."""
    bitis = datetime.now()
    baslangic = bitis - timedelta(days=GECMIS_AY * 30)
    return baslangic.strftime("%d-%m-%Y"), bitis.strftime("%d-%m-%Y")


def evds_cek(seri_kodu: str, baslangic: str, bitis: str) -> list:
    """
    TCMB EVDS'den tek bir seri çeker.
    Doğru URL formatı: /service/evds/series=KOD&startDate=...&key=...
    (series kodu query param değil, URL path'inin parçası)
    """
    url = (
        f"{BASE_URL}/series={seri_kodu}"
        f"&startDate={baslangic}"
        f"&endDate={bitis}"
        f"&type=json"
        f"&key={API_KEY}"
        f"&frequency=5"       # 5 = aylık
        f"&formulas=0"        # 0 = seviye
        f"&aggregationTypes=avg"
    )
    try:
        r = httpx.get(url, timeout=30)
        print(f"  HTTP {r.status_code} | URL: {url[:80]}...")
        if r.status_code != 200:
            print(f"  Hata yanıtı: {r.text[:200]}")
            return []

        raw = r.json()
        items = raw.get("items", [])
        if not items:
            print(f"  Uyarı: Boş items listesi geldi. Ham yanıt: {str(raw)[:200]}")
            return []

        result = []
        for item in items:
            tarih = item.get("Tarih", "")
            # Seri değeri key olarak seri kodu kullanılıyor
            deger = item.get(seri_kodu)
            if tarih and deger is not None:
                try:
                    result.append({
                        "tarih": _tcmb_tarih_cevir(tarih),
                        "deger": float(str(deger).replace(",", ".")),
                    })
                except (ValueError, TypeError):
                    pass

        return sorted(result, key=lambda x: x["tarih"])

    except Exception as e:
        print(f"  HATA [{seri_kodu}]: {type(e).__name__}: {e}")
        return []


def _tcmb_tarih_cevir(tarih_str: str) -> str:
    """TCMB tarih formatını 'YYYY-MM' formatına çevirir."""
    # TCMB formatları: "2024-01" veya "01-2024" veya "2024-01-01"
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
        yil, ay = item["tarih"].split("-")
        gecen_yil = f"{int(yil)-1}-{ay}"
        gecen_deger = tarih_map.get(gecen_yil)
        if gecen_deger and gecen_deger != 0:
            degisim = round((item["deger"] - gecen_deger) / gecen_deger * 100, 2)
        else:
            degisim = None
        sonuc.append({**item, "yillik_degisim_yuzde": degisim})
    return sonuc


def main():
    if not API_KEY:
        print("HATA: TCMB_API_KEY ortam değişkeni ayarlanmamış!")
        raise SystemExit(1)

    baslangic, bitis = tarih_aralik()
    print(f"Tarih aralığı: {baslangic} → {bitis}")
    print(f"API key: {API_KEY[:6]}***\n")

    tum_veri = {}
    ozet = {}

    for isim, kod in SERILER.items():
        print(f"Çekiliyor: {isim} ({kod})...")
        veri = evds_cek(kod, baslangic, bitis)
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

    toplam = sum(len(v) for v in tum_veri.values())
    print(f"✅ Kaydedildi: {cikti_dosya}")
    print(f"   Toplam {toplam} kayıt, {len([v for v in tum_veri.values() if v])} seri başarılı")

    if toplam == 0:
        print("\n⚠️  Hiç veri gelmedi! Seri kodlarını veya API key'i kontrol et.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
