"""Mutasyon sınaması: her korumayı KOPYADA bilerek bozar ve sınamaların kırıldığını doğrular.
Kırılmayan sınama o korumayı sınamıyor demektir. Çalıştır: python test/mutasyon.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALISMA = os.path.join(KOK, "test", "_calisma")

# (dosya, ad, bozulacak metin, yerine)
MUTASYONLAR = [
    ("hesap.js", "kısmi toplam koruması", "if (sorunlar.length) return { hazir: false", "if (false) return { hazir: false"),
    ("hesap.js", "birden fazla virgül", "if (virgul > 1) return", "if (virgul > 9) return"),
    ("hesap.js", "fiyat binlik noktası", 'if (tur === "fiyat" && /^\\d{1,3}(\\.\\d{3})+$/.test(s))', "if (false)"),
    ("hesap.js", "gram üst sınırı", "if (v > SINIR.gramMax) return", "if (false) return"),
    ("hesap.js", "gram sıfır/eksi", "if (!(v > 0)) return { ok: false, hata: \"Gram", "if (false) return { ok: false, hata: \"Gram"),
    ("hesap.js", "milyem 585→0,585", "if (v > 1 && v <= 1000) {", "if (false) {"),
    ("hesap.js", "ayar prototip koruması", "Object.prototype.hasOwnProperty.call(AYAR, String(p.ayar))", "(String(p.ayar) in AYAR)"),
    ("hesap.js", "içerideki boşluk", 'return String(s).normalize("NFKC").trim();', 'return String(s).normalize("NFKC").replace(/\\s/g, "");'),
    ("hesap.js", "rakam yok", 'if (!/[0-9]/.test(s)) return', "if (false) return"),
    ("hesap.js", "yalnız rakam", "if (!/^[0-9.,]+$/.test(s))", "if (false)"),
    ("hesap.js", "para: siz öderseniz satış", 'sonuc.yon === "siz" ? fiyat.has.satis : fiyat.has.alis', "fiyat.has.alis"),
    ("hesap.js", "piyasa: 14 ayar satış fiyatı", "alinanTL += f && Number.isFinite(f.satis) ? r.gram * f.satis : r.teorikHas * fiyat.has.satis;", "alinanTL += r.teorikHas * fiyat.has.satis;"),
    ("hesap.js", "fiyat: satış ≥ alış", "c.satis >= c.alis && c.satis / c.alis < 1.5", "true"),
    ("hesap.js", "fiyat: sayı denetimi (metin fiyat)", "Number.isFinite(c.alis) && Number.isFinite(c.satis) &&", ""),
    ("hesap.js", "fiyat: ileri tarih", "if (zamanMs - simdi > SINIR.gelecekTolDk * 60000) return", "if (false) return"),
    ("hesap.js", "fiyat: oran tutarlılığı", "if (r < oran[k][0] || r > oran[k][1]) {", "if (false) {"),
    ("hesap.js", "fiyat: eski işareti", "eski: yasDk > SINIR.eskiDk", "eski: false"),
    ("hesap.js", "fiyat: has zorunlu", 'if (zorunlu) return { hata: `${ETIKET[ad] || ad} fiyatı yok` }; return {};', "return {};"),
    ("hesap.js", "fiyat: __proto__", "const c = o && Object.prototype.hasOwnProperty.call(o, ad) ? o[ad] : undefined;", "const c = o ? o[ad] : undefined;"),
    ("hesap.js", "biçim: NaN", 'if (!Number.isFinite(n)) return "–";', ""),
    ("araclar/fiyat_cek.py", "çekici: sayı biçimi", r'not re.fullmatch(r"\d{1,3}(\.\d{3})*(,\d+)?", s.strip())', "False"),
    ("araclar/fiyat_cek.py", "çekici: alış/satış", "if satis < alis or satis / alis >= 1.5:", "if False:"),
    ("araclar/fiyat_cek.py", "çekici: has zorunlu", 'if KODLAR["has"] not in kayitlar:', "if False:"),
    ("araclar/fiyat_cek.py", "çekici: ileri tarih", "if zaman - simdi > timedelta(minutes=10):", "if False:"),
    ("araclar/fiyat_cek.py", "çekici: oran", "if not lo <= r <= hi:", "if False:"),
    ("araclar/fiyat_cek.py", "çekici: HTTP durum", "except urllib.error.HTTPError as e:\n        raise KaynakHatasi", "except ZeroDivisionError as e:\n        raise KaynakHatasi"),
    ("araclar/fiyat_cek.py", "çekici: boyut sınırı", "if len(govde) > AZAMI_GOVDE:", "if False:"),
    ("araclar/fiyat_cek.py", "çekici: HTTPException", "OSError, http.client.HTTPException) as e:", "OSError) as e:"),
    ("araclar/fiyat_cek.py", "çekici: atomik yazma", "        os.replace(gecici, yol)\n", "        os.replace(gecici, yol)\n        raise OSError('yarım')\n"),
]


def sinama(dosya: str, kopya: str) -> tuple[bool, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if dosya == "hesap.js":
        env["HESAP_YOLU"] = kopya
        r = subprocess.run(["node", "--test", os.path.join(KOK, "test", "hesap.test.js")], capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
    else:
        env["FIYAT_CEK_YOLU"] = kopya
        r = subprocess.run([sys.executable, os.path.join(KOK, "test", "test_fiyat_cek.py")], capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
    return r.returncode != 0, (r.stdout + r.stderr)[-300:]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(CALISMA, exist_ok=True)
    yakalanan, kacan = 0, []
    try:
        for dosya, ad, eski, yeni in MUTASYONLAR:
            with open(os.path.join(KOK, dosya), encoding="utf-8", newline="") as f:
                kaynak = f.read()
            if kaynak.count(eski) != 1:
                print(f"UYGULANAMADI  {ad}: bozulacak metin {kaynak.count(eski)} kez bulundu")
                kacan.append(ad)
                continue
            kopya = os.path.join(CALISMA, os.path.basename(dosya))
            with open(kopya, "w", encoding="utf-8", newline="") as f:
                f.write(kaynak.replace(eski, yeni))
            kirildi, _ = sinama(dosya, kopya)
            print(f"{'YAKALANDI' if kirildi else 'KAÇTI    '}  {ad}")
            if kirildi:
                yakalanan += 1
            else:
                kacan.append(ad)
    finally:
        shutil.rmtree(CALISMA, ignore_errors=True)
    print(f"\nMutasyon: {yakalanan}/{len(MUTASYONLAR)} yakalandı")
    return 0 if not kacan else 1


if __name__ == "__main__":
    sys.exit(main())
