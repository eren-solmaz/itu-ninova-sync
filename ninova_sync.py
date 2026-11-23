import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from getpass import getpass

import keyring
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

os.system("")


class Renk:
    MOR = '\033[95m'
    MAVI = '\033[94m'
    CYAN = '\033[96m'
    YESIL = '\033[92m'
    SARI = '\033[93m'
    KIRMIZI = '\033[91m'
    GRI = '\033[90m'
    KALIN = '\033[1m'
    RESET = '\033[0m'


# --- AYARLAR ---
ANA_KLASOR = "ITU_Dersleri"
ARSIV_KLASOR = os.path.join(ANA_KLASOR, "_ARSIV")
URL = "https://ninova.itu.edu.tr/tr/"
METADATA_FILE = "dosya_takip.json"
CONFIG_FILE = "config.json"
SERVICE_NAME = "NinovaAutomation"
IS_HEADLESS = False


# --- SAF YARDIMCI FONKSİYONLAR ---
def json_yukle(dosya_yolu):
    if os.path.exists(dosya_yolu):
        try:
            with open(dosya_yolu, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def json_kaydet(dosya_yolu, veri):
    with open(dosya_yolu, "w", encoding="utf-8") as f:
        json.dump(veri, f, indent=4, ensure_ascii=False)


def temizle_dosya_ismi(isim):
    if not isim:
        return "isimsiz_dosya"
    return re.sub(r'[\\/*?:"<>|]', '', isim).strip()


def metin_hash_hesapla(metin):
    normalized = metin.replace("\r\n", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def kimlik_bilgilerini_al():
    config = json_yukle(CONFIG_FILE)
    username = config.get("username")

    if not username:
        print(f"{Renk.SARI}--------------------------------------------------{Renk.RESET}")
        print(f"{Renk.KALIN}🚀 Sisteme ilk defa giriş yapıyorsunuz.{Renk.RESET}")
        username = input(f"{Renk.MAVI}{Renk.KALIN}👉 Kullanıcı Adı: {Renk.RESET}")
        password = getpass(f"{Renk.MAVI}{Renk.KALIN}👉 Şifre: {Renk.RESET}")

        keyring.set_password(SERVICE_NAME, username, password)
        config["username"] = username
        json_kaydet(CONFIG_FILE, config)
        print(f"\n{Renk.YESIL}✅ Şifreniz işletim sisteminin güvenli kasasına (Keyring) kaydedildi.{Renk.RESET}\n")
    else:
        password = keyring.get_password(SERVICE_NAME, username)
        if not password:
            print(f"{Renk.SARI}[!] Keyring kasasında şifre bulunamadı, lütfen tekrar girin.{Renk.RESET}")
            password = getpass(f"{Renk.MAVI}{Renk.KALIN}👉 Şifre: {Renk.RESET}")
            keyring.set_password(SERVICE_NAME, username, password)

    print(f"{Renk.YESIL}Bilgiler yüklendi: {Renk.KALIN}{username}{Renk.RESET}")
    return username, password


def kimlik_bilgilerini_sil():
    """Keyring üzerindeki şifreyi ve config.json dosyasındaki kullanıcı adını temizler."""
    config = json_yukle(CONFIG_FILE)
    username = config.get("username")

    if username:
        try:
            keyring.delete_password(SERVICE_NAME, username)
        except keyring.errors.PasswordDeleteError:
            pass
        except Exception as e:
            print(f"{Renk.SARI}[!] Keyring silme uyarısı: {e}{Renk.RESET}")

    if os.path.exists(CONFIG_FILE):
        try:
            os.remove(CONFIG_FILE)
        except Exception as e:
            print(f"{Renk.KIRMIZI}[!] {CONFIG_FILE} silinemedi: {e}{Renk.RESET}")

    if username:
        print(f"{Renk.YESIL}🗑️  '{username}' hesabına ait yerel ve Keyring kayıtları silindi.{Renk.RESET}")
    else:
        print(f"{Renk.GRI}[i] Kayıtlı bir kullanıcı bulunamadı.{Renk.RESET}")


def sifre_guncelle():
    """Mevcut kullanıcı için Keyring üzerindeki şifreyi günceller."""
    config = json_yukle(CONFIG_FILE)
    username = config.get("username")

    if not username:
        print(f"{Renk.KIRMIZI}[!] Kayıtlı kullanıcı bulunamadı. Önce yeni giriş oluşturun.{Renk.RESET}")
        return None

    yeni_sifre = getpass(f"{Renk.MAVI}{Renk.KALIN}👉 '{username}' için yeni şifre: {Renk.RESET}")
    if not yeni_sifre:
        print(f"{Renk.SARI}[!] Boş şifre girildi, işlem iptal edildi.{Renk.RESET}")
        return None

    keyring.set_password(SERVICE_NAME, username, yeni_sifre)
    print(f"{Renk.YESIL}✅ '{username}' için Keyring şifresi güncellendi.{Renk.RESET}")
    return yeni_sifre


# --- ANA SENKRONİZASYON SINIFI ---
class NinovaSync:
    def __init__(self, username, password, headless=False):
        self.username = username
        self.password = password
        self.headless = headless
        self.driver = None
        self.session = None
        self.metadata = json_yukle(METADATA_FILE)
        self.taranan_dersler = []
        self.ozet = {
            "yeni": [],
            "degisen": [],
            "silinen": [],
            "hata": []
        }

    def _metadata_kaydet(self):
        try:
            json_kaydet(METADATA_FILE, self.metadata)
        except Exception as e:
            print(f"{Renk.KIRMIZI}Metadata kaydedilemedi: {e}{Renk.RESET}")

    def _arsivle(self, local_path, neden):
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
        except Exception:
            return False

    def _ozete_ekle(self, durum, rapor_yolu):
        if durum == "YENİ":
            self.ozet["yeni"].append(rapor_yolu)
        elif durum == "GÜNCEL":
            self.ozet["degisen"].append(rapor_yolu)

    # --- TARAYICI VE OTURUM YÖNETİMİ ---
    def tarayici_baslat(self):
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--log-level=3")
        if self.headless:
            options.add_argument("--headless=new")

        print(f"{Renk.KALIN}🚀 Chrome başlatılıyor...{Renk.RESET}")
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(URL)

    def tarayici_kapat(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def giris_yap(self):
        while True:
            try:
                print("Giriş yapılıyor...")
                if "ninova.itu.edu.tr" not in self.driver.current_url:
                    self.driver.get(URL)

                # Zaten giriş formundaysak tekrar oturumAc'a tıklamaya çalışma
                if not self.driver.find_elements(By.ID, "ContentPlaceHolder1_tbUserName"):
                    WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CLASS_NAME, "oturumAc"))
                    ).click()

                user_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_tbUserName"))
                )
                pass_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "ContentPlaceHolder1_tbPassword"))
                )

                user_input.clear()
                user_input.send_keys(self.username)
                pass_input.clear()
                pass_input.send_keys(self.password)

                WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "ContentPlaceHolder1_btnLogin"))
                ).click()

                try:
                    hata_el = WebDriverWait(self.driver, 3).until(
                        EC.visibility_of_element_located((By.ID, "ContentPlaceHolder1_lbHata"))
                    )
                    if hata_el.text.strip():
                        print(f"\n{Renk.KIRMIZI}⛔ GİRİŞ BAŞARISIZ! Kullanıcı adı veya şifre hatalı.{Renk.RESET}")
                        if not self._hatali_giris_coz():
                            sys.exit(1)
                        continue
                except SystemExit:
                    raise
                except Exception:
                    pass

                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "menuErisimAgaci"))
                )
                print(f"{Renk.YESIL}✅ Giriş Başarılı!{Renk.RESET}")
                break

            except SystemExit:
                raise
            except Exception as e:
                print(f"\n{Renk.KIRMIZI}❌ Giriş Hatası: {e}{Renk.RESET}")
                sys.exit(1)

        self.session = requests.Session()
        for cookie in self.driver.get_cookies():
            self.session.cookies.set(cookie["name"], cookie["value"])
        self.session.headers.update({"User-Agent": self.driver.execute_script("return navigator.userAgent;")})

    def _hatali_giris_coz(self):
        """Giriş başarısız olduğunda kullanıcıya şifre güncelleme veya hesabı sıfırlama seçeneği sunar."""
        print(f"\n{Renk.SARI}Ne yapmak istersiniz?{Renk.RESET}")
        print(f"  {Renk.CYAN}1.{Renk.RESET} '{Renk.KALIN}{self.username}{Renk.RESET}' için yeni şifre gir ve tekrar dene")
        print(f"  {Renk.CYAN}2.{Renk.RESET} Kayıtlı hesabı sil (kullanıcı adı + şifre) ve baştan gir")
        print(f"  {Renk.CYAN}3.{Renk.RESET} Çıkış yap")

        while True:
            secim = input(f"{Renk.MAVI}{Renk.KALIN}Seçiminiz (1/2/3): {Renk.RESET}").strip()
            if secim == "1":
                yeni_sifre = sifre_guncelle()
                if yeni_sifre:
                    self.password = yeni_sifre
                    return True
            elif secim == "2":
                kimlik_bilgilerini_sil()
                self.username, self.password = kimlik_bilgilerini_al()
                return True
            elif secim in {"3", "q", "exit", "cikis"}:
                return False
            else:
                print(f"{Renk.KIRMIZI}[!] Lütfen 1, 2 veya 3 girin.{Renk.RESET}")

    def ders_listesini_al(self, sessiz_liste=False):
        if not sessiz_liste:
            print("Ders listesi alınıyor...")
        ders_maddeleri = self.driver.find_elements(By.CSS_SELECTOR, ".menuErisimAgaci > ul > li")
        hedef_dersler = []

        for madde in ders_maddeleri:
            try:
                kod = madde.find_element(By.XPATH, "./span").text.strip()
                link_el = madde.find_element(By.CSS_SELECTOR, "ul li a")
                link = link_el.get_attribute("href")
                if link:
                    hedef_dersler.append((kod, link))
                    if not sessiz_liste:
                        print(f"Listeye eklendi: {kod}")
            except Exception:
                continue

        if not sessiz_liste:
            print(f"Toplam {len(hedef_dersler)} ders bulundu.\n")
        return hedef_dersler

    # --- DOSYA VE WEB LİNK SENKRONİZASYONU ---
    def _link_bilgisi_al(self, url):
        filename = None
        is_weblink = False

        try:
            head_resp = self.session.head(url, allow_redirects=True, timeout=5)
            if head_resp.status_code >= 400:
                is_weblink = True
            else:
                content_type = head_resp.headers.get("content-type", "").lower()
                if "text/html" in content_type:
                    is_weblink = True
                else:
                    cd = head_resp.headers.get("content-disposition")
                    if cd:
                        fname = re.findall('filename="?([^"]+)"?', cd)
                        if fname:
                            try:
                                filename = fname[0].encode("iso-8859-1").decode("utf-8")
                            except Exception:
                                filename = fname[0]
        except Exception:
            is_weblink = True

        return is_weblink, filename

    def _weblink_kaydet(self, url, folder_path, varsayilan_isim, remote_date_str, indent_str):
        filename = temizle_dosya_ismi(varsayilan_isim) + ".url"
        full_path = os.path.join(folder_path, filename)
        rel_path_key = os.path.relpath(full_path, ANA_KLASOR)

        try:
            if not os.path.exists(full_path):
                durum = "YENİ"
                print(f"{indent_str}{Renk.YESIL}[🌐] YENİ WEB LİNK: {varsayilan_isim}{Renk.RESET}")
            elif self.metadata.get(rel_path_key) != remote_date_str:
                durum = "GÜNCEL"
                print(f"{indent_str}{Renk.SARI}[!] WEB LİNK GÜNCELLENDİ: {varsayilan_isim}{Renk.RESET}")
                self._arsivle(full_path, "Changed")
            else:
                print(f"{indent_str}{Renk.GRI}[.] Web Link Güncel: {varsayilan_isim} ({remote_date_str}){Renk.RESET}")
                return filename

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(f"[InternetShortcut]\nURL={url}\n")

            self.metadata[rel_path_key] = remote_date_str
            self._metadata_kaydet()
            self._ozete_ekle(durum, rel_path_key)
            return filename

        except Exception as e:
            print(f"{indent_str}{Renk.KIRMIZI}[HATA] Web link kaydedilemedi: {e}{Renk.RESET}")
            self.ozet["hata"].append(f"{folder_path}/{varsayilan_isim}: {e}")
            return None

    def dosya_senkronize_et(self, url, folder_path, varsayilan_isim, remote_date_str, indent_level):
        indent_str = "│   " * indent_level
        is_weblink, filename = self._link_bilgisi_al(url)

        if is_weblink:
            return self._weblink_kaydet(url, folder_path, varsayilan_isim, remote_date_str, indent_str)

        if not filename:
            filename = varsayilan_isim
            if "." not in filename:
                filename += ".pdf"

        filename = temizle_dosya_ismi(filename)
        full_path = os.path.join(folder_path, filename)
        rel_path_key = os.path.relpath(full_path, ANA_KLASOR)

        try:
            if not os.path.exists(full_path):
                durum = "YENİ"
                print(f"{indent_str}{Renk.YESIL}[+] İNDİRİLİYOR: {filename}{Renk.RESET}")
            else:
                local_stored_date = self.metadata.get(rel_path_key)
                if local_stored_date != remote_date_str:
                    durum = "GÜNCEL"
                    print(f"{indent_str}{Renk.SARI}[!] GÜNCELLEME: {filename}{Renk.RESET}")
                    print(f"{indent_str}    Eski: {local_stored_date} -> Yeni: {remote_date_str}")
                    self._arsivle(full_path, "Changed")
                else:
                    print(f"{indent_str}{Renk.GRI}[.] Güncel: {filename} ({remote_date_str}){Renk.RESET}")
                    return filename

            response = self.session.get(url, stream=True, timeout=20)
            if "text/html" in response.headers.get("content-type", "").lower():
                weblink_filename = temizle_dosya_ismi(varsayilan_isim) + ".url"
                weblink_full_path = os.path.join(folder_path, weblink_filename)
                with open(weblink_full_path, "w", encoding="utf-8") as f:
                    f.write(f"[InternetShortcut]\nURL={url}\n")
                print(f"{indent_str}{Renk.YESIL}[🌐] WEB LİNK OLARAK KAYDEDİLDİ: {varsayilan_isim}{Renk.RESET}")
                self.metadata[rel_path_key] = remote_date_str
                self._metadata_kaydet()
                self._ozete_ekle(durum, rel_path_key)
                return weblink_filename

            with open(full_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)

            self.metadata[rel_path_key] = remote_date_str
            self._metadata_kaydet()
            self._ozete_ekle(durum, rel_path_key)
            return filename

        except Exception as e:
            print(f"{indent_str}{Renk.KIRMIZI}[HATA] İndirme başarısız: {e}{Renk.RESET}")
            self.ozet["hata"].append(f"{folder_path}/{varsayilan_isim}: {e}")
            return None

    def silinenleri_kontrol_et(self, folder_path, server_files, indent_level):
        if not os.path.exists(folder_path):
            return
        indent_str = "│   " * indent_level

        local_files = [
            f for f in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, f)) and not f.startswith(".")
        ]

        for l_file in local_files:
            if l_file not in server_files:
                print(f"{indent_str}{Renk.KIRMIZI}[-] SİLİNMİŞ: {l_file}{Renk.RESET}")
                full_path = os.path.join(folder_path, l_file)
                rapor_yolu = os.path.relpath(full_path, ANA_KLASOR)

                if rapor_yolu in self.metadata:
                    del self.metadata[rapor_yolu]
                    self._metadata_kaydet()

                self._arsivle(full_path, "Deleted")
                self.ozet["silinen"].append(rapor_yolu)

    # --- MODÜL TARAYICILARI ---
    def klasor_tarama(self, local_path, indent_level=1):
        os.makedirs(local_path, exist_ok=True)
        indent_str = "│   " * indent_level

        try:
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.data"))
            )
        except Exception:
            self.silinenleri_kontrol_et(local_path, [], indent_level)
            return

        rows = self.driver.find_elements(By.CSS_SELECTOR, "table.data tr")
        items = []
        found_files = []

        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) < 2:
                continue

            try:
                img_src = cols[0].find_element(By.TAG_NAME, "img").get_attribute("src").lower()
                link_el = cols[0].find_element(By.TAG_NAME, "a")
                url = link_el.get_attribute("href")
                name = link_el.text.strip()

                date_text = "TarihYok"
                if len(cols) >= 3:
                    candidate = cols[-1].text.strip()
                    if not candidate and len(cols) > 2:
                        candidate = cols[-2].text.strip()
                    date_text = candidate

                items.append({
                    "type": "folder" if ("folder" in img_src or "dosya" in img_src) else "file",
                    "url": url,
                    "name": name,
                    "date": date_text
                })
            except Exception:
                continue

        for item in items:
            if item["type"] == "folder":
                print(f"{indent_str}{Renk.MAVI}📂 [{item['name']}]{Renk.RESET}")
                new_path = os.path.join(local_path, temizle_dosya_ismi(item["name"]))
                self.driver.get(item["url"])
                self.klasor_tarama(new_path, indent_level + 1)
                self.driver.back()
            else:
                saved_name = self.dosya_senkronize_et(
                    item["url"], local_path, item["name"], item["date"], indent_level
                )
                if saved_name:
                    found_files.append(saved_name)

        self.silinenleri_kontrol_et(local_path, found_files, indent_level)

    def _odev_aciklamasi_senkronize_et(self, odev, hw_folder, indent_level=2):
        """Ödev detay sayfasındaki teslim tarihlerini ve ödev açıklamasını .txt olarak senkronize eder."""
        indent_str = "│   " * indent_level
        ders_kodu = os.path.relpath(hw_folder, ANA_KLASOR).split(os.sep)[0]
        filename = f"{ders_kodu}_{temizle_dosya_ismi(odev['title'])[:30].rstrip(' .')}_Aciklama.txt"
        full_path = os.path.join(hw_folder, filename)
        rel_path_key = os.path.relpath(full_path, ANA_KLASOR)

        try:
            form2 = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.form2"))
            )

            teslim_baslangici = ""
            teslim_bitisi = ""

            for td in form2.find_elements(By.CSS_SELECTOR, "table td"):
                try:
                    baslik = td.find_element(By.CSS_SELECTOR, "span.title_field").text.strip().lower()
                    deger = td.find_element(By.CSS_SELECTOR, "span.data_field").text.strip()
                    if "başlang" in baslik or "baslang" in baslik:
                        teslim_baslangici = deger
                    elif "bitiş" in baslik or "bitis" in baslik:
                        teslim_bitisi = deger
                except Exception:
                    continue

            aciklama_text = ""
            try:
                aciklama_els = form2.find_elements(By.XPATH, "./span[contains(@class, 'data_field')]")
                if aciklama_els:
                    aciklama_text = aciklama_els[0].text.strip()
            except Exception:
                pass

            if not (teslim_baslangici or teslim_bitisi or aciklama_text):
                return None

            txt_content = f"Ödev             : {odev['title']}\n"
            if teslim_baslangici:
                txt_content += f"Teslim Başlangıcı: {teslim_baslangici}\n"
            if teslim_bitisi:
                txt_content += f"Teslim Bitişi    : {teslim_bitisi}\n"
            txt_content += f"Link             : {odev['url']}\n"
            txt_content += "=" * 60 + "\n\n"
            txt_content += (aciklama_text if aciklama_text else "(Açıklama girilmemiş)") + "\n"

            remote_hash = metin_hash_hesapla(txt_content)

            dosya_kaydedilmeli = False
            durum = ""

            if not os.path.exists(full_path):
                dosya_kaydedilmeli = True
                durum = "YENİ"
            else:
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        local_hash = metin_hash_hesapla(f.read())
                except Exception:
                    local_hash = None

                if local_hash != remote_hash:
                    print(f"{indent_str}{Renk.SARI}[!] ÖDEV AÇIKLAMASI GÜNCELLENDİ: {filename}{Renk.RESET}")
                    self._arsivle(full_path, "Changed")
                    dosya_kaydedilmeli = True
                    durum = "GÜNCEL"
                else:
                    print(f"{indent_str}{Renk.GRI}[.] Ödev Açıklaması Güncel: {filename}{Renk.RESET}")
                    if self.metadata.get(rel_path_key) != remote_hash:
                        self.metadata[rel_path_key] = remote_hash
                        self._metadata_kaydet()

            if dosya_kaydedilmeli:
                if durum == "YENİ":
                    print(f"{indent_str}{Renk.YESIL}[📝] YENİ ÖDEV AÇIKLAMASI: {filename}{Renk.RESET}")
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(txt_content)
                self.metadata[rel_path_key] = remote_hash
                self._metadata_kaydet()
                self._ozete_ekle(durum, rel_path_key)

            return filename

        except Exception as e:
            print(f"{indent_str}{Renk.KIRMIZI}[HATA] Ödev açıklaması kaydedilemedi ({filename}): {e}{Renk.RESET}")
            self.ozet["hata"].append(f"{hw_folder}/{filename}: {e}")
            return filename if os.path.exists(full_path) else None

    def odevleri_tara(self, odev_base_path):
        os.makedirs(odev_base_path, exist_ok=True)
        odevler_info = []

        try:
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table[id$='gvOdevListesi'] tr td")
            for td in rows:
                try:
                    title = td.find_element(By.TAG_NAME, "h2").text.strip()
                    link_url = next(
                        (a.get_attribute("href") for a in td.find_elements(By.TAG_NAME, "a")
                         if a.get_attribute("href") and "/Odev/" in a.get_attribute("href")),
                        None
                    )
                    if link_url:
                        odevler_info.append({"title": title, "url": link_url})
                except Exception:
                    continue
        except Exception:
            pass

        for odev in odevler_info:
            hw_folder = os.path.join(odev_base_path, temizle_dosya_ismi(odev["title"]))
            os.makedirs(hw_folder, exist_ok=True)
            print(f"│   {Renk.MAVI}📄 [{odev['title']}]{Renk.RESET}")

            self.driver.get(odev["url"])
            found_files = []

            # Ödev teslim tarihleri ve açıklaması .txt olarak senkronize edilir
            aciklama_dosyasi = self._odev_aciklamasi_senkronize_et(odev, hw_folder, indent_level=2)
            if aciklama_dosyasi:
                found_files.append(aciklama_dosyasi)

            # Ödeve ekli kaynak dosyalar senkronize edilir
            try:
                table = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table[id$='gvDosyalar']"))
                )
                for row in table.find_elements(By.CSS_SELECTOR, "tr"):
                    cols = row.find_elements(By.TAG_NAME, "td")
                    if len(cols) < 2:
                        continue
                    try:
                        link_el = cols[0].find_element(By.TAG_NAME, "a")
                        url = link_el.get_attribute("href")
                        name = link_el.text.strip()
                        date_text = cols[-1].text.strip() if len(cols) >= 3 else "TarihYok"

                        saved_name = self.dosya_senkronize_et(
                            url, hw_folder, name, date_text, indent_level=2
                        )
                        if saved_name:
                            found_files.append(saved_name)
                    except Exception:
                        continue
            except Exception:
                pass

            self.silinenleri_kontrol_et(hw_folder, found_files, indent_level=2)

    def duyurulari_tara(self, duyuru_base_path, indent_level=1):
        os.makedirs(duyuru_base_path, exist_ok=True)
        indent_str = "│   " * indent_level
        duyurular_info = []

        try:
            for div in self.driver.find_elements(By.CSS_SELECTOR, "div.duyuruGoruntule"):
                try:
                    a_el = div.find_element(By.CSS_SELECTOR, "h2 a")
                    title = a_el.text.strip()
                    url = a_el.get_attribute("href")
                    tarih_els = div.find_elements(By.CSS_SELECTOR, "div.tarih")
                    date_str = tarih_els[0].text.strip() if tarih_els else "TarihYok"

                    if url:
                        duyurular_info.append({"title": title, "url": url, "date": date_str})
                except Exception:
                    continue
        except Exception:
            pass

        found_files = []
        name_counts = {}

        for duyuru in duyurular_info:
            base_clean_name = temizle_dosya_ismi(duyuru["title"])
            name_counts[base_clean_name] = name_counts.get(base_clean_name, 0) + 1
            count = name_counts[base_clean_name]
            filename = f"{base_clean_name}.txt" if count == 1 else f"{base_clean_name}_({count}).txt"

            full_path = os.path.join(duyuru_base_path, filename)
            rel_path_key = os.path.relpath(full_path, ANA_KLASOR)
            remote_date_str = duyuru["date"]

            try:
                self.driver.get(duyuru["url"])
                detay_div = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.duyuruGoruntule"))
                )

                icerik_text = ""
                try:
                    icerik_text = detay_div.find_element(By.CSS_SELECTOR, "div.icerik").text.strip()
                except Exception:
                    pass

                yazar_text = ""
                try:
                    yazar_text = detay_div.find_element(By.CSS_SELECTOR, "span[id$='lbKullanici']").text.strip()
                except Exception:
                    pass

                try:
                    baslangic_text = detay_div.find_element(By.CSS_SELECTOR, "span[id$='lblBaslangic']").text.strip()
                    if baslangic_text:
                        remote_date_str = baslangic_text
                except Exception:
                    pass

                txt_content = (
                    f"Başlık : {duyuru['title']}\n"
                    f"Tarih  : {remote_date_str}\n"
                    + (f"Yazan  : {yazar_text}\n" if yazar_text else "")
                    + f"Link   : {duyuru['url']}\n"
                    + "=" * 60 + "\n\n"
                    + icerik_text + "\n"
                )
                remote_hash = metin_hash_hesapla(txt_content)

                dosya_kaydedilmeli = False
                durum = ""

                if not os.path.exists(full_path):
                    dosya_kaydedilmeli = True
                    durum = "YENİ"
                else:
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            local_hash = metin_hash_hesapla(f.read())
                    except Exception:
                        local_hash = None

                    if local_hash != remote_hash:
                        print(f"{indent_str}{Renk.SARI}[!] DUYURU İÇERİĞİ GÜNCELLENDİ: {filename}{Renk.RESET}")
                        self._arsivle(full_path, "Changed")
                        dosya_kaydedilmeli = True
                        durum = "GÜNCEL"
                    else:
                        print(f"{indent_str}{Renk.GRI}[.] Duyuru Güncel: {filename} ({remote_date_str}){Renk.RESET}")
                        if self.metadata.get(rel_path_key) != remote_hash:
                            self.metadata[rel_path_key] = remote_hash
                            self._metadata_kaydet()

                if dosya_kaydedilmeli:
                    if durum == "YENİ":
                        print(f"{indent_str}{Renk.YESIL}[📢] YENİ DUYURU: {filename}{Renk.RESET}")
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(txt_content)
                    self.metadata[rel_path_key] = remote_hash
                    self._metadata_kaydet()
                    self._ozete_ekle(durum, rel_path_key)

                found_files.append(filename)

            except Exception as e:
                print(f"{indent_str}{Renk.KIRMIZI}[HATA] Duyuru kontrol edilemedi/kaydedilemedi ({filename}): {e}{Renk.RESET}")
                self.ozet["hata"].append(f"{duyuru_base_path}/{filename}: {e}")
                if os.path.exists(full_path):
                    found_files.append(filename)

        self.silinenleri_kontrol_et(duyuru_base_path, found_files, indent_level=indent_level)

    # --- ANA AKIŞ VE RAPOR ---
    def dersi_senkronize_et(self, ders_adi, ders_link):
        safe_ders_adi = temizle_dosya_ismi(ders_adi)
        if safe_ders_adi not in self.taranan_dersler:
            self.taranan_dersler.append(safe_ders_adi)

        print(f"{Renk.MOR}════════════════════════════════════════════════════════════{Renk.RESET}")
        print(f"{Renk.KALIN}[{safe_ders_adi}]{Renk.RESET} Senkronize Ediliyor...")

        base_path = os.path.join(ANA_KLASOR, safe_ders_adi)
        moduller = ["/DersDosyalari", "/SinifDosyalari", "/Odevler", "/Duyurular"]

        for mod in moduller:
            self.driver.get(ders_link.rstrip("/") + mod)
            if "bulunamadı" in self.driver.title.lower():
                continue

            mod_adi = mod.replace("/", "")
            if mod == "/Odevler":
                print(f"{Renk.CYAN}{Renk.KALIN}📝 [Odevler]{Renk.RESET}")
                self.odevleri_tara(os.path.join(base_path, "Odevler"))
            elif mod == "/Duyurular":
                print(f"{Renk.CYAN}{Renk.KALIN}📢 [Duyurular]{Renk.RESET}")
                self.duyurulari_tara(os.path.join(base_path, "Duyurular"), indent_level=1)
            else:
                print(f"{Renk.CYAN}{Renk.KALIN}📁 [{mod_adi}]{Renk.RESET}")
                self.klasor_tarama(os.path.join(base_path, mod_adi), indent_level=1)

    def rapor_yazdir(self):
        print(f"\n\n{Renk.KALIN}████████████████████  SONUÇ RAPORU  ████████████████████{Renk.RESET}")

        if self.taranan_dersler:
            print(f"\n{Renk.CYAN}[i] KONTROL EDİLEN DERSLER ({len(self.taranan_dersler)}):{Renk.RESET}")
            for d in self.taranan_dersler:
                print(f"  📘 {d}")
        else:
            print(f"\n{Renk.GRI}[i] KONTROL EDİLEN DERSLER (0){Renk.RESET}")

        if not any(self.ozet.values()):
            print(f"\n{Renk.YESIL}✅ Her şey güncel!{Renk.RESET}")
        else:
            for key in ("yeni", "degisen", "silinen"):
                self.ozet[key].sort()

            if self.ozet["yeni"]:
                print(f"\n{Renk.YESIL}[+] YENİ EKLENEN DOSYALAR / LİNKLER ({len(self.ozet['yeni'])}):{Renk.RESET}")
                for f in self.ozet["yeni"]:
                    print(f"  📂 {f}")

            if self.ozet["degisen"]:
                print(f"\n{Renk.SARI}[!] TARİHİ / İÇERİĞİ DEĞİŞEN DOSYALAR ({len(self.ozet['degisen'])}):{Renk.RESET}")
                for f in self.ozet["degisen"]:
                    print(f"  📝 {f}")

            if self.ozet["silinen"]:
                print(f"\n{Renk.KIRMIZI}[-] SİLİNEN DOSYALAR / LİNKLER ({len(self.ozet['silinen'])}):{Renk.RESET}")
                for f in self.ozet["silinen"]:
                    print(f"  🗑️  {f}")

            if self.ozet["hata"]:
                print(f"\n{Renk.KIRMIZI}[X] HATALAR ({len(self.ozet['hata'])}):{Renk.RESET}")
                for f in self.ozet["hata"]:
                    print(f"  ❌ {f}")

        print(f"\n{Renk.KALIN}İşlem Tamamlandı.{Renk.RESET}")

    def calistir(self):
        try:
            self.tarayici_baslat()
            self.giris_yap()
            for ders_adi, ders_link in self.ders_listesini_al():
                self.dersi_senkronize_et(ders_adi, ders_link)
        finally:
            self.tarayici_kapat()

        self.rapor_yazdir()


if __name__ == "__main__":
    kullanici_adi, sifre = kimlik_bilgilerini_al()
    bot = NinovaSync(kullanici_adi, sifre, headless=IS_HEADLESS)
    bot.calistir()