// Hesap çekirdeği sınamaları. Çalıştır: node --test test/
// HESAP_YOLU ortam değişkeni verilirse o dosya sınanır (mutasyon sınaması bunu kullanır).
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const H = require(process.env.HESAP_YOLU || path.join(__dirname, "..", "hesap.js"));

const yakin = (a, b, tol = 1e-9) => assert.ok(Math.abs(a - b) <= tol, `${a} ≈ ${b}`);

// ---------------- Sayı okuma ----------------
test("gram: kabul edilen yazımlar", () => {
  const iyi = {
    "23,61": 23.61, "23.61": 23.61, " 23,61 ": 23.61, "23": 23, "0,5": 0.5, ".5": 0.5, ",5": 0.5,
    "23,": 23, "23.": 23, "1.234,5": 1234.5, "2000": 2000, "1.250": 1.25, "１２": 12, "0,001": 0.001
  };
  for (const [g, v] of Object.entries(iyi)) {
    const r = H.sayiOku(g, "gram");
    assert.ok(r.ok, `${JSON.stringify(g)} kabul edilmeli: ${r.hata}`);
    yakin(r.deger, v);
  }
});

test("gram: reddedilen yazımlar (sessizce sayıya dönmemeli)", () => {
  const kotu = ["0", "0,000", "-5", "+5", "5e2", "1e3", "Infinity", "NaN", "0x10", "abc", "1,2,3", "1.2.3",
    "12,3.4", "2000,01", "2 3", "23 61", "٢٣", "<script>", "1".repeat(25), "99999999999999999999",
    ",", ".", ",.", "1,,2", "..5", "5..", "½", "23,61g", "₺23"];
  for (const g of kotu) {
    const r = H.sayiOku(g, "gram");
    assert.equal(r.ok, false, `${JSON.stringify(g)} reddedilmeli, ${r.deger} okundu`);
    assert.equal(typeof r.hata, "string");
  }
});

test("iki katmanlı koruma: çok virgül kendi iletisini verir", () => {
  // Arkadaki biçim denetimi de reddeder; bu sınama öndeki açıklayıcı katmanı ayrıca tutar.
  assert.equal(H.sayiOku("1,2,3", "gram").hata, "Birden fazla virgül var");
  assert.equal(H.sayiOku("12,3.4", "gram").hata, "Sayı anlaşılmadı");
  assert.equal(H.sayiOku("5e2", "gram").hata, "Yalnızca rakam, nokta ve virgül yazın");
  assert.equal(H.sayiOku("-5", "gram").hata, "Yalnızca rakam, nokta ve virgül yazın");
  assert.equal(H.sayiOku(",.", "gram").hata, "Rakam yok");
});

test("boş girdi 'boş' diye işaretlenir, hata sayılmaz", () => {
  for (const g of ["", "   ", null, undefined]) {
    const r = H.sayiOku(g, "gram");
    assert.equal(r.ok, false); assert.equal(r.bos, true);
  }
});

test("milyem: 585 yazılırsa 0,585 okunur ve uyarı döner", () => {
  const r = H.sayiOku("585", "milyem");
  assert.ok(r.ok); yakin(r.deger, 0.585); assert.match(r.uyari, /0,585/);
  yakin(H.sayiOku("0,333", "milyem").deger, 0.333);
  yakin(H.sayiOku("1", "milyem").deger, 1);
  assert.equal(H.sayiOku("0,333", "milyem").uyari, null);
  for (const k of ["0", "0,05", "1001", "1,5", "5000", "-0,5"]) assert.equal(H.sayiOku(k, "milyem").ok, false, k);
});

test("fiyat: binlik noktası doğru okunur, 100 TL altı reddedilir", () => {
  const iyi = { "6.511,34": 6511.34, "6511,34": 6511.34, "6511.34": 6511.34, "6.511": 6511, "4180": 4180, "10.000.000": 1e7 };
  for (const [g, v] of Object.entries(iyi)) { const r = H.sayiOku(g, "fiyat"); assert.ok(r.ok, g + " " + r.hata); yakin(r.deger, v); }
  for (const k of ["6,511", "99", "10.000.001", "6.51", "6.5110"]) assert.equal(H.sayiOku(k, "fiyat").ok, false, k);
});

// ---------------- Takas hesabı ----------------
const ORNEK_V = [{ ad: "Kelepçe", gram: "23,61", ayar: "8", milyem: "0,333" }];
const ORNEK_A = [{ ad: "Bilezik", gram: "8,62", ayar: "14", milyem: "0,585" }];

test("örnek takas: 23,61 g 8 ayar ↔ 8,62 g 14 ayar", () => {
  const s = H.hesapla(ORNEK_V, ORNEK_A);
  assert.ok(s.hazir);
  yakin(s.verilenHas, 23.61 * 0.333); yakin(s.alinanHas, 8.62 * 0.585);
  yakin(s.fark, 2.81943, 1e-9);
  assert.equal(s.yon, "kuyumcu");
  yakin(s.esdeger22, 2.81943 / 0.916, 1e-9); yakin(s.esdeger14, 2.81943 / 0.585, 1e-9);
  yakin(s.kuyumcuPayi, 0);
});

test("yön: siz ödersiniz / başa baş", () => {
  assert.equal(H.hesapla(ORNEK_A, ORNEK_V).yon, "siz");
  const e = H.hesapla([{ gram: "10", ayar: "14", milyem: "0,585" }], [{ gram: "10", ayar: "14", milyem: "0,585" }]);
  assert.equal(e.yon, "esit");
});

test("kuyumcu milyemi değişince pay doğru hesaplanır", () => {
  const s = H.hesapla([{ gram: "23,61", ayar: "8", milyem: "0,310" }], [{ gram: "8,62", ayar: "14", milyem: "0,620" }]);
  yakin(s.fark, 23.61 * 0.31 - 8.62 * 0.62);
  yakin(s.teorikFark, 23.61 * 0.333 - 8.62 * 0.585);
  yakin(s.kuyumcuPayi, s.teorikFark - s.fark);
});

test("KISMİ TOPLAM VERİLMEZ: bir parça hatalıysa sonuç yok", () => {
  const vakalar = [
    [[...ORNEK_V, { gram: "", ayar: "8", milyem: "0,333" }], ORNEK_A],
    [ORNEK_V, [...ORNEK_A, { gram: "abc", ayar: "14", milyem: "0,585" }]],
    [ORNEK_V, [{ gram: "8,62", ayar: "14", milyem: "" }]],
    [[], []],
    [null, undefined]
  ];
  for (const [v, a] of vakalar) {
    const s = H.hesapla(v, a);
    assert.equal(s.hazir, false);
    assert.equal(s.fark, undefined);
    assert.ok(s.sorunlar.length > 0);
  }
  const s = H.hesapla([...ORNEK_V, { gram: "", ayar: "8", milyem: "0,333" }], ORNEK_A);
  assert.deepEqual([s.sorunlar[0].taraf, s.sorunlar[0].sira, s.sorunlar[0].sorun[0].hata], ["verilen", 1, "Gram girin"]);
});

test("ayar: sözlük dışı ve prototip adları reddedilir", () => {
  for (const ayar of ["99", "__proto__", "constructor", "toString", "hasOwnProperty", "", null, undefined, 14.5]) {
    const r = H.parcaOku({ gram: "5", ayar, milyem: "0,5" });
    assert.equal(r.ok, false, String(ayar));
  }
  assert.ok(H.parcaOku({ gram: "5", ayar: 14, milyem: "0,5" }).ok, "sayı olarak 14 de kabul");
});

test("parça adı 60 karakterde kesilir, olduğu gibi metin kalır", () => {
  const r = H.parcaOku({ ad: "<img src=x onerror=alert(1)>" + "x".repeat(100), gram: "5", ayar: "14", milyem: "0,585" });
  assert.equal(r.ad.length, 60); assert.ok(r.ad.startsWith("<img"));
});

test("rastgele 5000 takas bağımsız hesapla aynı sonucu verir", () => {
  let tohum = 12345; const rnd = () => (tohum = (tohum * 1103515245 + 12345) % 2147483648) / 2147483648;
  const ayarlar = Object.keys(H.AYAR);
  for (let i = 0; i < 5000; i++) {
    const parca = () => { const g = Math.round((0.01 + rnd() * 500) * 100) / 100, m = Math.round((0.1 + rnd() * 0.9) * 1000) / 1000;
      return { gram: String(g).replace(".", rnd() < 0.5 ? "," : "."), ayar: ayarlar[Math.floor(rnd() * ayarlar.length)], milyem: String(m).replace(".", ","), g, m }; };
    const V = Array.from({ length: 1 + Math.floor(rnd() * 4) }, parca), A = Array.from({ length: Math.floor(rnd() * 4) }, parca);
    const s = H.hesapla(V, A);
    assert.ok(s.hazir, JSON.stringify(s.sorunlar));
    const beklenen = V.reduce((t, p) => t + p.g * p.m, 0) - A.reduce((t, p) => t + p.g * p.m, 0);
    yakin(s.fark, beklenen, 1e-7);
    assert.ok(Number.isFinite(s.esdeger22) && s.esdeger22 >= 0);
  }
});

// ---------------- Para ve piyasa ----------------
const FIYAT = { kaynak: "Test", has: { alis: 6500, satis: 6550 }, ayar14: { alis: 3680, satis: 4180 }, bilezik22: { alis: 5930, satis: 6390 } };

test("para karşılığı: kuyumcu öderse alış, siz öderseniz satış fiyatı", () => {
  const s = H.hesapla(ORNEK_V, ORNEK_A);
  const p = H.paraKarsiligi(s, FIYAT); yakin(p.tutar, s.mutlak * 6500); assert.equal(p.fiyatTuru, "alış");
  const s2 = H.hesapla(ORNEK_A, ORNEK_V);
  const p2 = H.paraKarsiligi(s2, FIYAT); yakin(p2.tutar, s2.mutlak * 6550); assert.equal(p2.fiyatTuru, "satış");
  assert.equal(H.paraKarsiligi(s, null), null);
  assert.equal(H.paraKarsiligi(H.hesapla([], []), FIYAT), null);
});

test("piyasa kıyası: 14 ayar kendi satış fiyatından, fiyatı olmayan ayar has × milyemden", () => {
  const s = H.hesapla(ORNEK_V, ORNEK_A);
  const pz = H.piyasa(s, FIYAT);
  yakin(pz.verilenTL, 23.61 * 0.333 * 6500); yakin(pz.alinanTL, 8.62 * 4180);
  const s18 = H.hesapla(ORNEK_V, [{ gram: "5", ayar: "18", milyem: "0,75" }]);
  yakin(H.piyasa(s18, FIYAT).alinanTL, 5 * 0.75 * 6550);
  assert.equal(H.piyasa(s, null), null);
});

// ---------------- Fiyat doğrulama (ağdan gelen veri) ----------------
const SIMDI = Date.parse("2026-09-29T09:00:00Z");
const iyiVeri = () => ({ kaynak: "Altınkaynak", zaman: "2026-09-29T11:55:00+03:00", has: { alis: 6509.47, satis: 6559.94 },
  ayar14: { alis: 3678.95, satis: 4180 }, ayar18: { alis: 4490, satis: 5250 }, bilezik22: { alis: 5936, satis: 6390 }, gram: { alis: 6476, satis: 6592 } });

test("fiyat: iyi veri kabul edilir, yaş hesaplanır", () => {
  const d = H.fiyatDogrula(iyiVeri(), SIMDI);
  assert.ok(d.ok, d.hata); yakin(d.yasDk, 5); assert.equal(d.eski, false); assert.deepEqual(d.uyarilar, []);
  assert.equal(d.fiyat.ayar14.satis, 4180);
});

test("fiyat: bozuk kökler reddedilir", () => {
  for (const v of [null, undefined, [], "str", 5, true, {}, { has: null }, { has: [] }, { has: "6500" }]) {
    assert.equal(H.fiyatDogrula(v, SIMDI).ok, false, JSON.stringify(v));
  }
});

test("fiyat: has alanındaki her bozukluk reddedilir", () => {
  const bozuklar = [
    { alis: "6500", satis: 6550 }, { alis: 6550, satis: 6500 }, { alis: 0, satis: 6550 }, { alis: -1, satis: 6550 },
    { alis: NaN, satis: 6550 }, { alis: 6500, satis: Infinity }, { alis: 6500, satis: 1e12 }, { alis: 6500, satis: 10000 },
    { alis: 50, satis: 60 }, { alis: 6500 }, { satis: 6500 }
  ];
  for (const has of bozuklar) {
    const v = iyiVeri(); v.has = has;
    assert.equal(H.fiyatDogrula(v, SIMDI).ok, false, JSON.stringify(has));
  }
});

test("fiyat: saat yok/bozuk/ilerideyse reddedilir, 5 dk ileri tolere edilir, eski işaretlenir", () => {
  for (const z of [undefined, "", "çöp", 12345, "2026-13-45"]) { const v = iyiVeri(); v.zaman = z; assert.equal(H.fiyatDogrula(v, SIMDI).ok, false, String(z)); }
  const ileri = iyiVeri(); ileri.zaman = "2026-09-29T13:00:00+03:00"; assert.equal(H.fiyatDogrula(ileri, SIMDI).ok, false);
  const az = iyiVeri(); az.zaman = "2026-09-29T12:05:00+03:00"; assert.ok(H.fiyatDogrula(az, SIMDI).ok);
  const eski = iyiVeri(); eski.zaman = "2026-09-29T09:00:00+03:00"; const d = H.fiyatDogrula(eski, SIMDI);
  assert.ok(d.ok); assert.equal(d.eski, true);
});

test("fiyat: bozuk ya da tutarsız yan kalem düşürülür, has kullanılmaya devam eder", () => {
  const v = iyiVeri(); v.ayar14 = { alis: "x", satis: 4180 }; v.bilezik22 = { alis: 6500, satis: 6560 * 3 };
  v.ayar18 = { alis: 6500, satis: 6559 }; // 18 ayar has fiyatına eşit: tutarsız değil (oran ≤1,05) — sınır içi
  v.gram = { alis: 100, satis: 120 };      // oran çok düşük: tutarsız
  const d = H.fiyatDogrula(v, SIMDI);
  assert.ok(d.ok);
  assert.equal(d.fiyat.ayar14, undefined); assert.equal(d.fiyat.bilezik22, undefined); assert.equal(d.fiyat.gram, undefined);
  assert.equal(d.uyarilar.length, 3);
  const v2 = iyiVeri(); v2.ayar14 = { alis: 6500, satis: 6559 }; // 14 ayar has fiyatına satılamaz
  assert.equal(H.fiyatDogrula(v2, SIMDI).fiyat.ayar14, undefined);
});

test("fiyat: __proto__ ile gelen has kabul edilmez", () => {
  const v = JSON.parse('{"__proto__":{"has":{"alis":6500,"satis":6550}},"zaman":"2026-09-29T11:55:00+03:00"}');
  assert.equal(H.fiyatDogrula(v, SIMDI).ok, false);
  assert.equal({}.has, undefined, "Object.prototype kirlenmedi");
});

test("fiyat: sayfadaki başka bir betik Object.prototype'u kirletse bile sahte has okunmaz", () => {
  Object.prototype.has = { alis: 1000, satis: 1010 };
  try { assert.equal(H.fiyatDogrula({ zaman: "2026-09-29T11:55:00+03:00" }, SIMDI).ok, false); }
  finally { delete Object.prototype.has; }
});

test("fiyat: kaynak adı metin değilse ya da uzunsa temizlenir", () => {
  const v = iyiVeri(); v.kaynak = { x: 1 }; assert.equal(H.fiyatDogrula(v, SIMDI).fiyat.kaynak, "Bilinmeyen kaynak");
  v.kaynak = "A".repeat(500); assert.equal(H.fiyatDogrula(v, SIMDI).fiyat.kaynak.length, 40);
});

// ---------------- Özet ve yardımcılar ----------------
test("özet: temel satırları içerir, hazır değilse boş", () => {
  const s = H.hesapla(ORNEK_V, ORNEK_A);
  const o = H.ozetMetni(s, FIYAT, "Altınkaynak 29.09 11:42");
  assert.match(o, /Kuyumcu bize borçlu: 2,819 g has/);
  assert.match(o, /Kelepçe: 23,61 g, 8 ayar/);
  assert.match(o, /Piyasa kıyası \(Altınkaynak 29\.09 11:42\)/);
  assert.equal(H.ozetMetni(H.hesapla([], []), FIYAT), "");
  assert.doesNotMatch(H.ozetMetni(s, null), /Piyasa/);
  assert.match(H.ozetMetni(H.hesapla(ORNEK_A, ORNEK_V), null), /Biz kuyumcuya öderiz/);
});

test("yaş metni", () => {
  assert.equal(H.yasMetni(0.5), "az önce"); assert.equal(H.yasMetni(12.9), "12 dk önce");
  assert.equal(H.yasMetni(125), "2 saat önce"); assert.equal(H.yasMetni(3 * 1440), "3 gün önce"); assert.equal(H.yasMetni(NaN), "");
});

test("biçim: sonsuz/NaN asla ekrana sayı diye çıkmaz", () => {
  assert.equal(H.fmt(NaN), "–"); assert.equal(H.fmt(Infinity), "–"); assert.equal(H.fmt(2.81943), "2,819"); assert.equal(H.tl(18357.6), "18.358 TL");
});
