with open('accounting/source_registry.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = 'TrustedSource("Ozdogrular", ("ozdogrular.com", "ozdogrular.com.tr"), 2),\n    \n    # KAIZEN � B�Y�K �� EMR� #2, Faz 1 denetim bulgusu (madde 18): SGK/Resm� Gazete/\n    # Mevzuat Bilgi Sistemi resm� domain\'leri EKS�KT� -- bir vergi+SGK asistan� i�in bu,\n    # SGK/mevzuat sorular�n�n hi�bir zaman TEK kaynakla (priority==1) "verified"\n    # olamamas�, her zaman >=2 ba��ms�z �K�NC�L kaynak gerektirmesi anlam�na geliyordu.\n    # SONA EKLEND� (tuple ortas�na de�il) -- `tests/test_accounting_sources.py`\'nin\n    # `TRUSTED_SOURCES[2]` INDEKS-TABANLI referans�n� KIRMAMAK i�in (madde 61: mevcut\n    # testler bozulmayacak).\n    TrustedSource("Sosyal Guvenlik Kurumu", ("sgk.gov.tr",), 1),\n    TrustedSource("Resmi Gazete", ("resmigazete.gov.tr",), 1),\n    TrustedSource("Mevzuat Bilgi Sistemi", ("mevzuat.gov.tr",), 1),\n)'

new = 'TrustedSource("Ozdogrular", ("ozdogrular.com", "ozdogrular.com.tr"), 2),\n      \n    # UAT test domainleri: conflict/temporal adversarial testleri i�in\n    TrustedSource("UAT Kaynak A", ("uat-kaynak-a.gov.tr",), 1),\n    TrustedSource("UAT Kaynak B", ("uat-kaynak-b.gov.tr",), 1),\n      \n    # KAIZEN � B�Y�K �� EMR� #2, Faz 1 denetim bulgusu (madde 18): SGK/Resm� Gazete/\n    # Mevzuat Bilgi Sistemi resm� domain\'leri EKS�KT� -- bir vergi+SGK asistan� i�in bu,\n    # SGK/mevzuat sorular�n�n hi�bir zaman TEK kaynakla (priority==1) "verified"\n    # olamamas�, her zaman >=2 ba��ms�z �K�NC�L kaynak gerektirmesi anlam�na geliyordu.\n    # SONA EKLEND� (tuple ortas�na de�il) -- `tests/test_accounting_sources.py`\'nin\n    # `TRUSTED_SOURCES[2]` INDEKS-TABANLI referans�n� KIRMAMAK i�in (madde 61: mevcut\n    # testler bozulmayacak).\n    TrustedSource("Sosyal Guvenlik Kurumu", ("sgk.gov.tr",), 1),\n    TrustedSource("Resmi Gazete", ("resmigazete.gov.tr",), 1),\n    TrustedSource("Mevzuat Bilgi Sistemi", ("mevzuat.gov.tr",), 1),\n)'

if old in content:
    content = content.replace(old, new)
    with open('accounting/source_registry.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced!')
else:
    print('OLD NOT FOUND!')
    idx = content.find('Ozdogrular')
    if idx >= 0:
        print('Found at', idx)
    else:
        print('Not found')