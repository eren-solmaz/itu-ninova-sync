import os
import sys
import time
import json
import hashlib
import requests
import re
import shutil
from getpass import getpass
from datetime import datetime
import keyring
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
CONFIG_FILE = "config.json"
SERVICE_NAME = "NinovaAutomation"
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

# --- 1. KİMLİK BİLGİLERİ (KEYRING ENTEGRASYONU) ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

config = load_config()
my_username = config.get("username")

if not my_username:
    print(f"{Renk.SARI}--------------------------------------------------{Renk.RESET}")
    print(f"{Renk.KALIN}🚀 Sisteme ilk defa giriş yapıyorsunuz.{Renk.RESET}")
    my_username = input(f"{Renk.MAVI}{Renk.KALIN}👉 Kullanıcı Adı: {Renk.RESET}")
    new_password = getpass(f"{Renk.MAVI}{Renk.KALIN}👉 Şifre: {Renk.RESET}")
    
    # Şifreyi OS Keyring'e kaydet
    keyring.set_password(SERVICE_NAME, my_username, new_password)
    
    # Kullanıcı adını config'e kaydet (Kullanıcı adı gizli bilgi değildir)
    config["username"] = my_username
    save_config(config)
    print(f"\n{Renk.YESIL}✅ Şifreniz işletim sisteminin güvenli kasasına (Keyring) kaydedildi.{Renk.RESET}\n")

# Keyring'den şifreyi güvenli bir şekilde çek
my_password = keyring.get_password(SERVICE_NAME, my_username)

if not my_password:
    print(f"{Renk.SARI}[!] Keyring kasasında şifre bulunamadı, lütfen tekrar girin.{Renk.RESET}")
    my_password = getpass(f"{Renk.MAVI}{Renk.KALIN}👉 Şifre: {Renk.RESET}")
    keyring.set_password(SERVICE_NAME, my_username, my_password)

print(f"{Renk.YESIL}Bilgiler yüklendi: {Renk.KALIN}{my_username}{Renk.RESET}")

# --- YARDIMCI FONKSİYONLAR ---

def temizle_dosya_ismi(isim):
    if not isim: return "isimsiz_dosya"
    yasakli = r'[\\/*?:"<>|]'
    temiz = re.sub(yasakli, '', isim)
    return temiz.strip()

def metin_hash_hesapla(metin):
    # Satır sonu farklarını (\r\n vs \n) normalize ederek SHA-256 hash üretir
    normalized = metin.replace("\r\n", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def arsivle(local_path, neden):
    try:
        filename = os.path.basename(local_path)
        name, ext = os.path.splitext(filename)
        zaman = datetime.now().strftime("%Y%m%d_%H%M%S")
        yeni_isim = f"{name}_{zaman}{ext}"
        
        rel_path = os.path.relpath(local_path, ANA_KLASOR)
        target_dir = os.path.join(ARSIV_KLASOR, neden, os.path.dirname(rel_path))
        target_path = os.path.join(target_dir, yeni_isim)

        os.makedirs(target_dir, exist_ok=True)
        shutil.move(local_path, target_path)
        return True
    except Exception as e:
        return False

def dosya_senkronize_et(url, session, folder_path, varsayilan_isim, remote_date_str, indent_level):
    indent_str = "│   " * indent_level
    filename = None
    is_weblink = False
    content_type = ""
    
    # 1. Link Kontrolü (HEAD)
    try:
        head_resp = session.head(url, allow_redirects=True, timeout=5)
        
        if head_resp.status_code >= 400:
            is_weblink = True
        else:
            content_type = head_resp.headers.get('content-type', '').lower()
            if 'text/html' in content_type:
                is_weblink = True
            else:
                cd = head_resp.headers.get('content-disposition')
                if cd:
                    fname = re.findall('filename="?([^"]+)"?', cd)
                    if fname:
                        try:
                            filename = fname[0].encode('iso-8859-1').decode('utf-8')
                        except:
                            filename = fname[0]
        
    except requests.exceptions.RequestException:
        is_weblink = True
    except Exception:
        is_weblink = True

    # Eğer web bağlantısı ise .url kısayol dosyası olarak kaydet
    if is_weblink:
        filename = temizle_dosya_ismi(varsayilan_isim) + ".url"
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
                    print(f"{indent_str}{Renk.SARI}[!] WEB LİNK GÜNCELLENDİ: {varsayilan_isim}{Renk.RESET}")
                    arsivle(full_path, "Changed")
                    dosya_indirilmeli = True
                    durum = "GÜNCEL"
                else:
                    print(f"{indent_str}{Renk.GRI}[.] Web Link Güncel: {varsayilan_isim} ({remote_date_str}){Renk.RESET}")
                    return filename

            if dosya_indirilmeli:
                if durum == "YENİ":
                    print(f"{indent_str}{Renk.YESIL}[🌐] YENİ WEB LİNK: {varsayilan_isim}{Renk.RESET}")
                
                url_icerigi = f"[InternetShortcut]\nURL={url}\n"
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(url_icerigi)
                
                files_metadata[rel_path_key] = remote_date_str
                save_metadata()

                if durum == "YENİ": ozet["yeni"].append(rapor_yolu)
                elif durum == "GÜNCEL": ozet["degisen"].append(rapor_yolu)
            
            return filename
        except Exception as e:
            print(f"{indent_str}{Renk.KIRMIZI}[HATA] Web link kaydedilemedi: {e}{Renk.RESET}")
            ozet["hata"].append(f"{folder_path}/{varsayilan_isim}: {e}")
            return None

    # Normal dosya indirme mantığı (PDF, PPTX vb.)
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
                # GET isteğinde beklenmedik şekilde HTML gelirse web link olarak kaydet
                url_icerigi = f"[InternetShortcut]\nURL={url}\n"
                weblink_filename = temizle_dosya_ismi(varsayilan_isim) + ".url"
                weblink_full_path = os.path.join(folder_path, weblink_filename)
                with open(weblink_full_path, 'w', encoding='utf-8') as f:
                    f.write(url_icerigi)
                print(f"{indent_str}{Renk.YESIL}[🌐] WEB LİNK OLARAK KAYDEDİLDİ: {varsayilan_isim}{Renk.RESET}")
                files_metadata[rel_path_key] = remote_date_str
                save_metadata()
                if durum == "YENİ": ozet["yeni"].append(rapor_yolu)
                elif durum == "GÜNCEL": ozet["degisen"].append(rapor_yolu)
                return weblink_filename

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

def duyurulari_tara(driver, duyuru_base_path, indent_level=1):
    os.makedirs(duyuru_base_path, exist_ok=True)
    indent_str = "│   " * indent_level
    
    duyurular_info = []
    try:
        # Ana duyurular sayfasındaki tüm duyuru kutularını bul
        duyuru_divleri = driver.find_elements(By.CSS_SELECTOR, "div.duyuruGoruntule")
        for div in duyuru_divleri:
            try:
                a_el = div.find_element(By.CSS_SELECTOR, "h2 a")
                title = a_el.text.strip()
                url = a_el.get_attribute("href")
                
                tarih_els = div.find_elements(By.CSS_SELECTOR, "div.tarih")
                date_str = tarih_els[0].text.strip() if tarih_els else "TarihYok"
                
                if url:
                    duyurular_info.append({
                        "title": title,
                        "url": url,
                        "date": date_str
                    })
            except Exception:
                continue
    except Exception:
        pass

    found_files = []
    name_counts = {}

    for duyuru in duyurular_info:
        base_clean_name = temizle_dosya_ismi(duyuru["title"])
        
        # Aynı başlığa sahip birden fazla duyuru varsa üzerine yazmamak için numaralandır
        if base_clean_name in name_counts:
            name_counts[base_clean_name] += 1
            filename = f"{base_clean_name}_({name_counts[base_clean_name]}).txt"
        else:
            name_counts[base_clean_name] = 1
            filename = f"{base_clean_name}.txt"

        full_path = os.path.join(duyuru_base_path, filename)
        rel_path_key = os.path.relpath(full_path, ANA_KLASOR)
        rapor_yolu = rel_path_key
        remote_date_str = duyuru["date"]

        try:
            # Hoca tarihi değiştirmeden içeriği güncelleyebildiği için
            # her duyurunun detay sayfasına gidip tam metni çekiyoruz.
            driver.get(duyuru["url"])
            detay_div = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.duyuruGoruntule"))
            )
            
            icerik_text = ""
            try:
                icerik_el = detay_div.find_element(By.CSS_SELECTOR, "div.icerik")
                icerik_text = icerik_el.text.strip()
            except:
                pass
            
            yazar_text = ""
            try:
                yazar_el = detay_div.find_element(By.CSS_SELECTOR, "span[id$='lbKullanici']")
                yazar_text = yazar_el.text.strip()
            except:
                pass

            try:
                baslangic_el = detay_div.find_element(By.CSS_SELECTOR, "span[id$='lblBaslangic']")
                if baslangic_el.text.strip():
                    remote_date_str = baslangic_el.text.strip()
            except:
                pass

            # .txt içeriğini oluştur
            txt_content = f"Başlık : {duyuru['title']}\n"
            txt_content += f"Tarih  : {remote_date_str}\n"
            if yazar_text:
                txt_content += f"Yazan  : {yazar_text}\n"
            txt_content += f"Link   : {duyuru['url']}\n"
            txt_content += "=" * 60 + "\n\n"
            txt_content += icerik_text + "\n"

            remote_hash = metin_hash_hesapla(txt_content)

            dosya_kaydedilmeli = False
            durum = ""

            if not os.path.exists(full_path):
                dosya_kaydedilmeli = True
                durum = "YENİ"
            else:
                # 1. Doğrudan lokaldeki dosyanın içeriğini oku ve karşılaştır
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        local_content = f.read()
                    local_hash = metin_hash_hesapla(local_content)
                except:
                    local_hash = None

                # İçerik (hash) değişmiş mi kontrol et
                if local_hash != remote_hash:
                    print(f"{indent_str}{Renk.SARI}[!] DUYURU İÇERİĞİ GÜNCELLENDİ: {filename}{Renk.RESET}")
                    arsivle(full_path, "Changed")
                    dosya_kaydedilmeli = True
                    durum = "GÜNCEL"
                else:
                    print(f"{indent_str}{Renk.GRI}[.] Duyuru Güncel: {filename} ({remote_date_str}){Renk.RESET}")
                    # Eğer metadata'da eski tarih bazlı kayıt kalmışsa hash ile güncelle
                    if files_metadata.get(rel_path_key) != remote_hash:
                        files_metadata[rel_path_key] = remote_hash
                        save_metadata()

            if dosya_kaydedilmeli:
                if durum == "YENİ":
                    print(f"{indent_str}{Renk.YESIL}[📢] YENİ DUYURU: {filename}{Renk.RESET}")

                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(txt_content)

                files_metadata[rel_path_key] = remote_hash
                save_metadata()

                if durum == "YENİ": ozet["yeni"].append(rapor_yolu)
                elif durum == "GÜNCEL": ozet["degisen"].append(rapor_yolu)

            found_files.append(filename)

        except Exception as e:
            print(f"{indent_str}{Renk.KIRMIZI}[HATA] Duyuru kontrol edilemedi/kaydedilemedi ({filename}): {e}{Renk.RESET}")
            ozet["hata"].append(f"{duyuru_base_path}/{filename}: {e}")
            # Hata olsa bile lokalde dosya varsa yanlışlıkla silinmiş sanıp arşivlemesin
            if os.path.exists(full_path):
                found_files.append(filename)

    silinenleri_kontrol_et(duyuru_base_path, found_files, indent_level=indent_level)

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

# --- OTOMATİK GİRİŞ (LOGIN) ---
try:
    print("Giriş yapılıyor...")
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "oturumAc"))).click()
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_tbUserName"))).send_keys(my_username)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_tbPassword"))).send_keys(my_password)
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_btnLogin"))).click()

    try:
        hata_elementi = WebDriverWait(driver, 3).until(EC.visibility_of_element_located((By.ID, "ContentPlaceHolder1_lbHata")))
        if hata_elementi.text.strip():
            print(f"\n{Renk.KIRMIZI}⛔ GİRİŞ BAŞARISIZ! Kullanıcı adı veya şifre hatalı.{Renk.RESET}")
            driver.quit()
            sys.exit(1)
    except: pass

    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "menuErisimAgaci")))
    print(f"{Renk.YESIL}✅ Giriş Başarılı!{Renk.RESET}")

except Exception as e:
    print(f"\n{Renk.KIRMIZI}❌ Giriş Hatası: {e}{Renk.RESET}")
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
    moduller = ["/DersDosyalari", "/SinifDosyalari", "/Odevler", "/Duyurular"]

    for mod in moduller:
        driver.get(ders_link.rstrip('/') + mod)
        if "bulunamadı" not in driver.title.lower():
            if mod == "/Odevler":
                # --- ÖDEVLERİ TARA VE İNDİR ---
                odev_base_path = os.path.join(base_path, "Odevler")
                os.makedirs(odev_base_path, exist_ok=True)
                
                odevler_info = []
                try:
                    # Ana ödev listesinden başlıkları ve linkleri topla
                    rows = driver.find_elements(By.CSS_SELECTOR, "table[id$='gvOdevListesi'] tr td")
                    for td in rows:
                        try:
                            title_el = td.find_element(By.TAG_NAME, "h2")
                            title = title_el.text.strip()
                            
                            links = td.find_elements(By.TAG_NAME, "a")
                            link_url = None
                            for a in links:
                                href = a.get_attribute("href")
                                if href and "/Odev/" in href:
                                    link_url = href
                                    break
                            
                            if link_url:
                                odevler_info.append({"title": title, "url": link_url})
                        except: continue
                except Exception:
                    pass

                for odev in odevler_info:
                    hw_folder = os.path.join(odev_base_path, temizle_dosya_ismi(odev["title"]))
                    os.makedirs(hw_folder, exist_ok=True)
                    print(f"│   {Renk.MAVI}📝 [{odev['title']}]{Renk.RESET}")
                    
                    driver.get(odev["url"])
                    
                    try:
                        # Ödev sayfasındaki Kaynak Dosyalar tablosunu bul (gvDosyalar)
                        table = WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "table[id$='gvDosyalar']"))
                        )
                        rows = table.find_elements(By.CSS_SELECTOR, "tr")
                        
                        found_files = []
                        for row in rows:
                            cols = row.find_elements(By.TAG_NAME, "td")
                            if len(cols) < 2: continue
                            
                            try:
                                link_el = cols[0].find_element(By.TAG_NAME, "a")
                                url = link_el.get_attribute("href")
                                name = link_el.text.strip()
                                
                                date_text = "TarihYok"
                                if len(cols) >= 3:
                                    date_text = cols[-1].text.strip()
                                    
                                saved_name = dosya_senkronize_et(
                                    url, session, hw_folder, name, date_text, indent_level=2
                                )
                                if saved_name: found_files.append(saved_name)
                            except: continue
                                
                        silinenleri_kontrol_et(hw_folder, found_files, indent_level=2)
                    except:
                        # Tablo yoksa ödeve ekli dosya yoktur
                        silinenleri_kontrol_et(hw_folder, [], indent_level=2)

            elif mod == "/Duyurular":
                # --- DUYURULARI TARA VE .TXT OLARAK KAYDET ---
                duyuru_base_path = os.path.join(base_path, "Duyurular")
                print(f"│   {Renk.MAVI}📢 [Duyurular]{Renk.RESET}")
                duyurulari_tara(driver, duyuru_base_path, indent_level=2)

            else:
                # --- NORMAL DERS VE SINIF DOSYALARINI TARA ---
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
        print(f"\n{Renk.YESIL}[+] YENİ EKLENEN DOSYALAR / LİNKLER ({len(ozet['yeni'])}):{Renk.RESET}")
        for f in ozet["yeni"]: print(f"  📂 {f}")

    if ozet["degisen"]:
        print(f"\n{Renk.SARI}[!] TARİHİ / İÇERİĞİ DEĞİŞEN DOSYALAR ({len(ozet['degisen'])}):{Renk.RESET}")
        for f in ozet["degisen"]: print(f"  📝 {f}")

    if ozet["silinen"]:
        print(f"\n{Renk.KIRMIZI}[-] SİLİNEN DOSYALAR / LİNKLER ({len(ozet['silinen'])}):{Renk.RESET}")
        for f in ozet["silinen"]: print(f"  🗑️  {f}")
        
    if ozet["hata"]:
        print(f"\n{Renk.KIRMIZI}[X] HATALAR ({len(ozet['hata'])}):{Renk.RESET}")
        for f in ozet["hata"]: print(f"  ❌ {f}")

print(f"\n{Renk.KALIN}İşlem Tamamlandı.{Renk.RESET}")