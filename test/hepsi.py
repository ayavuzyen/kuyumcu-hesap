"""Bütün sınamaları sırayla koşar ve teslim paketini denetler. Çalıştır: python test/hepsi.py
Kritik bulguda çıkış kodu sıfırdan farklıdır.
"""
from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Depoda bulunabilecek dosyalar. Beyaz liste: burada olmayan dosya pakete girmez,
# unutulan kişisel bir not ya da sınama artığı yayına çıkmasın.
BEYAZ_LISTE = {
    "index.html", "hesap.js", "sw.js", "manifest.webmanifest", "ikon-192.png", "ikon-512.png",
    "fiyatlar.json", "BENIOKU.md", ".gitignore", ".gitattributes",
    ".github/workflows/fiyat.yml", "araclar/fiyat_cek.py",
    "test/hesap.test.js", "test/test_fiyat_cek.py", "test/mutasyon.py", "test/hepsi.py",
    "test/_senaryo.py", "test/fiyatlar.iyi.json",
}


def adim(ad: str, komut: list[str], zaman: int = 300) -> bool:
    print(f"\n== {ad}", flush=True)
    r = subprocess.run(komut, cwd=KOK, capture_output=True, text=True, encoding="utf-8",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"), timeout=zaman)
    cikti = (r.stdout + r.stderr).strip().splitlines()
    ozet = [s for s in cikti if re.search(r"^ℹ (tests|pass|fail)|^Ran |^OK|^FAILED|Mutasyon:|KAÇTI|UYGULANAMADI|^✖", s)]
    print("\n".join(ozet[-12:]) or "\n".join(cikti[-15:]))
    print("TAMAM" if r.returncode == 0 else f"HATA (çıkış {r.returncode})")
    return r.returncode == 0


def teslim_denetimi() -> bool:
    print("\n== Teslim paketi", flush=True)
    sorun: list[str] = []
    r = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=KOK, capture_output=True, text=True, encoding="utf-8")
    dosyalar = set(r.stdout.split("\n")) - {""} if r.returncode == 0 else None
    if dosyalar is None:
        sorun.append("git ls-files çalışmadı (depo başlatılmamış mı?)")
    else:
        fazla = sorted(dosyalar - BEYAZ_LISTE)
        eksik = sorted(BEYAZ_LISTE - dosyalar)
        if fazla:
            sorun.append(f"beyaz listede olmayan dosya: {fazla}")
        if eksik:
            sorun.append(f"eksik dosya: {eksik}")

    html = open(os.path.join(KOK, "index.html"), encoding="utf-8").read()
    for ref in re.findall(r'(?:src|href)="([^"#:]+)"', html):
        if not os.path.exists(os.path.join(KOK, ref)):
            sorun.append(f"index.html var olmayan dosyaya bağlanıyor: {ref}")
    if "https://raw.githubusercontent.com" not in re.search(r'connect-src ([^;]+)', html).group(1):
        sorun.append("CSP connect-src fiyat adresine izin vermiyor")
    if re.search(r"innerHTML\s*=", html):
        sorun.append("index.html innerHTML atıyor (kullanıcı metni HTML'e girebilir)")

    man = json.load(open(os.path.join(KOK, "manifest.webmanifest"), encoding="utf-8"))
    for ik in man["icons"]:
        yol = os.path.join(KOK, ik["src"])
        with open(yol, "rb") as f:
            bas = f.read(24)
        w, h = struct.unpack(">II", bas[16:24])
        if f"{w}x{h}" != ik["sizes"]:
            sorun.append(f"{ik['src']} boyutu {w}x{h}, manifest {ik['sizes']} diyor")

    sw = open(os.path.join(KOK, "sw.js"), encoding="utf-8").read()
    kabuk = json.loads(re.search(r"const KABUK = (\[.*?\]);", sw).group(1))
    for k in kabuk:
        if k != "./" and not os.path.exists(os.path.join(KOK, k)):
            sorun.append(f"sw.js önbelleğe olmayan dosyayı alıyor: {k}")

    surum = re.search(r'const SURUM = "([\d.]+)"', open(os.path.join(KOK, "hesap.js"), encoding="utf-8").read()).group(1)
    for yol in ("index.html", "sw.js", "BENIOKU.md"):
        for m in re.findall(r"\b\d+\.\d+\.\d+\b", open(os.path.join(KOK, yol), encoding="utf-8").read()):
            if m != surum and yol != "BENIOKU.md":
                sorun.append(f"{yol} içinde ikinci bir sürüm dizesi: {m}")

    for yol in BEYAZ_LISTE:
        p = os.path.join(KOK, yol)
        if yol.endswith((".js", ".py", ".html", ".json", ".yml", ".md")) and os.path.exists(p):
            b = open(p, "rb").read()
            if b"\r\n" in b:
                sorun.append(f"{yol} CRLF satır sonu içeriyor")
            # Bu dosya kendi desenine takılmasın diye atlanır.
            if yol != "test/hepsi.py" and re.search(rb"(gho_|ghp_|github_pat_)[A-Za-z0-9]{10,}|ayavu@|\\Users\\", b):
                sorun.append(f"{yol} kişisel iz ya da sır içeriyor")

    print("\n".join(f"  - {s}" for s in sorun) or f"  {len(BEYAZ_LISTE)} dosya, beyaz liste, bağlantılar, ikonlar, sürüm {surum}: temiz")
    print("TAMAM" if not sorun else "HATA")
    return not sorun


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sonuc = [
        adim("Hesap çekirdeği (Node)", ["node", "--test", "test/hesap.test.js"]),
        adim("Fiyat çekici, düşman ağ", [sys.executable, "test/test_fiyat_cek.py"]),
        adim("Mutasyon", [sys.executable, "test/mutasyon.py"], zaman=900),
        teslim_denetimi(),
    ]
    print(f"\nSONUÇ: {sum(sonuc)}/{len(sonuc)} aşama geçti")
    return 0 if all(sonuc) else 1


if __name__ == "__main__":
    sys.exit(main())
