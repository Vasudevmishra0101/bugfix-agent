import os

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
REPO_NAME = os.environ["REPO_NAME"]
MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", "3"))
MODEL = os.environ.get("MODEL", "qwen/qwen3.8-27b:free")
