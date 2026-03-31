import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DOCUMENT_DIR = PROJECT_ROOT / "document"
COOKIE_PATH = PROJECT_ROOT / ".jobcan_cookies.json"

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# Jobcan
JOBCAN_BASE_URL = "https://ssl.wf.jobcan.jp"
JOBCAN_LOGIN_URL = "https://id.jobcan.jp/users/sign_in?app_key=wf"
JOBCAN_CONTRACT_FORM_ID = "666628"  # 契約・発注稟議
JOBCAN_PAYMENT_FORM_ID = "666591"   # 支払依頼 / 請求書提出
JOBCAN_EMAIL = os.getenv("JOBCAN_EMAIL", "")
JOBCAN_PASSWORD = os.getenv("JOBCAN_PASSWORD", "")
