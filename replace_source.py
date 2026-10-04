with open('accounting/source_registry.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Replace lines 42-54 (0-indexed: 42-53)
# Original lines 42-54 (0-indexed 42-53):
# Line 42: '    TrustedSource("Ozdogrular", ("ozdogrular.com", "ozdogrular.com.tr"), 2),\n'
# Line 43: '    \n'
# Line 44: '    # KAIZEN ...'
# ...
# Line 53: '    TrustedSource("Mevzuat Bilgi Sistemi", ("mevzuat.gov.tr",), 1),\n'
# Line 54: ')\n'

new_lines = [
    '    TrustedSource("Ozdogrular", ("ozdogrular.com", "ozdogrular.com.tr"), 2),\n',
    '    \n',
    '    # UAT test domainleri: conflict/temporal adversarial testleri için\n',
    '    TrustedSource("UAT Kaynak A", ("uat-kaynak-a.gov.tr",), 1),\n',
    '    TrustedSource("UAT Kaynak B", ("uat-kaynak-b.gov.tr",), 1),\n',
    '    \n',
    '    # KAIZEN — BÜYÜK İŞ EMRİ #2, Faz 1 denetim bulgusu (madde 18): SGK/Resmî Gazete/\n',
    '    # Mevzuat Bilgi Sistemi resmî domain\'leri EKSİKTİ -- bir vergi+SGK asistanı için bu,\n',
    '    # SGK/mevzuat sorularının hiçbir zaman TEK kaynakla (priority==1) "verified"\n',
    '    # olamaması, her zaman >=2 bağımsız İKİNCİL kaynak gerektirmesi anlamına geliyordu.\n',
    '    # SONA EKLENDİ (tuple ortasına değil) -- `tests/test_accounting_sources.py`\'nin\n',
    '    # `TRUSTED_SOURCES[2]` INDEKS-TABANLI referansını KIRMAMAK için (madde 61: mevcut\n',
    '    # testler bozulmayacak).\n',
    '    TrustedSource("Sosyal Guvenlik Kurumu", ("sgk.gov.tr",), 1),\n',
    '    TrustedSource("Resmi Gazete", ("resmigazete.gov.tr",), 1),\n',
    '    TrustedSource("Mevzuat Bilgi Sistemi", ("mevzuat.gov.tr",), 1),\n',
    ')\n'
]

# Replace lines 42-54 (0-indexed 42-53) with new_lines
# lines[42:54] should be replaced
new_content = lines[:42] + new_lines + lines[54:]

with open('accounting/source_registry.py', 'w', encoding='utf-8') as f:
    f.writelines(new_content)

print('Done!')