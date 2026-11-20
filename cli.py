import argparse
import re

from ninova_sync import (
    CONFIG_FILE,
    IS_HEADLESS,
    NinovaSync,
    Renk,
    json_yukle,
    kimlik_bilgilerini_al,
    kimlik_bilgilerini_sil,
    sifre_guncelle,
)


def dersleri_yazdir(dersler):
    print(f"\n{Renk.KALIN}📚 Bulunan Dersler:{Renk.RESET}")
    for idx, (kod, _) in enumerate(dersler, start=1):
        print(f"  {Renk.CYAN}{idx}.{Renk.RESET} {Renk.KALIN}{kod}{Renk.RESET}")
    print()


def yardim_yazdir():
    print(f"\n{Renk.SARI}Komut / Seçim Örnekleri:{Renk.RESET}")
    print(f"  • {Renk.KALIN}hepsi{Renk.RESET} (veya {Renk.KALIN}a{Renk.RESET}, {Renk.KALIN}*{Renk.RESET}) → Tüm dersleri senkronize eder")
    print(f"  • {Renk.KALIN}1, 3{Renk.RESET} (veya {Renk.KALIN}1 3{Renk.RESET})    → Seçilen numaradaki dersleri senkronize eder")
    print(f"  • {Renk.KALIN}liste{Renk.RESET}           → Ders listesini tekrar gösterir")
    print(f"  • {Renk.KALIN}hesap{Renk.RESET}           → Aktif kullanıcı bilgilerini gösterir")
    print(f"  • {Renk.KALIN}sifre{Renk.RESET}           → Keyring'deki şifreyi günceller ve yeniden giriş yapar")
    print(f"  • {Renk.KALIN}hesap-sil{Renk.RESET}       → Keyring ve config kayıtlarını siler (isteğe bağlı yeni giriş)")
    print(f"  • {Renk.KALIN}q{Renk.RESET} (veya {Renk.KALIN}cikis{Renk.RESET}) → Tarayıcıyı kapatır ve özet raporu gösterir\n")


def secimleri_cozumle(komut, dersler):
    temiz = komut.strip()
    if not temiz:
        return []

    if temiz.lower() in {"hepsi", "all", "a", "*"}:
        return list(dersler)

    parcalar = [p.strip() for p in re.split(r"[,\s]+", temiz) if p.strip()]
    secilenler = []
    gorulen_linkler = set()

    for parca in parcalar:
        if parca.isdigit():
            no = int(parca)
            if 1 <= no <= len(dersler):
                kod, link = dersler[no - 1]
                if link not in gorulen_linkler:
                    secilenler.append((kod, link))
                    gorulen_linkler.add(link)
            else:
                print(f"{Renk.KIRMIZI}[!] Geçersiz ders numarası: {no}{Renk.RESET}")
        else:
            print(f"{Renk.KIRMIZI}[!] Sadece ders numarası veya 'hepsi' girebilirsin: {parca}{Renk.RESET}")

    return secilenler


def oturumu_yeniden_baslat(bot):
    """Şifre veya kullanıcı değiştiğinde tarayıcıyı yeni kimlik bilgileriyle yeniden başlatır."""
    bot.tarayici_kapat()
    kullanici_adi, sifre = kimlik_bilgilerini_al()
    bot.username = kullanici_adi
    bot.password = sifre
    bot.tarayici_baslat()
    bot.giris_yap()
    dersler = bot.ders_listesini_al(sessiz_liste=True)
    dersleri_yazdir(dersler)
    return dersler


def etkilesimli_dongu(bot):
    dersler = bot.ders_listesini_al(sessiz_liste=True)
    if not dersler:
        print(f"{Renk.KIRMIZI}[!] Hiç ders bulunamadı.{Renk.RESET}")
        return

    dersleri_yazdir(dersler)
    yardim_yazdir()

    while True:
        try:
            cevap = input(f"{Renk.MAVI}{Renk.KALIN}ninova > {Renk.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if not cevap:
            continue

        alt = cevap.lower()
        if alt in {"q", "quit", "exit", "cikis", "çıkış"}:
            break
        if alt in {"liste", "ls", "list"}:
            dersleri_yazdir(dersler)
            continue
        if alt in {"yardim", "yardım", "help", "?"}:
            yardim_yazdir()
            continue
        if alt in {"hesap", "whoami"}:
            kayitli = json_yukle(CONFIG_FILE).get("username", "Yok")
            print(f"{Renk.CYAN}[i] Aktif kullanıcı: {Renk.KALIN}{bot.username}{Renk.RESET} (config.json: {kayitli})")
            continue
        if alt in {"sifre", "şifre", "sifre-degistir", "şifre-değiştir"}:
            yeni_sifre = sifre_guncelle()
            if yeni_sifre:
                dersler = oturumu_yeniden_baslat(bot)
            continue
        if alt in {"hesap-sil", "sil", "reset"}:
            onay = input(f"{Renk.SARI}[?] Keyring şifresi ve config.json silinsin mi? (e/h): {Renk.RESET}").strip().lower()
            if onay in {"e", "evet", "y", "yes"}:
                kimlik_bilgilerini_sil()
                yeni_giris = input(f"{Renk.MAVI}[?] Şimdi yeni kullanıcı bilgileri girilsin mi? (e/h): {Renk.RESET}").strip().lower()
                if yeni_giris in {"e", "evet", "y", "yes"}:
                    dersler = oturumu_yeniden_baslat(bot)
                else:
                    print(f"{Renk.GRI}[i] Oturum kapatılıyor...{Renk.RESET}")
                    break
            else:
                print(f"{Renk.GRI}[i] Silme işlemi iptal edildi.{Renk.RESET}")
            continue

        secilen_dersler = secimleri_cozumle(cevap, dersler)
        if not secilen_dersler:
            continue

        for ders_adi, ders_link in secilen_dersler:
            bot.dersi_senkronize_et(ders_adi, ders_link)

        print(f"\n{Renk.YESIL}✅ Seçilen derslerin senkronizasyonu bitti. Yeni seçim yapabilir veya 'q' ile çıkabilirsin.{Renk.RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="İTÜ Ninova Etkileşimli Senkronizasyon CLI")
    parser.add_argument("--headless", action="store_true", default=IS_HEADLESS, help="Tarayıcıyı görünmez (headless) başlatır")
    parser.add_argument("--hesap-sifirla", action="store_true", help="Mevcut Keyring ve config kayıtlarını silip yeniden giriş ister")
    args = parser.parse_args()

    if args.hesap_sifirla:
        kimlik_bilgilerini_sil()

    kullanici_adi, sifre = kimlik_bilgilerini_al()
    bot = NinovaSync(kullanici_adi, sifre, headless=args.headless)

    try:
        bot.tarayici_baslat()
        bot.giris_yap()
        etkilesimli_dongu(bot)
    finally:
        bot.tarayici_kapat()
        bot.rapor_yazdir()


if __name__ == "__main__":
    main()