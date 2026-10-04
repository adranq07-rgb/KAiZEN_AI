import asyncio, os, sys, time, json
os.environ['COGNEE_DATA_ROOT_DIRECTORY'] = r'C:\Users\ANL\Desktop\KAZEN_AI\artifacts\kazen1_p0_20260928\memory\cognee\data'
os.environ['COGNEE_LOGS_DIR'] = r'C:\Users\ANL\Desktop\KAZEN_AI\artifacts\kazen1_p0_20260928\memory\cognee\logs'
os.environ['LLM_PROVIDER'] = 'ollama'
os.environ['LLM_MODEL'] = 'llama3.2:3b'
os.environ['LLM_ENDPOINT'] = 'http://localhost:11434'
os.environ['LLM_API_KEY'] = 'ollama'
os.environ['LLM_TEMPERATURE'] = '0.0'
os.environ['EMBEDDING_PROVIDER'] = 'ollama'
os.environ['EMBEDDING_MODEL'] = 'bge-m3'
os.environ['EMBEDDING_ENDPOINT'] = 'http://localhost:11434/api/embed'

from cognee.api import remember, recall
from cognee.tools.search import SearchType

print('Testing Cognee recall directly...', flush=True)
start = time.time()
try:
    result = asyncio.run(recall('KZP03ebc5b77b630', query_type=SearchType.CHUNKS, datasets=['p0_KZP03ebc5b77b630'], top_k=10))
    elapsed = time.time() - start
    print(f'Time: {elapsed:.2f}s', flush=True)
    print(f'Result type: {type(result)}', flush=True)
    if isinstance(result, list):
        print(f'Result count: {len(result)}', flush=True)
        for r in result[:3]:
            print(f'  - {r}', flush=True)
    else:
        print(f'Result: {result}', flush=True)
except Exception as e:
    import traceback
    print(f'Error: {e}', flush=True)
    traceback.print_exc()