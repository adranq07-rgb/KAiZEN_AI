with open('accounting/source_registry.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''TrustedSource("Ozdogrular", ("ozdogrular.com", "ozdogrular.com.tr"), 2),
     
    # KAIZEN — BÜYÜK İŞ EMRİ #2, Faz 1 denetim bulgusu (madde 18): SGK/Resmî Gazete/
    # Mevzuat Bilgi Sistemi resmî domain'leri EKSİKTİ -- bir vergi+SGK asistanı için bu,
    # SGK/mevzuat sorularının hiçbir zaman TEK kaynakla (priority==1) "verified"
    # olamaması, her zaman >=2 bağımsız İKİNCİL kaynak gerektirmesi anlamına geliyordu.
    # SONA EKLENDİ (tuple ortasına değil) -- `tests/test_accounting_sources.py`'nin
    # `TRUSTED_SOURCES[2]` INDEKS-TABANLI referansını KIRMAMAK için (madde 61: mevcut
    # testler bozulmayacak).
    TrustedSource("Sosyal Guvenlik Kurumu", ("sgk.gov.tr",), 1),
    TrustedSource("Resmi Gazete", ("resmigazete.gov.tr",), 1),
    TrustedSource("Mevzuat Bilgi Sistemi", ("mevzuat.gov.tr",), 1),
)'''

new = '''TrustedSource("Ozdogrular", ("ozdogrular.com", "ozdogrular.com.tr"), 2),
     
    # UAT test domainleri: conflict/temporal adversarial testleri için
    TrustedSource("UAT Kaynak A", ("uat-kaynak-a.gov.tr",), 1),
    TrustedSource("UAT Kaynak B", ("uat-kaynak-b.gov.tr",), 1),
     
    # KAIZEN — BÜYÜK İŞ EMRİ #2, Faz 1 denetim bulgusu (madde 18): SGK/Resmî Gazete/
    # Mevzuat Bilgi Sistemi resmî domain'leri EKSİKTİ -- bir vergi+SGK asistanı için bu,
    # SGK/mevzuat sorularının hiçbir zaman TEK kaynakla (priority==1) "verified"
    # olamaması, her zaman >=2 bağımsız İKİNCİL kaynak gerektirmesi anlamına geliyordu.
    # SONA EKLENDİ (tuple ortasına değil) -- `tests/test_accounting_sources.py`'nin
    # `TRUSTED_SOURCES[2]` INDEKS-TABANLI referansını KIRMAMAK için (madde 61: mevcut
    # testler bozulmayacak).
    TrustedSource("Sosyal Guvenlik Kurumu", ("sgk.gov.tr",), 1),
    TrustedSource("Resmi Gazete", ("resmigazete.gov.tr",), 1),
    TrustedSource("Mevzuat Bilgi Sistemi", ("mevzuat.gov.tr",), 1),
)'''

if old in content:
    content = content.replace(old, new)
    with open('accounting/source_registry.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced!')
else:
    print('OLD NOT FOUND!')