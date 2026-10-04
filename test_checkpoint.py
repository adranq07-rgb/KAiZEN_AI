import sys
sys.path.insert(0, r'C:\Users\ANL\Desktop\KAZEN_AI')

from night_shift_supervisor import load_config, save_checkpoint, load_checkpoint, now_ts, select_model_from_pool

config = load_config()

# Test checkpoint save and load
checkpoint_state = {
    "task_id": 12345,
    "task_text": "Test task",
    "session_id": "test_session_001",
    "start_time": now_ts(),
    "attempted_models": ["opencode/longcat-2.5-preview-free"],
    "provider_cooldowns": {},
    "completed_milestones": [],
    "latest_test_command": "Test command",
    "latest_test_result": "test result",
    "git_diff_summary": None,
    "failure_history": [],
    "last_heartbeat": now_ts(),
    "final_status": "running"
}

# Save checkpoint
save_checkpoint(checkpoint_state)
print("Checkpoint saved")

# Load checkpoint
loaded = load_checkpoint()
print(f"Checkpoint loaded: {loaded.get('session_id')} - {loaded.get('final_status')}")

# Verify keys
required_keys = ["task_id", "task_text", "session_id", "start_time", "attempted_models"]
all_ok = True
for key in required_keys:
    if key in loaded:
        print(f"  OK {key}: {loaded[key]}")
    else:
        print(f"  MISSING {key}")
        all_ok = False

if all_ok:
    print("\nAll checkpoint tests passed!")