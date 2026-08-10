import sqlite3
conn = sqlite3.connect("data/news_monitor.db")
c = conn.cursor()
print("since 17:18 midband", c.execute(
    """
    SELECT COUNT(*) FROM text_extractions
    WHERE timestamp >= '2026-08-10 17:18:00'
      AND confidence >= 0.70 AND confidence < 0.95
    """
).fetchone()[0])
print("since 17:18 high", c.execute(
    """
    SELECT COUNT(*) FROM text_extractions
    WHERE timestamp >= '2026-08-10 17:18:00' AND confidence >= 0.95
    """
).fetchone()[0])
print("recent midband samples:")
for row in c.execute(
    """
    SELECT timestamp, round(confidence,3)
    FROM text_extractions
    WHERE timestamp >= '2026-08-10 17:18:00'
      AND confidence >= 0.70 AND confidence < 0.95
    ORDER BY timestamp DESC LIMIT 15
    """
):
    print(row)
conn.close()
