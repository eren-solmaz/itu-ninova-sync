import os
import sys
import time
import json
import requests
import re
import shutil
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
METADATA_FILE = "dosya_takip.json"
isHeadless = False

# --- ÖZET RAPOR LİSTELERİ ---
ozet = {
    "yeni": [],
    "degisen": [],
    "silinen": [],
    "hata": []
}

files_metadata = {}

def load_metadata():
    global files_metadata
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                files_metadata = json.load(f)
        except:
            files_metadata = {}

def save_metadata():
    try:
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(files_metadata, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"{Renk.KIRMIZI}Metadata kaydedilemedi: {e}{Renk.RESET}")

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
        return True
    except Exception as e:
        return False

def dosya_senkronize_et(url, session, folder_path, varsayilan_isim, remote_date_str, indent_level):
    indent_str = "│   " * indent_level
    filename = None
    
    # 1. Link Kontrolü (HEAD)
    try:
        head_resp = session.head(url, allow_redirects=True, timeout=5)
        
        if head_resp.status_code >= 400:
            print(f"{indent_str}{Renk.GRI}[i] Dış Bağlantı / Erişilemiyor (Atlandı): {varsayilan_isim}{Renk.RESET}")
            return None

        content_type = head_resp.headers.get('content-type', '').lower()
        if 'text/html' in content_type:
            print(f"{indent_str}{Renk.GRI}[i] Web Bağlantısı (Atlandı): {varsayilan_isim}{Renk.RESET}")
            return None

        cd = head_resp.headers.get('content-disposition')
        if cd:
            fname = re.findall('filename="?([^"]+)"?', cd)
            if fname:
                try:
                    filename = fname[0].encode('iso-8859-1').decode('utf-8')
                except:
                    filename = fname[0]
        
    except requests.exceptions.RequestException:
        print(f"{indent_str}{Renk.GRI}[i] Bağlantı Hatası / Dış Link (Atlandı): {varsayilan_isim}{Renk.RESET}")
        return None
    except Exception:
        pass

    if not filename:
        filename = varsayilan_isim
        if "." not in filename: 
             filename += ".pdf"
    
    filename = temizle_dosya_ismi(filename)
    full_path = os.path.join(folder_path, filename)
    rel_path_key = os.path.relpath(full_path, ANA_KLASOR)
    rapor_yolu = rel_path_key

    try:
        dosya_indirilmeli = False
        durum = ""

        if not os.path.exists(full_path):
            dosya_indirilmeli = True
            durum = "YENİ"
        else:
            local_stored_date = files_metadata.get(rel_path_key)
            if local_stored_date != remote_date_str:
                print(f"{indent_str}{Renk.SARI}[!] GÜNCELLEME: {filename}{Renk.RESET}")
                print(f"{indent_str}    Eski: {local_stored_date} -> Yeni: {remote_date_str}")
                arsivle(full_path, "Changed")
                dosya_indirilmeli = True
                durum = "GÜNCEL"
            else:
                print(f"{indent_str}{Renk.GRI}[.] Güncel: {filename} ({remote_date_str}){Renk.RESET}")
                return filename

        if dosya_indirilmeli:
            if durum == "YENİ":
                print(f"{indent_str}{Renk.YESIL}[+] İNDİRİLİYOR: {filename}{Renk.RESET}")
            
            response = session.get(url, stream=True, timeout=20)
            if 'text/html' in response.headers.get('content-type', '').lower():
                print(f"{indent_str}{Renk.GRI}[i] İndirme iptal (Web Sayfası): {filename}{Renk.RESET}")
                return None

            with open(full_path, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            
            files_metadata[rel_path_key] = remote_date_str
            save_metadata()

            if durum == "YENİ": ozet["yeni"].append(rapor_yolu)
            elif durum == "GÜNCEL": ozet["degisen"].append(rapor_yolu)
        
        return filename

    except Exception as e:
        print(f"{indent_str}{Renk.KIRMIZI}[HATA] İndirme başarısız: {e}{Renk.RESET}")
        ozet["hata"].append(f"{folder_path}/{varsayilan_isim}: {e}")
        return None

def silinenleri_kontrol_et(folder_path, server_files, indent_level):
    if not os.path.exists(folder_path): return
    indent_str = "│   " * indent_level

    local_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    
    for l_file in local_files:
        if l_file.startswith("."): continue
        
        if l_file not in server_files:
            print(f"{indent_str}{Renk.KIRMIZI}[-] SİLİNMİŞ: {l_file}{Renk.RESET}")
            full_path = os.path.join(folder_path, l_file)
            rapor_yolu = os.path.relpath(full_path, ANA_KLASOR)
            
            if rapor_yolu in files_metadata:
                del files_metadata[rapor_yolu]
                save_metadata()

            arsivle(full_path, "Deleted")
            ozet["silinen"].append(rapor_yolu)

def klasor_tarama(driver, session, local_path, indent_level=0):
    os.makedirs(local_path, exist_ok=True)
    indent_str = "│   " * indent_level
    
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.data")))
    except:
        silinenleri_kontrol_et(local_path, [], indent_level)
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
            link_el = cols[0].find_element(By.TAG_NAME, "a")
            url = link_el.get_attribute("href")
            name = link_el.text.strip()
            
            date_text = "TarihYok"
            if len(cols) >= 3:
                candidate_date = cols[-1].text.strip()
                if not candidate_date and len(cols) > 2:
                    candidate_date = cols[-2].text.strip()
                date_text = candidate_date

            items.append({
                "type": "folder" if ("folder" in img_src or "dosya" in img_src) else "file",
                "url": url,
                "name": name,
                "date": date_text
            })
        except: 
            continue

    for item in items:
        if item["type"] == "folder":
            print(f"{indent_str}{Renk.MAVI}📂 [{item['name']}]{Renk.RESET}")
            
            new_path = os.path.join(local_path, temizle_dosya_ismi(item['name']))
            driver.get(item["url"])
            
            klasor_tarama(driver, session, new_path, indent_level + 1)
            
            driver.back()
        else:
            saved_name = dosya_senkronize_et(
                item["url"], 
                session, 
                local_path, 
                item["name"], 
                item["date"],
                indent_level 
            )
            if saved_name: found_files.append(saved_name)

    silinenleri_kontrol_et(local_path, found_files, indent_level)

# ==============================================================================
# 🚀 BAŞLATMA
# ==============================================================================
load_metadata()

options = Options()
options.add_argument("--no-sandbox")
options.add_argument('--log-level=3')
if (isHeadless): options.add_argument("--headless=new")

print(f"{Renk.KALIN}🚀 Chrome başlatılıyor...{Renk.RESET}")
driver = webdriver.Chrome(options=options)
driver.get(URL)

# --- MANUEL GİRİŞ BEKLEME (60 SANİYE) ---
try:
    print(f"\n{Renk.SARI}⏳ Lütfen tarayıcı üzerinden 60 saniye içinde giriş yapın...{Renk.RESET}")
    print(f"{Renk.GRI}(Giriş yaptıktan sonra ders menüsü yüklenene kadar bekleniyor){Renk.RESET}\n")
    
    # Kullanıcının manuel giriş yapıp menüye ulaşmasını (menuErisimAgaci elemanının görünmesini) 60 sn boyunca bekler
    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.CLASS_NAME, "menuErisimAgaci"))
    )
    print(f"{Renk.YESIL}✅ Giriş Algılandı ve Başarılı!{Renk.RESET}")

except Exception as e:
    print(f"\n{Renk.KIRMIZI}❌ 60 saniye içinde giriş yapılamadı veya zaman aşımına uğradı. Program sonlandırılıyor.{Renk.RESET}")
    driver.quit()
    sys.exit(1)

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
        #full_name = f"{kod} - {donem}"
        full_name = kod
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
            klasor_tarama(driver, session, os.path.join(base_path, mod.replace("/","")), indent_level=0)

driver.quit()

# ==============================================================================
# 📊 SONUÇ RAPORU
# ==============================================================================
print(f"\n\n{Renk.KALIN}████████████████████  SONUÇ RAPORU  ████████████████████{Renk.RESET}")

if not (ozet["yeni"] or ozet["degisen"] or ozet["silinen"] or ozet["hata"]):
    print(f"\n{Renk.YESIL}✅ Her şey güncel!{Renk.RESET}")
else:
    ozet["yeni"].sort()
    ozet["degisen"].sort()
    ozet["silinen"].sort()

    if ozet["yeni"]:
        print(f"\n{Renk.YESIL}[+] YENİ EKLENEN DOSYALAR ({len(ozet['yeni'])}):{Renk.RESET}")
        for f in ozet["yeni"]: print(f"  📂 {f}")

    if ozet["degisen"]:
        print(f"\n{Renk.SARI}[!] TARİHİ DEĞİŞEN (GÜNCELLENEN) DOSYALAR ({len(ozet['degisen'])}):{Renk.RESET}")
        for f in ozet["degisen"]: print(f"  📝 {f}")

    if ozet["silinen"]:
        print(f"\n{Renk.KIRMIZI}[-] SİLİNEN DOSYALAR ({len(ozet['silinen'])}):{Renk.RESET}")
        for f in ozet["silinen"]: print(f"  🗑️  {f}")
        
    if ozet["hata"]:
        print(f"\n{Renk.KIRMIZI}[X] HATALAR ({len(ozet['hata'])}):{Renk.RESET}")
        for f in ozet["hata"]: print(f"  ❌ {f}")

print(f"\n{Renk.KALIN}İşlem Tamamlandı.{Renk.RESET}")