"""Gemini APIを使って発注書/請求書PDFから構造化データを抽出する"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, GEMINI_MODEL

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client

PURCHASE_ORDER_PROMPT = """\
この発注書PDFから以下の情報をJSON形式で抽出してください。
該当しない項目はnullとしてください。

{
  "vendor_name": "取引先名（会社名）",
  "subject": "件名・案件名",
  "amount_excluding_tax": 金額（税抜・数値）,
  "amount_including_tax": 金額（税込・数値）,
  "tax_rate": 税率（数値、例: 10）,
  "delivery_date": "納期（YYYY-MM-DD形式）",
  "item_description": "品名・摘要・内容の説明",
  "vendor_type": "corporation" または "individual",
  "period_start": "業務開始日（YYYY-MM-DD形式）",
  "period_end": "業務終了日（YYYY-MM-DD形式）",
  "transaction_type": "取引種別（見積/発注/発注変更/契約/その他）"
}

JSONのみを出力してください。説明文は不要です。
"""

INVOICE_PROMPT = """\
この請求書PDFから以下の情報をJSON形式で抽出してください。
該当しない項目はnullとしてください。

{
  "vendor_name": "支払先名（会社名）",
  "invoice_number": "請求書番号",
  "amount": 金額（数値）,
  "tax_amount": 消費税額（数値）,
  "payment_date": "支払日（YYYY-MM-DD形式）",
  "recording_date": "計上日（YYYY-MM-DD形式）",
  "description": "内容・摘要",
  "currency": "JPY" または "KRW" または "USD",
  "tax_withholding": "none" または "pretax" または "posttax",
  "payment_method": "bank_transfer" または "credit_card" または "direct_debit" または "overseas_transfer" または "payeasy" または "paypal",
  "vendor_type": "corporation" または "individual" または "corporation_overseas" または "individual_overseas",
  "breakdown_items": [
    {
      "description": "内訳の説明",
      "amount": 金額（数値）,
      "recording_date": "計上日（YYYY-MM-DD形式）"
    }
  ]
}

JSONのみを出力してください。説明文は不要です。
"""


def extract_from_pdf(pdf_path: str | Path, doc_type: str = "purchase_order") -> dict:
    """PDFからGemini APIを使って構造化データを抽出する。

    Args:
        pdf_path: PDFファイルのパス
        doc_type: "purchase_order"（発注書）または "invoice"（請求書）

    Returns:
        抽出された構造化データのdict
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    prompt = PURCHASE_ORDER_PROMPT if doc_type == "purchase_order" else INVOICE_PROMPT

    # PDFをインラインデータとして送信（日本語ファイル名対応）
    client = _get_client()
    pdf_bytes = pdf_path.read_bytes()

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            prompt,
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        ],
    )

    # JSONを抽出（```json ... ``` で囲まれている場合にも対応）
    text = response.text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # 最初と最後の```行を除去
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines)

    return json.loads(text)


def extract_purchase_order(pdf_path: str | Path) -> dict:
    """発注書PDFからデータを抽出する"""
    return extract_from_pdf(pdf_path, "purchase_order")


def extract_invoice(pdf_path: str | Path) -> dict:
    """請求書PDFからデータを抽出する"""
    return extract_from_pdf(pdf_path, "invoice")
