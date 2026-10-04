with open('accounting/source_registry.py', 'rb') as f:
    content = f.read()

old = b'TrustedSource("Ozdogrular", ("ozdogrular.com", "ozdogrular.com.tr"), 2),\n    \n    # KAIZEN \xc2\xae B\xc2\xafY\xc2\xafK \xc2\xaf\xc2\xaf EMR\xc2\xae #2, Faz 1 denetim bulgusu (madde 18): SGK/Resm\xc2\xaf Gazete/\n    # Mevzuat Bilgi Sistemi resm\xc2\xaf domain\'leri EKS\xc2\xafKT\xc2\xaf -- bir vergi+SGK asistan\u0131 i\u00e7in bu,\n    # SGK/mevzuat sorular\u0131n\u0131n hi\u00e7bir zaman TEK kaynakla (priority==1) "verified"\n    # olamamas\u0131, her zaman >=2 ba\u011f\u0131ms\u0131z \u0130K\u0130NC\u0130L kaynak gerektirmesi anlam\u0131na geliyordu.\n    # SONA EKLEND\xc2\xaf (tuple ortas\u0131na de\u011fil) -- `tests/test_accounting_sources.py`\xe2\x80\x99nin\n    # `TRUSTED_SOURCES[2]` INDEKS-TABANLI referans\u0131n\u0131 KIRMAMAK i\u00e7in (madde 61: mevcut\n    # testler bozulmayacak).\n    TrustedSource("Sosyal Guvenlik Kurumu", ("sgk.gov.tr",), 1),\n    TrustedSource("Resmi Gazete", ("resmigazete.gov.tr",), 1),\n    TrustedSource("Mevzuat Bilgi Sistemi", ("mevzuat.gov.tr",), 1),\n)'

new = b'TrustedSource("Ozdogrular", ("ozdogrular.com", "ozdogrular.com.tr"), 2),\n      \n    # UAT test domainleri: conflict/temporal adversarial testleri i\u00e7in\n    TrustedSource("UAT Kaynak A", ("uat-kaynak-a.gov.tr",), 1),\n    TrustedSource("UAT Kaynak B", ("uat-kaynak-b.gov.tr",), 1),\n      \n    # KAIZEN \xc2\xae B\xc2\xafY\xc2\xafK \xc2\xaf\xc2\xaf EMR\xc2\xae #2, Faz 1 denetim bulgusu (madde 18): SGK/Resm\xc2\xaf Gazete/\n    # Mevzuat Bilgi Sistemi resm\xc2\xaf domain\xe2\x80\x99leri EKS\xc2\xafKT\xc2\xaf -- bir vergi+SGK asistan\u0131 i\u00e7in bu,\n    # SGK/mevzuat sorular\u0131n\u0131n hi\u00e7bir zaman TEK kaynakla (priority==1) "verified"\n    # olamamas\u0131, her zaman >=2 ba\u011f\u0131ms\u0131z \u0130K\u0130NC\u0130L kaynak gerektirmesi anlam\u0131na geliyordu.\n    # SONA EKLEND\xc2\xaf (tuple ortas\u0131na de\u011fil) -- `tests/test_accounting_sources.py`\xe2\x80\x99nin\n    # `TRUSTED_SOURCES[2]` INDEKS-TABANLI referans\u0131n\u0131 KIRMAMAK i\u00e7in (madde 61: mevcut\n    # testler bozulmayacak).\n    TrustedSource("Sosyal Guvenlik Kurumu", ("sgk.gov.tr",), 1),\n    TrustedSource("Resmi Gazete", ("resmigazete.gov.tr",), 1),\n    TrustedSource("Mevzuat Bilgi Sistemi", ("mevzuat.gov.tr",), 1),\n)'

with open('accounting/source_registry.py', 'rb') as f:
    content = f.read()

if old in content:
    content = content.replace(old, new)
    with open('accounting/source_registry.py', 'wb') as f:
        f.write(content)
    print('Replaced!')
else:
    print('OLD NOT FOUND!')
    idx = content.find(b'Ozdogrular')
    if idx >= 0:
        print('Found at', idx)
    else:
        print('Not found')