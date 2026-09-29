"""Altınkaynak fiyatlarını çekip uygulamanın okuyacağı fiyatlar.json dosyasını yazar.

GitHub Actions'ta 5 dakikada bir çalışır. Altınkaynak tarayıcıya başka siteden
veri vermediği (CORS başlığı yok) için sayfa fiyatı doğrudan çekemez; bu betik
aradaki aktarıcıdır.

Kural: kaynak cevabı biçim, aralık ve tutarlılık denetiminden geçmezse çıktı
dosyasına DOKUNULMAZ ve çıkış kodu sıfırdan farklı olur. Bozuk bir fiyatı
"güncel" diye yayımlamak, eski ama doğru fiyatı bırakmaktan kötüdür.

Çıkış kodları: 0 yazıldı · 2 kaynak/biçim hatası · 3 ağ hatası · 4 çıktı yazılamadı
Yalnız standart kütüphane kullanır.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

KAYNAK_URL = "https://static.altinkaynak.com/public/Gold"
AZAMI_GOVDE = 1_000_000          # bayt; kaynak ~3 KB döner
FIYAT_MIN, FIYAT_MAX = 100.0, 10_000_000.0
ISTANBUL = timezone(timedelta(hours=3))

# Uygulamadaki ad → Altınkaynak kodu. Yalnız "has" zorunlu.
KODLAR = {"has": "HH_T", "ayar14": "P14", "ayar18": "P18", "bilezik22": "PB", "gram": "GA"}
ORAN = {"ayar14": (0.45, 0.95), "ayar18": (0.6, 1.05), "bilezik22": (0.8, 1.15), "gram": (0.9, 1.2)}


class KaynakHatasi(Exception):
    pass


def tr_sayi(s: object) -> float:
    """'6.511,34' → 6511.34. Başka biçim kabul edilmez (tahmin edilmez)."""
    if not isinstance(s, str) or not re.fullmatch(r"\d{1,3}(\.\d{3})*(,\d+)?", s.strip()):
        raise KaynakHatasi(f"sayı biçimi beklenmedik: {s!r}")
    return float(s.strip().replace(".", "").replace(",", "."))


def cift(kayit: dict) -> dict:
    alis, satis = tr_sayi(kayit.get("Alis")), tr_sayi(kayit.get("Satis"))
    if not (FIYAT_MIN <= alis <= FIYAT_MAX and FIYAT_MIN <= satis <= FIYAT_MAX):
        raise KaynakHatasi(f"fiyat aralık dışında: {alis} / {satis}")
    if satis < alis or satis / alis >= 1.5:
        raise KaynakHatasi(f"alış/satış tutarsız: {alis} / {satis}")
    return {"alis": alis, "satis": satis}


def zaman_oku(s: object) -> datetime:
    if not isinstance(s, str):
        raise KaynakHatasi("güncellenme zamanı yok")
    try:
        return datetime.strptime(s.strip(), "%d.%m.%Y %H:%M:%S").replace(tzinfo=ISTANBUL)
    except ValueError as e:
        raise KaynakHatasi(f"güncellenme zamanı okunamadı: {s!r}") from e


def donustur(ham: object, simdi: datetime) -> tuple[dict, list[str]]:
    if not isinstance(ham, list) or not ham:
        raise KaynakHatasi("cevap boş ya da liste değil")
    kayitlar = {k.get("Kod"): k for k in ham if isinstance(k, dict) and isinstance(k.get("Kod"), str)}
    if KODLAR["has"] not in kayitlar:
        raise KaynakHatasi("has altın (HH_T) kaydı yok")

    uyarilar: list[str] = []
    has_kayit = kayitlar[KODLAR["has"]]
    cikti: dict = {"kaynak": "Altınkaynak", "has": cift(has_kayit)}
    zaman = zaman_oku(has_kayit.get("GuncellenmeZamani"))
    if zaman - simdi > timedelta(minutes=10):
        raise KaynakHatasi(f"kaynak saati ileri tarihte: {zaman.isoformat()}")

    for ad, (lo, hi) in ORAN.items():
        k = kayitlar.get(KODLAR[ad])
        if k is None:
            uyarilar.append(f"{ad} yok")
            continue
        try:
            c = cift(k)
        except KaynakHatasi as e:
            uyarilar.append(f"{ad} atlandı: {e}")
            continue
        r = c["satis"] / cikti["has"]["satis"]
        if not lo <= r <= hi:
            uyarilar.append(f"{ad} has fiyatıyla tutarsız (oran {r:.3f}), atlandı")
            continue
        cikti[ad] = c

    cikti["zaman"] = zaman.isoformat()
    cikti["cekilme"] = simdi.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return cikti, uyarilar


def indir(url: str, zaman_asimi: float) -> object:
    istek = urllib.request.Request(url, headers={"User-Agent": "altin-takas-fiyat/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(istek, timeout=zaman_asimi) as c:
            if c.status != 200:
                raise KaynakHatasi(f"HTTP {c.status}")
            govde = c.read(AZAMI_GOVDE + 1)
    except urllib.error.HTTPError as e:
        raise KaynakHatasi(f"HTTP {e.code}") from e
    if len(govde) > AZAMI_GOVDE:
        raise KaynakHatasi("cevap beklenenden çok büyük")
    try:
        return json.loads(govde.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise KaynakHatasi(f"JSON değil: {govde[:80]!r}") from e


def atomik_yaz(yol: str, veri: dict) -> None:
    klasor = os.path.dirname(os.path.abspath(yol))
    fd, gecici = tempfile.mkstemp(prefix=".fiyat-", suffix=".json", dir=klasor)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:   # Windows'ta da LF
            json.dump(veri, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(gecici, yol)
    except BaseException:
        if os.path.exists(gecici):
            os.remove(gecici)
        raise


def main(argv: list[str] | None = None) -> int:
    for akis in (sys.stdout, sys.stderr):   # Windows konsolunda Türkçe karakter bozulmasın
        if hasattr(akis, "reconfigure"):
            akis.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Altınkaynak fiyatlarını fiyatlar.json'a yazar")
    p.add_argument("--url", default=KAYNAK_URL)
    p.add_argument("--cikti", default="fiyatlar.json")
    p.add_argument("--zaman-asimi", type=float, default=15.0)
    a = p.parse_args(argv)
    try:
        ham = indir(a.url, a.zaman_asimi)
        veri, uyarilar = donustur(ham, datetime.now(timezone.utc))
    except KaynakHatasi as e:
        print(f"HATA: kaynak kabul edilmedi, dosyaya dokunulmadı: {e}", file=sys.stderr)
        return 2
    # http.client.HTTPException OSError değildir: bozuk durum satırı (BadStatusLine)
    # yakalanmazsa betik ham hatayla çöküyordu (sınama: test_cop_durum_satiri).
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as e:
        print(f"HATA: ağ: {type(e).__name__}: {e}", file=sys.stderr)
        return 3
    try:
        atomik_yaz(a.cikti, veri)
    except OSError as e:
        print(f"HATA: çıktı yazılamadı ({a.cikti}): {e}", file=sys.stderr)
        return 4
    for u in uyarilar:
        print(f"UYARI: {u}", file=sys.stderr)
    print(f"Yazıldı: {a.cikti} · has {veri['has']['alis']} / {veri['has']['satis']} · {veri['zaman']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
