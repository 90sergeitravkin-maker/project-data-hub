import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent  / ".env"

load_dotenv(dotenv_path=env_path)


sssss = os.getenv("APP_DATA_REGISTRY_DB", "0.0.0.0")
print(sssss)


