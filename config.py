import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Установіть BOT_TOKEN як змінну середовища")

NARRATOR = "Ведучий бункера"

