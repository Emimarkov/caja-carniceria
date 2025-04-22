import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"),
    port=os.getenv("DB_PORT", 5432)
)

cur = conn.cursor()

# Renombrar columna con espacio
cur.execute('ALTER TABLE ventas RENAME COLUMN "fecha " TO fecha;')

conn.commit()
conn.close()
print("✅ Columna renombrada correctamente.")
