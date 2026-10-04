from accounting.facts import _domain_from_url, _count_unique_domains
from accounting.source_registry import trusted_source_for_url

domain1 = _domain_from_url('https://www.muhasebetr.com/guncelmevzuat/')
domain2 = _domain_from_url('https://musavirlerkulubu.com.tr/makale/')

print('Domain 1:', domain1)
print('Domain 2:', domain2)

print()
print('Checking via trusted_source_for_url:')
source1 = trusted_source_for_url('https://www.muhasebetr.com/guncelmevzuat/')
source2 = trusted_source_for_url('https://musavirlerkulubu.com.tr/makale/')
print(f'  Source 1: {source1.name if source1 else None}')
print(f'  Source 2: {source2.name if source2 else None}')