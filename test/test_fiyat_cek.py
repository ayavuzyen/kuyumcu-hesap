"""Fiyat çekicinin düşman ağ sınaması. Çalıştır: python -m unittest test/test_fiyat_cek.py

Gerçek Altınkaynak'a istek ATILMAZ; yerel sahte sunucu her senaryoyu üretir.
Kural: kötü her cevapta çıktı dosyasına dokunulmamalı ve çıkış kodu sıfır olmamalı.
FIYAT_CEK_YOLU verilirse o dosya sınanır (mutasyon sınaması bunu kullanır).
"""
from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YOL = os.environ.get("FIYAT_CEK_YOLU", os.path.join(KOK, "araclar", "fiyat_cek.py"))
spec = importlib.util.spec_from_file_location("fiyat_cek", YOL)
fc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fc)

IST = timezone(timedelta(hours=3))


def tr(n: float) -> str:
    s = f"{n:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def kayit(kod: str, alis: float, satis: float, zaman: str | None = None) -> dict:
    z = zaman or datetime.now(IST).strftime("%d.%m.%Y %H:%M:%S")
    return {"Alis": tr(alis), "Satis": tr(satis), "Kod": kod, "Aciklama": kod, "GuncellenmeZamani": z, "IsMobile": True}


def iyi_liste(**degis) -> list:
    k = {
        "HH_T": kayit("HH_T", 6509.47, 6559.94), "P14": kayit("P14", 3678.95, 4180.00),
        "P18": kayit("P18", 4490.07, 5250.00), "PB": kayit("PB", 5936.44, 6390.00), "GA": kayit("GA", 6476.93, 6592.41),
        "AG_T": kayit("AG_T", 86.73, 96.40),
    }
    for kod, v in degis.items():
        if v is None:
            k.pop(kod, None)
        else:
            k[kod] = v
    return list(k.values())


SENARYO: dict = {}


class Sahte(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        s = SENARYO[self.path.strip("/")]
        tur = s[0]
        if tur == "json":
            self._gonder(200, json.dumps(s[1], ensure_ascii=False).encode())
        elif tur == "ham":
            self._gonder(s[1], s[2])
        elif tur == "yavas":
            time.sleep(s[1])
            self._gonder(200, json.dumps(iyi_liste()).encode())
        elif tur == "kopar":
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
        elif tur == "cop_durum":
            self.wfile.write(b"ZZZ garbage\r\n\r\n")
        elif tur == "yarim":
            self.send_response(200)
            self.send_header("Content-Length", "5000")
            self.end_headers()
            self.wfile.write(b'[{"Alis":"6.5')
            self.wfile.flush()
            self.connection.shutdown(socket.SHUT_RDWR)

    def _gonder(self, kod: int, govde: bytes):
        self.send_response(kod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(govde)))
        self.end_headers()
        self.wfile.write(govde)


class FiyatCekDusmanAg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sunucu = ThreadingHTTPServer(("127.0.0.1", 0), Sahte)
        cls.sunucu.daemon_threads = True
        cls.port = cls.sunucu.server_address[1]
        threading.Thread(target=cls.sunucu.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.sunucu.shutdown()
        cls.sunucu.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.cikti = os.path.join(self.tmp.name, "fiyatlar.json")
        self.onceki = b'{"onceki": true}'
        with open(self.cikti, "wb") as f:
            f.write(self.onceki)

    def tearDown(self):
        self.tmp.cleanup()

    def calistir(self, ad: str, senaryo, zaman_asimi: float = 3.0) -> int:
        SENARYO[ad] = senaryo
        import io, contextlib
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            try:
                return fc.main(["--url", f"http://127.0.0.1:{self.port}/{ad}", "--cikti", self.cikti, "--zaman-asimi", str(zaman_asimi)])
            except SystemExit as e:  # argparse
                return int(e.code or 0)

    def dokunulmadi(self):
        with open(self.cikti, "rb") as f:
            self.assertEqual(f.read(), self.onceki, "kötü cevapta çıktı dosyası değişti")
        self.assertEqual([n for n in os.listdir(self.tmp.name) if n.startswith(".fiyat-")], [], "geçici dosya kaldı")

    def reddedilmeli(self, ad, senaryo, zaman_asimi=3.0):
        kod = self.calistir(ad, senaryo, zaman_asimi)
        self.assertNotEqual(kod, 0, f"{ad}: kötü cevap kabul edildi")
        self.dokunulmadi()
        return kod

    # ---- iyi yol ----
    def test_iyi_cevap_yazilir_ve_uygulama_dogrulayicisindan_gecer(self):
        self.assertEqual(self.calistir("iyi", ("json", iyi_liste())), 0)
        with open(self.cikti, encoding="utf-8") as f:
            v = json.load(f)
        self.assertEqual(v["has"], {"alis": 6509.47, "satis": 6559.94})
        self.assertEqual(v["ayar14"]["satis"], 4180.0)
        self.assertEqual(v["kaynak"], "Altınkaynak")
        # Çapraz sınama: sayfanın doğrulayıcısı bu dosyayı kabul ediyor mu?
        js = ("const H=require(process.argv[1]);const v=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));"
              "const d=H.fiyatDogrula(v,Date.now());if(!d.ok||d.uyarilar.length){console.log(JSON.stringify(d));process.exit(1)}")
        r = subprocess.run(["node", "-e", js, os.path.join(KOK, "hesap.js"), self.cikti], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_bom_ile_gelen_json_okunur(self):
        self.assertEqual(self.calistir("bom", ("ham", 200, b"\xef\xbb\xbf" + json.dumps(iyi_liste()).encode())), 0)

    def test_yan_kalem_bozuksa_has_yine_yazilir(self):
        # P14: alış/satış makası normal ama has fiyatına satılıyor → yalnız ORAN denetimi yakalar.
        liste = iyi_liste(P14=kayit("P14", 6500.0, 6559.0), PB=kayit("PB", 0, 0), GA=None)
        self.assertEqual(self.calistir("yan", ("json", liste)), 0)
        with open(self.cikti, encoding="utf-8") as f:
            v = json.load(f)
        self.assertNotIn("ayar14", v)
        self.assertNotIn("bilezik22", v)
        self.assertNotIn("gram", v)
        self.assertIn("ayar18", v)

    # ---- HTTP hataları ----
    def test_http_hatalari(self):
        for kod in (500, 502, 503, 403, 404, 429, 401):
            with self.subTest(kod=kod):
                # Sunucu cevap verdi ama reddetti: kaynak hatası (2), ağ hatası (3) değil.
                self.assertEqual(self.reddedilmeli(f"h{kod}", ("ham", kod, b"hata")), 2)

    def test_cloudflare_engel_sayfasi(self):
        self.reddedilmeli("cf", ("ham", 200, b"<!DOCTYPE html><title>Just a moment...</title>"))

    # ---- biçim ----
    def test_bozuk_bicimler(self):
        simdi = datetime.now(IST)
        durumlar = {
            "yarim_json": ("ham", 200, b'[{"Kod":"HH_T"'),
            "bos_govde": ("ham", 200, b""),
            "bos_liste": ("json", []),
            "sozluk": ("json", {"HH_T": {}}),
            "null": ("json", None),
            "has_yok": ("json", iyi_liste(HH_T=None)),
            "has_sifir": ("json", iyi_liste(HH_T=kayit("HH_T", 0, 0))),
            "has_harf": ("json", iyi_liste(HH_T={**kayit("HH_T", 1, 1), "Alis": "abc"})),
            "has_sayi_tipi": ("json", iyi_liste(HH_T={**kayit("HH_T", 1, 1), "Alis": 6509.47, "Satis": 6559.94})),
            "nokta_ondalik": ("json", iyi_liste(HH_T={**kayit("HH_T", 1, 1), "Alis": "6509.47", "Satis": "6559.94"})),
            "satis_kucuk": ("json", iyi_liste(HH_T=kayit("HH_T", 6600, 6500))),
            "makas_genis": ("json", iyi_liste(HH_T=kayit("HH_T", 3000, 6500))),
            "has_devasa": ("json", iyi_liste(HH_T=kayit("HH_T", 6.5e9, 6.6e9))),
            "zaman_yok": ("json", iyi_liste(HH_T={**kayit("HH_T", 6509.47, 6559.94), "GuncellenmeZamani": None})),
            "zaman_cop": ("json", iyi_liste(HH_T=kayit("HH_T", 6509.47, 6559.94, "yarın öğlen"))),
            "zaman_ileri": ("json", iyi_liste(HH_T=kayit("HH_T", 6509.47, 6559.94, (simdi + timedelta(days=1)).strftime("%d.%m.%Y %H:%M:%S")))),
            "kod_sayi": ("json", [{**kayit("HH_T", 6509.47, 6559.94), "Kod": 5}]),
            "eleman_cop": ("json", ["x", 5, None, [], {"Kod": None}]),
            "utf16": ("ham", 200, json.dumps(iyi_liste()).encode("utf-16")),
        }
        for ad, s in durumlar.items():
            with self.subTest(ad=ad):
                self.reddedilmeli(ad, s)

    def test_devasa_govde_acik_iletiyle_reddedilir(self):
        # İki katman: okuma 1 MB'ta kesilir (bellek), boyut denetimi açık ileti verir.
        import io, contextlib
        SENARYO["devasa"] = ("json", iyi_liste() + [kayit(f"X{i}", 100, 101) for i in range(12000)])
        hata = io.StringIO()
        with contextlib.redirect_stderr(hata), contextlib.redirect_stdout(io.StringIO()):
            kod = fc.main(["--url", f"http://127.0.0.1:{self.port}/devasa", "--cikti", self.cikti])
        self.assertEqual(kod, 2)
        self.assertIn("çok büyük", hata.getvalue())
        self.dokunulmadi()

    # ---- bağlantı ----
    def test_yavas_cevap_zaman_asimina_ugrar(self):
        t = time.monotonic()
        self.reddedilmeli("yavas", ("yavas", 4), zaman_asimi=1)
        self.assertLess(time.monotonic() - t, 3.5, "zaman aşımı işlemedi")

    def test_baglanti_koparsa(self):
        self.assertEqual(self.reddedilmeli("kopar", ("kopar",)), 3)

    def test_cop_durum_satiri(self):
        self.reddedilmeli("cop", ("cop_durum",))

    def test_yarim_govde(self):
        self.reddedilmeli("yarim", ("yarim",))

    def test_sunucu_yok(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        bos_port = s.getsockname()[1]
        s.close()
        import io, contextlib
        with contextlib.redirect_stderr(io.StringIO()):
            kod = fc.main(["--url", f"http://127.0.0.1:{bos_port}/x", "--cikti", self.cikti, "--zaman-asimi", "2"])
        self.assertNotEqual(kod, 0)
        self.dokunulmadi()

    def test_cikti_klasoru_yoksa_cokmez(self):
        SENARYO["iyi2"] = ("json", iyi_liste())
        yol = os.path.join(self.tmp.name, "yok", "fiyatlar.json")
        r = subprocess.run([sys.executable, YOL, "--url", f"http://127.0.0.1:{self.port}/iyi2", "--cikti", yol],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr, "ham Python hatası kullanıcıya gitti")

    def test_komut_satirindan_turkce_cikti(self):
        SENARYO["iyi3"] = ("json", iyi_liste())
        r = subprocess.run([sys.executable, YOL, "--url", f"http://127.0.0.1:{self.port}/iyi3", "--cikti", self.cikti],
                           capture_output=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Yazıldı", r.stdout)


if __name__ == "__main__":
    unittest.main()
