import os
import sys
import time
import json
import requests
import re
import shutil
from getpass import getpass
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# --- RENK KODLARI (ANSI) ---
class Renk:
    MOR = '\033[95m'
    MAVI = '\033[94m'
    YESIL = '\033[92m'
    SARI = '\033[93m'
    KIRMIZI = '\033[91m'
    GRI = '\033[90m'
    KALIN = '\033[1m'
    RESET = '\033[0m'

# Windows terminalinde renkleri aktif etmek için
os.system("")

# --- AYARLAR ---
ANA_KLASOR = "ITU_Dersleri"
ARSIV_KLASOR = os.path.join(ANA_KLASOR, "_ARSIV")
URL = "https://ninova.itu.edu.tr/tr/"
isHeadless = True

# --- ÖZET RAPOR LİSTELERİ ---
ozet = {
    "yeni": [],
    "degisen": [],
    "silinen": [],
    "hata": []
}

# --- 1. KİMLİK BİLGİLERİNİ OKU VEYA OLUŞTUR ---
credentials_file = "credentials.json"

if not os.path.exists(credentials_file):
    print(f"{Renk.SARI}--------------------------------------------------{Renk.RESET}")
    print(f"{Renk.KALIN}🚀 Sisteme ilk defa giriş yapıyorsunuz.{Renk.RESET}")
    print(f"Lütfen Ninova (İTÜ) kullanıcı bilgilerinizi giriniz.")
    print(f"Bu bilgiler sadece bilgisayarınızdaki {Renk.MAVI}'credentials.json'{Renk.RESET} dosyasına kaydedilecektir.")
    print(f"{Renk.SARI}--------------------------------------------------{Renk.RESET}")
    
    # Input kısmını renklendirelim
    new_username = input(f"{Renk.MAVI}{Renk.KALIN}👉 Kullanıcı Adı: {Renk.RESET}")
    
    print(f"\n{Renk.GRI}[BİLGİ] Şifrenizi yazarken karakterler güvenlik nedeniyle ekranda GÖZÜKMEYECEKTİR.{Renk.RESET}")
    print(f"{Renk.GRI}Yazmaya devam edin ve bitince Enter'a basın.{Renk.RESET}")
    
    # getpass kısmını renklendirelim
    new_password = getpass(f"{Renk.MAVI}{Renk.KALIN}👉 Şifre: {Renk.RESET}")
    
    # Bilgileri sözlük yapısına al
    creds_data = {
        "username": new_username,
        "password": new_password
    }
    
    # Dosyayı oluştur ve kaydet
    with open(credentials_file, "w", encoding="utf-8") as f:
        json.dump(creds_data, f, indent=4, ensure_ascii=False)
    
    print(f"\n{Renk.YESIL}✅ Bilgiler başarıyla '{credentials_file}' dosyasına kaydedildi.{Renk.RESET}\n")

# Dosya zaten varsa veya az önce oluşturulduysa buradan devam eder
try:
    with open(credentials_file, "r", encoding="utf-8") as f:
        creds = json.load(f)
    my_username = creds["username"]
    my_password = creds["password"]
    print(f"{Renk.YESIL}Bilgiler yüklendi: {Renk.KALIN}{my_username}{Renk.RESET}")
except Exception as e:
    print(f"{Renk.KIRMIZI}HATA: Dosya okunurken bir sorun oluştu: {e}{Renk.RESET}")
    sys.exit(1)

# --- YARDIMCI FONKSİYONLAR ---

def temizle_dosya_ismi(isim):
    if not isim: return "isimsiz_dosya"
    yasakli = r'[\\/*?:"<>|]'
    temiz = re.sub(yasakli, '', isim)
    return temiz.strip()

def arsivle(local_path, neden):
    try:
        filename = os.path.basename(local_path)
        name, ext = os.path.splitext(filename)
        zaman = datetime.now().strftime("%Y%m%d_%H%M%S")
        yeni_isim = f"{name}_{zaman}{ext}"
        
        rel_path = os.path.relpath(local_path, ANA_KLASOR)
        target_dir = os.path.join(ARSIV_KLASOR, neden, os.path.dirname(os.path.relpath(local_path, ANA_KLASOR)))
        target_path = os.path.join(target_dir, yeni_isim)

        os.makedirs(target_dir, exist_ok=True)
        shutil.move(local_path, target_path)
        print(f"{Renk.SARI}    -> [ARŞİVLENDİ] {yeni_isim}{Renk.RESET}")
        return True
    except Exception as e:
        print(f"{Renk.KIRMIZI}    -> [ARŞİV HATASI] {e}{Renk.RESET}")
        return False

def dosya_senkronize_et(url, session, folder_path, varsayilan_isim, ders_adi_log):
    try:
        try:
            response = session.get(url, stream=True, timeout=10)
        except Exception as e:
            # Hata durumunda da tam yolu kestirmeye çalışalım
            rel_path = os.path.join(os.path.relpath(folder_path, ANA_KLASOR), varsayilan_isim)
            print(f"{Renk.KIRMIZI}  [HATA] Bağlantı kurulamadı: {varsayilan_isim}{Renk.RESET}")
            ozet["hata"].append(f"{rel_path} -> (Bağlantı Hatası)")
            return None

        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' in content_type:
            return None

        cd = response.headers.get('content-disposition')
        remote_size = response.headers.get('content-length')
        if remote_size: remote_size = int(remote_size)

        filename = None
        if cd:
            fname = re.findall('filename="?([^"]+)"?', cd)
            if fname:
                try:
                    filename = fname[0].encode('iso-8859-1').decode('utf-8')
                except:
                    filename = fname[0]
        
        if not filename:
            filename = varsayilan_isim + ".pdf"
            
        filename = temizle_dosya_ismi(filename)
        full_path = os.path.join(folder_path, filename)
        
        # Rapor için okunabilir kısa yol (Örn: Mat101/DersDosyalari/Hafta1/not.pdf)
        rapor_yolu = os.path.relpath(full_path, ANA_KLASOR)

        # --- KONTROL ---
        if os.path.exists(full_path):
            local_size = os.path.getsize(full_path)
            
            if remote_size is not None and local_size == remote_size:
                print(f"{Renk.GRI}  [.] {filename}{Renk.RESET}")
                return filename 
            
            # Değişiklik
            print(f"{Renk.SARI}  [!] DEĞİŞİKLİK: {filename}{Renk.RESET}")
            arsivle(full_path, "Changed")
            ozet["degisen"].append(rapor_yolu) # Tam yol eklendi
        else:
            # Yeni Dosya
            print(f"{Renk.YESIL}  [+] YENİ DOSYA: {filename}{Renk.RESET}")
            ozet["yeni"].append(rapor_yolu) # Tam yol eklendi
        
        # İndirme
        with open(full_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        
        return filename

    except Exception as e:
        print(f"{Renk.KIRMIZI}  [HATA] İndirme başarısız: {e}{Renk.RESET}")
        ozet["hata"].append(f"{folder_path}/{varsayilan_isim}: {e}")
        return None

def silinenleri_kontrol_et(folder_path, server_files, ders_adi_log):
    if not os.path.exists(folder_path): return

    local_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    
    for l_file in local_files:
        if l_file.startswith("."): continue
        
        if l_file not in server_files:
            print(f"{Renk.KIRMIZI}  [-] SİLİNMİŞ: {l_file}{Renk.RESET}")
            full_path = os.path.join(folder_path, l_file)
            
            # Rapor için tam yol
            rapor_yolu = os.path.relpath(full_path, ANA_KLASOR)
            
            arsivle(full_path, "Deleted")
            ozet["silinen"].append(rapor_yolu)

def klasor_tarama(driver, session, local_path, ders_adi_log):
    os.makedirs(local_path, exist_ok=True)
    
    try:
        WebDriverWait(driver, 2).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.data")))
    except:
        silinenleri_kontrol_et(local_path, [], ders_adi_log)
        return

    rows = driver.find_elements(By.CSS_SELECTOR, "table.data tr")
    items = []
    found_files = []

    for row in rows:
        cols = row.find_elements(By.TAG_NAME, "td")
        if len(cols) < 2: continue 
        try:
            img = cols[0].find_element(By.TAG_NAME, "img")
            img_src = img.get_attribute("src").lower()
            link_el = row.find_element(By.TAG_NAME, "a")
            items.append({
                "type": "folder" if ("folder" in img_src or "dosya" in img_src) else "file",
                "url": link_el.get_attribute("href"),
                "name": link_el.text.strip()
            })
        except: continue

    for item in items:
        if item["type"] == "folder":
            print(f"{Renk.MAVI} > Alt Klasör: {item['name']}{Renk.RESET}")
            new_path = os.path.join(local_path, temizle_dosya_ismi(item['name']))
            driver.get(item["url"])
            klasor_tarama(driver, session, new_path, ders_adi_log)
            driver.back()
        else:
            saved = dosya_senkronize_et(item["url"], session, local_path, item["name"], ders_adi_log)
            if saved: found_files.append(saved)

    silinenleri_kontrol_et(local_path, found_files, ders_adi_log)

# ==============================================================================
# 🚀 BAŞLATMA
# ==============================================================================
options = Options()
# options.add_argument("--headless=new") 
options.add_argument("--no-sandbox")
options.add_argument('--log-level=3')
if (isHeadless): options.add_argument("--headless=new")

print(f"{Renk.KALIN}🚀 Chrome başlatılıyor...{Renk.RESET}")
driver = webdriver.Chrome(options=options)
driver.get(URL)

# --- LOGIN İŞLEMİ ---
try:
    print("Giriş yapılıyor...")
    
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "oturumAc"))).click()
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_tbUserName"))).send_keys(my_username)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_tbPassword"))).send_keys(my_password)
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_btnLogin"))).click()

    # --- HATA KONTROLÜ ---
    try:
        # 3 saniye içinde hata mesajını bekle
        hata_elementi = WebDriverWait(driver, 3).until(
            EC.visibility_of_element_located((By.ID, "ContentPlaceHolder1_lbHata"))
        )
        
        if hata_elementi.text.strip():
            print(f"\n{Renk.KIRMIZI}⛔ GİRİŞ BAŞARISIZ! (Site Cevabı: {hata_elementi.text}){Renk.RESET}")
            print(f"{Renk.SARI}--------------------------------------------------{Renk.RESET}")
            print(f"{Renk.KALIN}NASIL DÜZELTİLİR?{Renk.RESET}")
            print("1. Kullanıcı adı veya şifreniz hatalı görünüyor.")
            print(f"2. Kayıtlı bilgileri sıfırlamak için klasördeki {Renk.MAVI}'credentials.json'{Renk.RESET} dosyasını silin.")
            print("3. Programı tekrar çalıştırın, doğru bilgileri yeniden girin.")
            print(f"{Renk.SARI}--------------------------------------------------{Renk.RESET}")
            
            driver.quit()
            print("Program kapatılıyor...")
            sys.exit(1) # <-- BURASI DEĞİŞTİ (Kesin çıkış yapar)
            
    except Exception:
        # Hata mesajı çıkmadıysa her şey yolundadır, devam et
        pass

    # Başarılı giriş kontrolü
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "menuErisimAgaci")))
    print(f"{Renk.YESIL}✅ Giriş Başarılı!{Renk.RESET}")

except SystemExit:
    # sys.exit() çağrıldığında buraya düşer, programı gerçekten kapatır
    sys.exit(1)
except Exception as e:
    print(f"\n{Renk.KIRMIZI}❌ Beklenmedik bir hata oluştu: {e}{Renk.RESET}")
    driver.quit()
    sys.exit(1)

# --- SETUP ---
session = requests.Session()
for cookie in driver.get_cookies(): session.cookies.set(cookie['name'], cookie['value'])
session.headers.update({"User-Agent": driver.execute_script("return navigator.userAgent;")})

# --- DERS LİSTESİ ---
print("Ders listesi alınıyor...")
ders_maddeleri = driver.find_elements(By.CSS_SELECTOR, ".menuErisimAgaci > ul > li")
hedef_dersler = []

for madde in ders_maddeleri:
    try:
        kod = madde.find_element(By.XPATH, "./span").text
        link_el = madde.find_element(By.CSS_SELECTOR, "ul li a")
        link = link_el.get_attribute("href")
        donem = link_el.text
        full_name = f"{kod} - {donem}"
        if link: hedef_dersler.append((full_name, link))
        print(f"Listeye eklendi: {full_name}")
    except: continue

print(f"Toplam {len(hedef_dersler)} ders bulundu.\n")

# --- ANA DÖNGÜ ---
for ders_adi, ders_link in hedef_dersler:
    safe_ders_adi = temizle_dosya_ismi(ders_adi)
    print(f"{Renk.MOR}════════════════════════════════════════════════════════════{Renk.RESET}")
    print(f"{Renk.KALIN}[{safe_ders_adi}]{Renk.RESET} Senkronize Ediliyor...")
    
    base_path = os.path.join(ANA_KLASOR, safe_ders_adi)
    moduller = ["/DersDosyalari", "/SinifDosyalari"]

    for mod in moduller:
        driver.get(ders_link.rstrip('/') + mod)
        if "bulunamadı" not in driver.title.lower():
            klasor_tarama(driver, session, os.path.join(base_path, mod.replace("/","")), safe_ders_adi)

driver.quit()

# ==============================================================================
# 📊 SONUÇ RAPORU (TAM YOL GÖSTERİMLİ)
# ==============================================================================
print(f"\n\n{Renk.KALIN}████████████████████  SONUÇ RAPORU  ████████████████████{Renk.RESET}")

if not (ozet["yeni"] or ozet["degisen"] or ozet["silinen"] or ozet["hata"]):
    print(f"\n{Renk.YESIL}✅ Her şey güncel! Hiçbir değişiklik yok.{Renk.RESET}")
else:
    # Listeleri alfabetik sırala ki aynı dersin dosyaları alt alta gelsin
    ozet["yeni"].sort()
    ozet["degisen"].sort()
    ozet["silinen"].sort()

    if ozet["yeni"]:
        print(f"\n{Renk.YESIL}[+] YENİ EKLENEN DOSYALAR ({len(ozet['yeni'])}):{Renk.RESET}")
        for f in ozet["yeni"]: 
            print(f"  📂 {f}")

    if ozet["degisen"]:
        print(f"\n{Renk.SARI}[!] DEĞİŞEN DOSYALAR ({len(ozet['degisen'])}):{Renk.RESET}")
        for f in ozet["degisen"]: 
            print(f"  📝 {f}")

    if ozet["silinen"]:
        print(f"\n{Renk.KIRMIZI}[-] SİLİNEN DOSYALAR ({len(ozet['silinen'])}):{Renk.RESET}")
        for f in ozet["silinen"]: 
            print(f"  🗑️  {f}")
        
    if ozet["hata"]:
        print(f"\n{Renk.KIRMIZI}[X] HATALAR ({len(ozet['hata'])}):{Renk.RESET}")
        for f in ozet["hata"]: 
            print(f"  ❌ {f}")

print(f"\n{Renk.KALIN}İşlem Tamamlandı.{Renk.RESET}")