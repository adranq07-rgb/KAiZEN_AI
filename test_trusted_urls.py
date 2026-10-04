from accounting.source_registry import trusted_source_for_url

urls = [
    'https://www.muhasebetr.com/a',
    'https://www.alomaliye.com/makaleler/b',
    'https://www.vergiport.com/c',
]

for url in urls:
    source = trusted_source_for_url(url)
    print(url, ':', source.name if source else 'None', ', priority=', source.priority if source else None)