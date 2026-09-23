from supabase import create_client, Client
from dotenv import load_dotenv
import logging
import os
import warnings
import ollama
from bs4 import XMLParsedAsHTMLWarning
import asyncio

load_dotenv()

# Suppress XML warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# ==========================================
# 1. LOGGING & CONFIGURATION SETUP
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("agent_engine_debug.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AskFastaIngestionEngine")

# Production Credentials / Environment Variables
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "your-production-ollama-key")
SUPABASE_URL = os.getenv("SUPABASE_URL", "your-supabase-url")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-supabase-key")

# Initialize Clients
ollama_client = ollama.Client(
    host=OLLAMA_HOST,
    headers={'Authorization': f'Bearer {OLLAMA_API_KEY}'} if OLLAMA_API_KEY != "your-production-ollama-key" else {}
)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Pure RAM Memory Queue (No Disk I/O)
message_queue = asyncio.Queue(maxsize=50)
