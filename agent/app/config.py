import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "retailagent")
DB_NAME = os.getenv("DB_NAME", "store_142")

AUDIO_DIR = "static/audio"