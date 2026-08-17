from src.back.app_datasets.services import DataSetsVerifiedServices
from src.back.app_ecomru.config import get_split_columns

r = get_split_columns("API-COMTRADE-WORLD_TRADE-1")
print(r)
