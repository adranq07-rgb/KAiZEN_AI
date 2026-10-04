import sys
sys.path.insert(0, r'C:\Users\ANL\Desktop\KAZEN_AI')
from night_shift_supervisor import run_opencode

result = run_opencode('opencode/longcat-2.5-preview-free', 'Test task for UAT', format_json=True)
print(f"Result type: {type(result)}")
if result is not None:
    print(f"Returncode: {result.returncode}")
    print(f"Stdout length: {len(result.stdout) if result.stdout else 0}")
    print(f"Stderr length: {len(result.stderr) if result.stderr else 0}")
    print(f"Stdout first 200: {result.stdout[:200] if result.stdout else 'None'}")
else:
    print("Result is None")