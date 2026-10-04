import json

with open('night_shift_config.json', 'r') as f:
    config = json.load(f)

pool = config['model_pool']

print('=== MODEL POOL STRUCTURE ===')
print(f'Verified models: {len(pool["verified"])}')
for m in pool['verified']:
    print(f'  - {m["model_id"]} (provider: {m["provider"]}, priority: {m["priority"]}, enabled: {m["enabled"]})')

print(f'\nCandidate models: {len(pool["candidates"])}')
for m in pool['candidates']:
    print(f'  - {m["model_id"]} (provider: {m["provider"]}, priority: {m["priority"]}, enabled: {m["enabled"]})')

print(f'\nProvider domains:')
for p, d in pool['provider_domains'].items():
    print(f'  - {p}: max_failures={d["max_consecutive_failures"]}, cooldown_minutes={d["cooldown_minutes"]}')

print(f'\nFailover reasons (infrastructure): {len(config["model_pool"]["failover_reasons"]["infrastructure"])}')
print(f'Failover reasons (non-failover): {len(config["model_pool"]["failover_reasons"]["non_failover"])}')

print('\n=== VERIFIED vs CANDIDATE STATUS ===')
verified_ids = {m['model_id'] for m in pool['verified']}
candidate_ids = {m['model_id'] for m in pool['candidates']}
print(f'Verified IDs: {verified_ids}')
print(f'Candidate IDs: {candidate_ids}')
print(f'Overlap: {verified_ids & candidate_ids}')
print(f'Total unique: {len(verified_ids | candidate_ids)}')