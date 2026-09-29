# Altın Takas Hesabı

Kuyumcuda eski altını yenisiyle değiştirirken iki altını da saf altına (has)
çevirip farkı gösterir. Farkın TL karşılığını ve Altınkaynak fiyatlarına göre
piyasa kıyasını verir. Özet WhatsApp'a tek dokunuşla gönderilir.

**Adres:** https://ayavuzyen.github.io/kuyumcu-hesap/

## Telefona uygulama olarak ekleme

- **Android (Chrome):** adresi aç → sağ üstteki ⋮ → *Ana ekrana ekle* / *Uygulamayı yükle*.
- **iPhone (Safari):** adresi aç → Paylaş düğmesi → *Ana Ekrana Ekle*.
  WhatsApp içinde açılırsa önce sağ üstten *Safari'de aç* deyin.

Bir kez açıldıktan sonra internet yokken de hesap çalışır. Fiyat için internet gerekir,
yoksa cihazda kayıtlı son fiyat saatiyle birlikte gösterilir.

## Fiyat nasıl güncelleniyor

Altınkaynak'ın fiyat servisi tarayıcıya başka bir siteden veri vermiyor. Bu yüzden
sayfa fiyatı doğrudan çekemez. Araya GitHub'ın zamanlanmış işi (`.github/workflows/fiyat.yml`)
girer:

1. İş 5 dakikada bir `araclar/fiyat_cek.py` betiğini çalıştırır.
2. Betik cevabı denetler: biçim, alış ≤ satış, ayar fiyatlarının has fiyatıyla tutarlılığı
   ve saat. Denetimden geçmeyen fiyat **yayımlanmaz**; eski ama doğru fiyat yerinde kalır.
3. Geçen fiyat `veri` dalındaki `fiyatlar.json` dosyasına yazılır.
   Sayfa bu dosyayı `raw.githubusercontent.com` üzerinden okur.

Sayfa her fiyatın saatini gösterir. 60 dakikadan eski fiyatta "Eski fiyat" uyarısı çıkar
(hafta sonu ya da bayramda piyasa kapalıyken olağandır).

**Bilinen sınırlar**
- GitHub yoğunlukta zamanlanmış işleri birkaç dakika geciktirebilir.
- Depoda 60 gün boyunca hiç değişiklik olmazsa GitHub zamanlanmış işi durdurabilir. Fiyat
  eskimeye başlarsa depo sayfasında **Actions → Fiyat güncelle → Enable workflow** deyin.
- Fiyat Altınkaynak'ın herkese açık listesidir. Kuyumcunun kendi fiyatı farklı olabilir;
  kutulara elle yazılan fiyat hesabı hemen değiştirir.

## Hesap kuralları

- Parçalardan biri eksik ya da hatalıysa **toplam gösterilmez**; hangi kutunun hatalı
  olduğu yazılır. Eksik bir toplam tam sanılabilir.
- `23,61` ve `23.61` aynı okunur. Fiyatta `6.511` binlik ayırıcı sayılır (6511 TL).
- Milyem kutusuna `585` yazılırsa `0,585` okunur ve bu ekranda söylenir.
- Farkın TL karşılığı, kuyumcu size ödüyorsa has **alış**, siz ödüyorsanız has **satış**
  fiyatıyla hesaplanır.

## Sınama

```
python test/hepsi.py
```

Sırasıyla: hesap çekirdeği sınamaları (Node), fiyat çekicinin düşman ağ sınamaları (yerel
sahte sunucu, gerçek siteye istek atılmaz), mutasyon sınaması (her koruma kopyada bozulur,
bir sınamanın kırılması beklenir) ve teslim paketi denetimi. Gereken: Python 3.10+, Node 18+.
