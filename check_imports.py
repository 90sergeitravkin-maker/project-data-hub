# check_imports.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

modules = [
    # Backend
    "src.back.app_monitor.api",
    "src.back.app_users.api",
    "src.back.app_mail.api",
    "src.back.app_data_registry.api",
    "src.back.app_link.api",
    "src.back.app_kafka.api",
    # Frontend
    "src.front.web_monitor.api",
    "src.front.web_lk.api",
    "src.front.web_ecomru.api",
]

for mod in modules:
    try:
        __import__(mod)
        print(f"✅ {mod}")
    except Exception as e:
        print(f"❌ {mod}")
        print(f"   → {type(e).__name__}: {e}")
        # Показать цепочку импортов
        import traceback
        traceback.print_exc()
        print("-" * 60)