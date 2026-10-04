from accounting.source_registry import trusted_source_for_url, search_domains

print('Trusted domains:')
for d in search_domains():
    print(' ', d)

uat_domains = ['uat-kaynak-a.gov.tr', 'uat-kaynak-b.gov.tr']
print()
print('UAT domains test:')
for domain in uat_domains:
    result = trusted_source_for_url(f'https://{domain}')
    print(f'  {domain}: trusted={result is not None}')