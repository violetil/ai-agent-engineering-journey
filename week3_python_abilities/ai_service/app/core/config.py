from dotenv import load_dotenv
import os
import httpx


load_dotenv()


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

HTTP_TIMEOUT = httpx.Timeout(60.0, connect=5.0)


def deepseek_headers() -> dict[str, str]:
  return {
    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    "Content-Type": "application/json"
  }