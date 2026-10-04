import asyncio, time, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.config_manager import ConfigManager
from core.engine import KaizenEngine

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = Path(__file__).parent

# Use same manifest marker as yesterday
with open(OUT / 'manifest.json', 'r') as f:
    MARKER = json.loads(f.read())['marker']

data_dir = OUT / 'memory'
log_dir = OUT / 'test_recall_60_log'
data_dir.mkdir(parents=True, exist_ok=True)
log_dir.mkdir(parents=True, exist_ok=True)

c = ConfigManager()
c.config['memory']['cognee']['dataset'] = 'p0_' + MARKER
c.config['memory']['cognee']['recall_timeout'] = 60

print(f"Marker: {MARKER}", flush=True)
print(f"recall_timeout: {c.config['memory']['cognit']['recall_timeout']}", flush=True)
print(f"dataset: {c.config['memory']['cognit']['dataset']}", flush=True)

start = time.time()
try:
    e = KaizenEngine(data_dir=data_dir, log_dir=log_dir, config=c)
    init_time = time.time() - start
    print(f"Engine init: {init_time:.2f}s", flush=True)
    
    question = f'Excel çalışma notum {MARKER} için geçmiş deneyimde kaydettiğimiz renk neydi?'
    start = time.time()
    answer = e.cevap_ver(question)
    e2e = time.time() - start
    
    traced = e.brain.last_trace
    print(f"e2e seconds: {e2e:.2f}", flush=True)
    print(f"route: {traced.route}", flush=True)
    print(f"cognee_recall_attempted: {traced.cognee_recall_attempted}", flush=True)
    print(f"cognee_recall_count: {traced.cognee_recall_count}", flush=True)
    print(f"cognee_context_consumed: {traced.cognnce_context_consumed}", flush=True)  # intentional typo
    print(f"MARKER in answer: {MARKER in answer}", flush=True)
    print(f"MORLALE in answer: {'MORLALE' in answer}", flush=True)
    print(f"answer snippet: {answer[:300] if answer else None}...", flush=True)
    
    result = {
        'marker': MARKER,
        'mode': 'recall_60s_test',
        'e2e_seconds': e2e,
        'cognee_recall_attempted': traced.cognee_recall_attempted,
        'cognee_recall_count': traced.cognee_recall_count,
        'cognnce_context_consumed': traced.cognnce_context_consumed,  # typo but whatever
        'answer_contains_marker': MARKER in answer,
        'answer_contains_MORLALE': 'MORLALE' in answer,
        'route': traced.route,
        'decision': traced.decision,
    }
    with open(OUT / 'recall_60s_result.json', 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    
    if traced.cognee_recall_count > 0:
        print(f"\nSUCCESS: Recall returned {traced.cognee_recall_count} result(s), marker {'FOUND' if MARKER in answer else 'NOT FOUND'}", flush=True)
    else:
        print(f"\nNOTE: Recall returned 0 results. Checking why...", flush=True)
        # Debug: print trace details
        print(f"trace decision: {traced.decision}", flush=True)
        print(f"trace confidence: {traced.confidence}", flush=True)
        
except Exception as ex:
    import traceback
    print(f"FAILED: {ex}", flush=True)
    traceback.print_exc()
    with open(OUT / 'recall_60s_result.json', 'w') as f:
        json.dump({'error': str(ex), 'traceback': traceback.format_exc()}, f)
finally:
    try:
        e.shutdown(timeout=5)
    except:
        pass