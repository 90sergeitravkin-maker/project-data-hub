import pyarrow.parquet as pq

try:
    table = pq.read_table("C:/bank/opt/data/external_data_raw/WEB-CUSTOMS_CHN-WORLD_TRADE-1/2026-03-11/2020/17273583359ce357dc46e92b4950ee57a3b83cdec4b141853568257787775277_7_197.parquet")
    print("OK, rows:", table.num_rows)
except Exception as e:
    print("Ошибка:", e)