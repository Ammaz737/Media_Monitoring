import sqlite3
from pathlib import Path

db = Path("data/news_monitor.db")
conn = sqlite3.connect(db)
c = conn.cursor()
cols = [r[1] for r in c.execute("PRAGMA table_info(text_extractions)")]
print("has_ocr_engine", "ocr_engine" in cols)
if "ocr_engine" in cols:
    print("by_engine", list(c.execute(
        "SELECT COALESCE(ocr_engine,'null'), COUNT(*) FROM text_extractions GROUP BY ocr_engine"
    )))
print("--- recent ---")
engine_col = "ocr_engine" if "ocr_engine" in cols else "NULL"
sql = f"""
SELECT timestamp, round(confidence,3), substr(extracted_text,1,50), {engine_col}
FROM text_extractions ORDER BY timestamp DESC LIMIT 20
"""
for row in c.execute(sql):
    print(row)
rows = c.execute(
    "SELECT confidence FROM text_extractions ORDER BY timestamp DESC LIMIT 300"
).fetchall()
bands = {"lt70": 0, "70_95": 0, "ge95": 0}
for (conf,) in rows:
    if conf < 0.70:
        bands["lt70"] += 1
    elif conf < 0.95:
        bands["70_95"] += 1
    else:
        bands["ge95"] += 1
print("saved_conf_bands_last300", bands)
conn.close()
