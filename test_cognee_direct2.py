import asyncio, os, sys, time, json, traceback
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

from cognee.api.v1 import remember, recall, forget
from cognee.tools.search import SearchType

DATASET = 'p0_KZP03ebc5b77b630'

async def test():
    print('=== TEST 1: Verify write endpoint exists ===', flush=True)
    result = await remember(
        'TEST MESSAGE ' + 'KZP03ebc5b77b630',
        dataset_name=DATASET,
        self_improvement=False,
        raise_on_error=False
    )
    print(f'memorize result: {result}', flush=True)
    print(f'status: {result.status}, error: {result.error}', flush=True)
    
    print('\n=== TEST 2: Recall via cognee.recall ===', flush=True)
    start = time.time()
    try:
        responses = await recall(
            'KZP03ebc5b77b630',
            query_type=SearchType.CHUNKS,
            datasets=[DATASET],
            top_k=10
        )
        elapsed = time.time() - start
        print(f'Elapsed: {elapsed:.2f}s', flush=True)
        print(f'Results count: {len(responses)}', flush=True)
        for i, r in enumerate(responses[:5]):
            text = getattr(r, 'text', '')[:100]
            print(f'  [{i}] {text}...', flush=True)
    except Exception as e:
        print(f'Error: {e}', flush=True)
        traceback.print_exc()

asyncio.run(test())