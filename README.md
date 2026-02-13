# 🎓 İTÜ Ninova Senkronizasyon Aracı

Bu Python aracı, İstanbul Teknik Üniversitesi (İTÜ) Ninova Eğitim Sistemindeki ders içeriklerini otomatik olarak bilgisayarınıza indirir ve senkronize eder.

## ✨ Özellikler

* Akıllı Senkronizasyon: Sadece yeni eklenen veya sunucuda boyutu değişen dosyaları indirir.
* Gelişmiş Arşivleme:     * Sunucuda güncellenen dosyaların eski hallerini _ARSIV/Changed klasörüne taşır.
    * Ninova'dan silinen dosyaları yerelinizden kaldırmaz, _ARSIV/Deleted klasörüne yedekler.
* Otomatik Kimlik Yönetimi: İlk çalıştırmada bilgilerinizi ister ve credentials.json olarak güvenli bir şekilde kaydeder.
* Hiyerarşik Düzen: Dosyaları Ders Adı/DersDosyalari ve Ders Adı/SinifDosyalari şeklinde organize eder.
* Renkli Özet Rapor: İşlem bittiğinde terminal üzerinden yeni, değişen ve silinen dosyaların profesyonel bir raporunu sunar.

## 🛠️ Gereksinimler

Programın çalışması için bilgisayarınızda Python 3.x ve Google Chrome yüklü olmalıdır.

Gerekli kütüphaneleri requirements.txt dosyası yardımıyla toplu olarak yüklemek için:

pip install -r requirements.txt 

## 🚀 Kurulum ve Kullanım

1. Script'i İndirin: ninova_sync.py dosyasını bir klasöre koyun.
2. Programı Çalıştırın: Terminal veya Komut İstemi açıp şu komutu girin:
  python ninova_sync.py    
3. Giriş Yapın: İlk çalıştırmada İTÜ kullanıcı adınızı ve şifrenizi girmeniz istenecektir. Şifreniz yazarken ekranda görünmez (güvenlik önlemi).

## 📂 Klasör Yapısı

Program çalıştığında aşağıdaki yapıyı otomatik olarak yönetir:

* ITU_Dersleri/: Tüm ders içeriklerinin ana dizini.
* ITU_Dersleri/[Ders Adı]/: Her ders için ayrılmış alt klasörler.
* ITU_Dersleri/_ARSIV/:
    * /Changed/: İçeriği güncellenen eski dosyalar.
    * /Deleted/: Ninova sisteminden kaldırılmış dosyalar.

## ⚠️ Önemli Notlar

* Güvenlik: credentials.json dosyanız şifrenizi açık metin olarak saklar. Bu dosyayı başkalarıyla paylaşmayın ve GitHub gibi platformlara yüklerken .gitignore listesine ekleyin.
* Tarayıcı: Araç, Chrome tarayıcısını kullanarak Ninova'ya giriş yapar. İşlem sırasında Chrome pencereleri açılabilir.
* Hata Giderme: Eğer giriş hatası alırsanız veya bilgileriniz değişirse, credentials.json dosyasını silip programı yeniden başlatmanız yeterlidir.

## 📊 Sonuç Raporu Örneği

Senkronizasyon bittiğinde terminalde şu şekilde bir görsel rapor oluşur:

████████████████████  SONUÇ RAPORU  ████████████████████  
[+] YENİ EKLENEN DOSYALAR (2):   📂 MAT103E - Calculus I/DersDosyalari/Lecture_Notes_01.pdf  
[!] DEĞİŞEN DOSYALAR (1):   📝 FIZ101E - Physics I/SinifDosyalari/Experiment_Guide.pdf  
[-] SİLİNEN DOSYALAR (1):   🗑️ Old_Syllabus_2023.pdf  İşlem Tamamlandı.  

---
Bu araç tamamen eğitim amaçlı geliştirilmiştir. İTÜ Ninova sisteminin kullanım koşullarına uygun şekilde kullanılması kullanıcının sorumluluğundadır.