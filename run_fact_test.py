#!/usr/bin/env python
"""Test script to verify facts.py source count behavior"""

import json
from pathlib import Path
from uuid import uuid4
from accounting.site_store import SiteStore
from accounting.facts import FactRegistry, FactExtractor, load_topics

# Use the exact content from test_facts.py
PAGE_A = ('Fatura dzenleme sirini 2026 yilinde 11.111 TL olarak uygulanacaktir. '
          'Kurumlar vergisi orani %23 olarak belirlenmistir. 2026 yili icin SGK prim tavan 500.000 TL\'dir.')

workspace = Path('/tmp/test_workspace')
workspace.mkdir(parents=True, exist_ok=True)
db_path = workspace / f'facts_{uuid4().hex}.sqlite3'

store = SiteStore(db_path)
extractor = FactExtractor(load_topics(), current_year=2026)

# 3 sources for verified
store.upsert_page(url='https://www.muhasebetr.com/a', source_name='Muhasebe TR', title='A', content=PAGE_A, effective_year=2026)
store.upsert_page(url='https://www.alomaliye.com/makaleler/b', source_name='Alomaliye', title='B', content=PAGE_A, effective_year=2026)
store.upsert_page(url='https://www.vergiport.com/c', source_name='Vergiport', title='C', content=PAGE_A, effective_year=2026)

registry = FactRegistry(db_path, load_topics())
summary = registry.rebuild(store, min_year=2025, extractor=extractor)

print('Summary:', summary)

# Check the actual status
rows = registry.rows('fatura_duzenleme_siniri')
for r in rows:
    sources = json.loads(r['sources_json'])
    print('Year:', r['year'], 'Status:', r['status'], 'Value:', r['value'])
    print('Sources count:', len(sources))

db_path.unlink(missing_ok=True)