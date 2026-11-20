# 🎓 İTÜ Ninova Senkronizasyon Aracı

Bu Python aracı, İstanbul Teknik Üniversitesi (İTÜ) Ninova Eğitim Sistemindeki ders içeriklerini, ödev dosyalarını ve duyurularını otomatik olarak bilgisayarınıza indirir ve senkronize eder.

## ✨ Özellikler

- **Etkileşimli CLI (`cli.py`):** Otomatik taranan dersler arasından numara seçimi (`1, 3`) veya `hepsi` komutuyla istenen dersleri senkronize etme imkanı sunar.
- **Etkileşimli Hesap ve Şifre Yönetimi:** Terminal üzerinden şifre güncelleme (`sifre`), kayıtlı hesabı silme (`hesap-sil`), aktif kullanıcıyı görüntüleme (`hesap`) ve `--hesap-sifirla` başlangıç bayrağı sunar.
- **Hatalı Giriş Kurtarma:** Şifre veya kullanıcı adı yanlış girildiğinde programı kapatmadan doğrudan terminal üzerinden şifre yenileme veya hesabı sıfırlayıp yeniden deneme seçeneği sunar.
- **Akıllı Senkronizasyon ve Web Link Desteği:** Dosyalarda tarih/metadata kontrolü, duyurularda SHA-256 içerik hash karşılaştırması yapar; HTML/web bağlantılarını `.url` kısayolu olarak kaydeder.
- **Duyuru ve Ödev Taraması:** Duyuruları `.txt` dosyaları halinde kaydeder (aynı başlıktaki duyuruları numaralandırır) ve ödev eklerini ödev başlığına göre klasörler.
- **Gelişmiş Arşivleme:**
  - Sunucuda güncellenen dosya, link veya duyuruların eski hallerini `ITU_Dersleri/_ARSIV/Changed` klasörüne taşır.
  - Ninova'dan kaldırılan öğeleri yerelinizden silmez, `ITU_Dersleri/_ARSIV/Deleted` klasörüne yedekler.
- **Güvenli Kimlik Yönetimi (`keyring`):** Kullanıcı adını `config.json` dosyasına kaydeder, şifreyi ise işletim sisteminin güvenli kasasına (`keyring`) saklar.
- **Hiyerarşik ve Renkli Terminal Çıktısı:** Dersleri ve alt modülleri (`DersDosyalari`, `SinifDosyalari`, `Odevler`, `Duyurular`) ağaç yapısında ve farklı renk hiyerarşisiyle gösterir.
- **Kapsamlı Özet Rapor:** İşlem sonunda kontrol edilen dersleri ve yeni, değişen, silinen ya da hatalı öğeleri raporlar.

## 🛠️ Gereksinimler

Programın çalışması için bilgisayarınızda **Python 3.x** ve **Google Chrome** yüklü olmalıdır.

Gerekli kütüphaneleri `requirements.txt` dosyası yardımıyla toplu olarak yüklemek için:

```bash
pip install -r requirements.txt
```

## 🚀 Kurulum ve Kullanım

1. **Dosyaları Hazırlayın:** `ninova_sync.py` ve `cli.py` dosyalarını aynı klasöre koyun.
2. **Etkileşimli CLI'ı Başlatın:** Terminal açıp şu komutu çalıştırın:
   ```bash
   python cli.py
   ```
   **İsteğe Bağlı Başlangıç Bayrakları:**
   - `python cli.py --headless`: Tarayıcı penceresini gizli (arka planda) çalıştırır.
   - `python cli.py --hesap-sifirla`: Kayıtlı `keyring` şifresini ve `config.json` dosyasını silip yeniden giriş ister.
3. **Giriş Yapın:** İlk çalıştırmada İTÜ kullanıcı adınızı ve şifrenizi girmeniz istenecektir. Şifreniz `getpass` ile gizli alınır ve sistem `keyring` kasasına kaydedilir.
4. **Komutları Kullanın (`ninova >`):**
   - `1, 3` veya `1 3`: Seçilen numaradaki dersleri senkronize eder.
   - `hepsi` (`a`, `*`): Tüm dersleri senkronize eder.
   - `liste`: Ders listesini tekrar gösterir.
   - `hesap`: Aktif kullanıcı bilgilerini gösterir.
   - `sifre`: Keyring'deki şifreyi günceller ve oturumu yeniden başlatır.
   - `hesap-sil`: Keyring şifresini ve `config.json` dosyasını siler.
   - `q` (`cikis`): Tarayıcıyı kapatır ve özet raporu gösterir.

## 📂 Klasör ve Takip Yapısı

Program çalıştığında aşağıdaki yapıyı otomatik olarak yönetir:

- `ITU_Dersleri/`: Tüm ders içeriklerinin ana dizini.
- `ITU_Dersleri/[Ders Kodu]/`: `DersDosyalari`, `SinifDosyalari`, `Odevler` ve `Duyurular` alt klasörleri.
- `ITU_Dersleri/_ARSIV/`:
  - `Changed/`: İçeriği veya tarihi güncellenen eski dosyalar ve duyurular.
  - `Deleted/`: Ninova sisteminden kaldırılmış dosyalar ve duyurular.
- `dosya_takip.json`: Dosya tarihlerini ve duyuru içerik hash'lerini tutan takip dosyası.
- `config.json`: Kayıtlı kullanıcı adını tutan yapılandırma dosyası.

## ⚠️ Önemli Notlar

- **Güvenlik:** Şifreler `config.json` yerine işletim sisteminin `keyring` kasasında tutulur; yine de yerel çalışma dizininizi paylaşırken `config.json`, `dosya_takip.json` ve `ITU_Dersleri/` klasörünü `.gitignore` listesine eklemeniz önerilir.
- **Tarayıcı:** Araç, Selenium üzerinden Chrome tarayıcısını kullanarak Ninova'ya oturum açar ve çerezleri `requests.Session` ile paylaşarak dosya indirmelerini hızlandırır.
- **Hata Giderme:** Şifrenizi değiştirdiyseniz veya yanlış girdiyseniz giriş sırasındaki kurtarma menüsünden, CLI içindeki `sifre` / `hesap-sil` komutlarından ya da `python cli.py --hesap-sifirla` bayrağından yararlanabilirsiniz.

## 📊 Sonuç Raporu Örneği

Senkronizasyon bittiğinde terminalde şu şekilde bir özet rapor oluşur:

```text
████████████████████  SONUÇ RAPORU  ████████████████████

[i] KONTROL EDİLEN DERSLER (2):
  📘 BLG 231E
  📘 EKO 201E

[+] YENİ EKLENEN DOSYALAR / LİNKLER (2):
  📂 BLG 231E/DersDosyalari/Hafta_01/Logic_Gates.pdf
  🌐 EKO 201E/DersDosyalari/Reading_Link.url

[!] TARİHİ / İÇERİĞİ DEĞİŞEN DOSYALAR (1):
  📝 BLG 231E/Duyurular/Sinav_Tarihi.txt

[-] SİLİNEN DOSYALAR / LİNKLER (1):
  🗑️  EKO 201E/SinifDosyalari/Eski_Not.pdf

İşlem Tamamlandı.
```

---
Bu araç eğitim ve kişisel organizasyon amacıyla geliştirilmiştir. İTÜ Ninova sisteminin kullanım koşullarına uygun şekilde kullanılması kullanıcının sorumluluğundadır.