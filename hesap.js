/* Altın Takas Hesabı — hesap çekirdeği.
 * Arayüzden bağımsız, saf fonksiyonlar. Tarayıcıda window.Hesap, Node'da module.exports.
 * Buradaki her koruma test/hesap.test.js içinde bir sınamayla karşılanır; koruma
 * kaldırılırsa test/mutasyon.js o sınamanın kırıldığını doğrular.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Hesap = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // Sürüm tek kaynaktan: sayfa altı ve servis çalışanının önbellek adı bunu okur.
  const SURUM = "1.0.0";

  // Türkiye'de kullanılan standart milyemler.
  const AYAR = Object.freeze({ "8": 0.333, "10": 0.416, "14": 0.585, "18": 0.75, "22": 0.916, "24": 0.995 });

  const SINIR = Object.freeze({
    gramMax: 2000,          // tek parça için; daha büyüğü yazım hatasıdır
    milyemMin: 0.1,
    milyemMax: 1,
    fiyatMin: 100,          // TL/g; altında bir has fiyatı yazım hatasıdır ("6.511" → 6,5 TL gibi)
    fiyatMax: 10000000,
    eskiDk: 60,             // bu yaştan eski fiyat "eski" diye işaretlenir
    gelecekTolDk: 10,       // kaynak saati bundan fazla ilerideyse fiyat reddedilir
    esitlikEsigi: 0.0005    // g has; bunun altı "eşit" sayılır
  });

  // ---------- Sayı okuma ----------
  // Türkçe klavyede virgül ondalıktır, telefon klavyesinde çoğu kişi nokta yazar.
  // İkisi de kabul edilir; iki türlü okunabilen durumlar türe göre çözülür ve uyarı döner.
  // Yalnız baş/son boşluk atılır. İçerideki boşluk silinmez: "2 3" sessizce 23 olmasın.
  function temizle(s) {
    if (s === null || s === undefined) return "";
    return String(s).normalize("NFKC").trim();
  }

  function sayiOku(girdi, tur) {
    const s = temizle(girdi);
    if (s === "") return { ok: false, bos: true, hata: "Boş" };
    if (s.length > 20) return { ok: false, hata: "Çok uzun" };
    if (!/^[0-9.,]+$/.test(s)) return { ok: false, hata: "Yalnızca rakam, nokta ve virgül yazın" };
    if (!/[0-9]/.test(s)) return { ok: false, hata: "Rakam yok" };

    let norm, uyari = null;
    const virgul = (s.match(/,/g) || []).length;
    if (virgul > 1) return { ok: false, hata: "Birden fazla virgül var" };
    if (virgul === 1) {
      // Virgül ondalık; varsa noktalar binlik ayırıcı olmalı.
      if (!/^(\d{1,3}(\.\d{3})+|\d+)?,\d*$/.test(s)) return { ok: false, hata: "Sayı anlaşılmadı" };
      norm = s.replace(/\./g, "").replace(",", ".");
    } else {
      const nokta = (s.match(/\./g) || []).length;
      if (tur === "fiyat" && /^\d{1,3}(\.\d{3})+$/.test(s)) {
        norm = s.replace(/\./g, "");      // 6.511 → 6511 TL
      } else if (nokta > 1) {
        return { ok: false, hata: "Sayı anlaşılmadı" };
      } else {
        norm = s;                          // 23.61 → 23,61 g
      }
    }
    if (norm.endsWith(".")) norm = norm.slice(0, -1);   // yazarken "23," ara hali
    if (norm.startsWith(".")) norm = "0" + norm;
    if (!/^\d+(\.\d+)?$/.test(norm)) return { ok: false, hata: "Sayı anlaşılmadı" };
    let v = Number(norm);
    if (!Number.isFinite(v)) return { ok: false, hata: "Sayı anlaşılmadı" };

    if (tur === "gram") {
      if (!(v > 0)) return { ok: false, hata: "Gram 0'dan büyük olmalı" };
      if (v > SINIR.gramMax) return { ok: false, hata: `Gram en çok ${SINIR.gramMax} olabilir` };
    } else if (tur === "milyem") {
      if (v > 1 && v <= 1000) { uyari = `${s} yerine ${fmt(v / 1000)} okundu`; v = v / 1000; }
      if (!(v >= SINIR.milyemMin && v <= SINIR.milyemMax)) return { ok: false, hata: "Milyem 0,100 ile 1,000 arasında olmalı" };
    } else if (tur === "fiyat") {
      if (!(v >= SINIR.fiyatMin && v <= SINIR.fiyatMax)) return { ok: false, hata: `Fiyat ${fmt(SINIR.fiyatMin, 0)} TL ile ${fmt(SINIR.fiyatMax, 0)} TL arasında olmalı` };
    }
    return { ok: true, deger: v, uyari };
  }

  // ---------- Biçimlendirme ----------
  function fmt(n, basamak) {
    const d = basamak === undefined ? 3 : basamak;
    if (!Number.isFinite(n)) return "–";
    return n.toLocaleString("tr-TR", { minimumFractionDigits: d, maximumFractionDigits: d });
  }
  const tl = (n) => fmt(n, 0) + " TL";

  // ---------- Takas hesabı ----------
  // parca: { ad, gram, ayar, milyem }  (gram ve milyem ham metin ya da sayı olabilir)
  function parcaOku(p) {
    const g = sayiOku(p.gram, "gram");
    const m = sayiOku(p.milyem, "milyem");
    const ayarOk = Object.prototype.hasOwnProperty.call(AYAR, String(p.ayar));
    const sorun = [];
    if (!g.ok) sorun.push({ alan: "gram", hata: g.bos ? "Gram girin" : g.hata });
    if (!m.ok) sorun.push({ alan: "milyem", hata: m.bos ? "Milyem girin" : m.hata });
    if (!ayarOk) sorun.push({ alan: "ayar", hata: "Ayar seçin" });
    if (sorun.length) return { ok: false, sorun };
    const ayarMilyem = AYAR[String(p.ayar)];
    return {
      ok: true, ad: String(p.ad || "Parça").slice(0, 60), ayar: String(p.ayar),
      gram: g.deger, milyem: m.deger, has: g.deger * m.deger, teorikHas: g.deger * ayarMilyem,
      uyari: m.uyari
    };
  }

  // Parçalardan biri okunamıyorsa toplam VERİLMEZ: eksik toplam tam sanılır.
  function hesapla(verilen, alinan) {
    const V = (verilen || []).map(parcaOku), A = (alinan || []).map(parcaOku);
    const sorunlar = [];
    V.forEach((r, i) => { if (!r.ok) sorunlar.push({ taraf: "verilen", sira: i, sorun: r.sorun }); });
    A.forEach((r, i) => { if (!r.ok) sorunlar.push({ taraf: "alinan", sira: i, sorun: r.sorun }); });
    if (V.length === 0 && A.length === 0) sorunlar.push({ taraf: "genel", sira: -1, sorun: [{ alan: "", hata: "En az bir parça ekleyin" }] });
    if (sorunlar.length) return { hazir: false, sorunlar, verilen: V, alinan: A };

    const topla = (arr, k) => arr.reduce((t, r) => t + r[k], 0);
    const vHas = topla(V, "has"), aHas = topla(A, "has");
    const vTeo = topla(V, "teorikHas"), aTeo = topla(A, "teorikHas");
    const fark = vHas - aHas, teorikFark = vTeo - aTeo;
    const yon = Math.abs(fark) < SINIR.esitlikEsigi ? "esit" : fark > 0 ? "kuyumcu" : "siz";
    return {
      hazir: true, verilen: V, alinan: A,
      verilenHas: vHas, alinanHas: aHas, fark, mutlak: Math.abs(fark), yon,
      esdeger22: Math.abs(fark) / AYAR["22"], esdeger14: Math.abs(fark) / AYAR["14"],
      teorikFark, kuyumcuPayi: teorikFark - fark
    };
  }

  // Farkın TL karşılığı: kuyumcu size ödüyorsa sizden has ALIYOR (alış fiyatı),
  // siz ödüyorsanız size has SATIYOR (satış fiyatı).
  function paraKarsiligi(sonuc, fiyat) {
    if (!sonuc || !sonuc.hazir || !fiyat || !fiyat.has) return null;
    const birim = sonuc.yon === "siz" ? fiyat.has.satis : fiyat.has.alis;
    if (!Number.isFinite(birim)) return null;
    return { tutar: sonuc.mutlak * birim, birim, fiyatTuru: sonuc.yon === "siz" ? "satış" : "alış" };
  }

  // Piyasa kıyası: verilen altın tam milyemle has alış fiyatından, alınan altın
  // kaynağın o ayar için yayımladığı satış fiyatından (yoksa has satış × milyem).
  function piyasa(sonuc, fiyat) {
    if (!sonuc || !sonuc.hazir || !fiyat || !fiyat.has) return null;
    const satisFiyati = { "14": fiyat.ayar14, "18": fiyat.ayar18, "22": fiyat.bilezik22, "24": fiyat.gram };
    let verilenTL = 0, alinanTL = 0;
    sonuc.verilen.forEach((r) => { verilenTL += r.teorikHas * fiyat.has.alis; });
    sonuc.alinan.forEach((r) => {
      const f = satisFiyati[r.ayar];
      alinanTL += f && Number.isFinite(f.satis) ? r.gram * f.satis : r.teorikHas * fiyat.has.satis;
    });
    const fark = verilenTL - alinanTL;
    return { verilenTL, alinanTL, fark, yon: fark >= 0 ? "kuyumcu" : "siz" };
  }

  // ---------- Fiyat verisi doğrulama ----------
  // Ağdan gelen veri güvenilmezdir: biçim, aralık ve tutarlılık denetlenir.
  // Zorunlu olan yalnız "has"; diğer kalemler bozuksa düşürülür ve uyarı döner.
  const ETIKET = { has: "Has", ayar14: "14 ayar", ayar18: "18 ayar", bilezik22: "22 ayar bilezik", gram: "Gram altın" };
  function ciftOku(o, ad, zorunlu, uyarilar) {
    const c = o && Object.prototype.hasOwnProperty.call(o, ad) ? o[ad] : undefined;
    if (c === undefined) { if (zorunlu) return { hata: `${ETIKET[ad] || ad} fiyatı yok` }; return {}; }
    const iyi = c && typeof c === "object" && !Array.isArray(c) &&
      Number.isFinite(c.alis) && Number.isFinite(c.satis) &&
      c.alis >= SINIR.fiyatMin && c.satis <= SINIR.fiyatMax &&
      c.satis >= c.alis && c.satis / c.alis < 1.5;
    if (!iyi) {
      if (zorunlu) return { hata: `${ETIKET[ad] || ad} fiyatı geçersiz` };
      uyarilar.push(`${ETIKET[ad] || ad} fiyatı geçersiz, kullanılmadı`);
      return {};
    }
    return { deger: { alis: c.alis, satis: c.satis } };
  }

  function fiyatDogrula(veri, simdiMs) {
    const simdi = Number.isFinite(simdiMs) ? simdiMs : Date.now();
    if (!veri || typeof veri !== "object" || Array.isArray(veri)) return { ok: false, hata: "fiyat verisi okunamadı" };
    const uyarilar = [];
    const has = ciftOku(veri, "has", true, uyarilar);
    if (has.hata) return { ok: false, hata: has.hata };
    const fiyat = { kaynak: typeof veri.kaynak === "string" ? veri.kaynak.slice(0, 40) : "Bilinmeyen kaynak", has: has.deger };

    // Ayar fiyatları has fiyatına göre makul aralıkta olmalı; değilse kullanılmaz.
    const oran = { ayar14: [0.45, 0.95], ayar18: [0.6, 1.05], bilezik22: [0.8, 1.15], gram: [0.9, 1.2] };
    Object.keys(oran).forEach((k) => {
      const c = ciftOku(veri, k, false, uyarilar);
      if (!c.deger) return;
      const r = c.deger.satis / has.deger.satis;
      if (r < oran[k][0] || r > oran[k][1]) { uyarilar.push(`${ETIKET[k]} fiyatı has fiyatıyla tutarsız, kullanılmadı`); return; }
      fiyat[k] = c.deger;
    });

    const zamanMs = typeof veri.zaman === "string" ? Date.parse(veri.zaman) : NaN;
    if (!Number.isFinite(zamanMs)) return { ok: false, hata: "fiyat saati okunamadı" };
    if (zamanMs - simdi > SINIR.gelecekTolDk * 60000) return { ok: false, hata: "fiyat saati ileri bir tarihte" };
    fiyat.zamanMs = zamanMs;
    const yasDk = Math.max(0, (simdi - zamanMs) / 60000);
    return { ok: true, fiyat, yasDk, eski: yasDk > SINIR.eskiDk, uyarilar };
  }

  function yasMetni(dk) {
    if (!Number.isFinite(dk)) return "";
    if (dk < 1) return "az önce";
    if (dk < 60) return `${Math.floor(dk)} dk önce`;
    if (dk < 48 * 60) return `${Math.floor(dk / 60)} saat önce`;
    return `${Math.floor(dk / 1440)} gün önce`;
  }

  // ---------- WhatsApp özeti ----------
  function ozetMetni(sonuc, fiyat, fiyatBilgi) {
    if (!sonuc || !sonuc.hazir) return "";
    const satir = (r) => `• ${r.ad}: ${fmt(r.gram, 2)} g, ${r.ayar} ayar, milyem ${fmt(r.milyem)} → ${fmt(r.has)} g has`;
    const out = ["ALTIN TAKAS HESABI"];
    if (sonuc.verilen.length) out.push("Verilen:", ...sonuc.verilen.map(satir));
    if (sonuc.alinan.length) out.push("Alınan:", ...sonuc.alinan.map(satir));
    out.push("");
    const para = paraKarsiligi(sonuc, fiyat);
    if (sonuc.yon === "esit") out.push("Takas başa baş, kimse kimseye borçlu değil.");
    else {
      out.push((sonuc.yon === "kuyumcu" ? "Kuyumcu bize borçlu: " : "Biz kuyumcuya öderiz: ") + fmt(sonuc.mutlak) + " g has");
      out.push(`= ${fmt(sonuc.esdeger22, 2)} g 22 ayar = ${fmt(sonuc.esdeger14, 2)} g 14 ayar` + (para ? ` ≈ ${tl(para.tutar)}` : ""));
    }
    out.push(`(Tam milyemle fark ${fmt(sonuc.teorikFark)} g has olurdu; kuyumcu payı ${fmt(sonuc.kuyumcuPayi)} g)`);
    const pz = piyasa(sonuc, fiyat);
    if (pz) {
      out.push("", `Piyasa kıyası${fiyatBilgi ? " (" + fiyatBilgi + ")" : ""}: verilen ${tl(pz.verilenTL)}, alınan ${tl(pz.alinanTL)}, fark ${tl(Math.abs(pz.fark))}`);
      out.push(`Has alış ${fmt(fiyat.has.alis, 2)} / satış ${fmt(fiyat.has.satis, 2)} TL` + (fiyat.ayar14 ? `, 14 ayar satış ${fmt(fiyat.ayar14.satis, 2)} TL` : ""));
    }
    return out.join("\n");
  }

  return { SURUM, AYAR, SINIR, sayiOku, fmt, tl, parcaOku, hesapla, paraKarsiligi, piyasa, fiyatDogrula, yasMetni, ozetMetni };
});
