import sys
sys.path.insert(0, r'C:\Users\ANL\Desktop\KAZEN_AI')

from night_shift_supervisor import load_config, select_model_from_pool, now_ts, update_model_status

config = load_config()
print("Config loaded successfully")

# Test model selection
selected = select_model_from_pool(config, failed_model_id='opencode/longcat-2.5-preview-free')
print(f"Selected model after opencode failure: {selected['model_id'] if selected else None}")

# Test update_model_status
update_model_status(config, 'opencode/longcat-2.5-preview-free', {
    'consecutive_failures': 3,
    'cooldown_until': now_ts() + 3600,
    'last_result': 'simulated_infra_error:429'
})
print("Model status updated")

# Test selection after update
selected2 = select_model_from_pool(config, failed_model_id='opencode/longcat-2.5-preview-free')
print(f"Selected model after failure with cooldown: {selected2['model_id'] if selected2 else None}")