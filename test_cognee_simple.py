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

from cognee import recall, SearchType

DATASET = 'p0_KZP03ebc5b77b630'

async def test():
    print('=== Test recall ===', flush=True)
    start = time.time()
    responses = await recall(
        'KZP03ebc5b77b630',
        query_type=SearchType.CHUNKS,
        datasets=[DATASET],
        top_k=10
    )
    elapsed = time.time() - start
    print(f'Elapsed: {elapsed:.2f}s', flush=True)
    print(f'Results: {len(responses)}', flush=True)
    for r in responses[:5]:
        print(f'  text={getattr(r,"text","N/A")[:80]}...', flush=True)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
result = loop.run_until_complete(test())
loop.close()