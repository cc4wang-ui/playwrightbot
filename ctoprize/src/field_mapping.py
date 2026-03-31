"""Jobcanフォームフィールドのマッピング定義

PDFから抽出したデータをJobcanのフォームフィールドにマッピングする。
Jobcanの画面構造が変更された場合は、このファイルのセレクタを更新する。

=== 契約・発注稟議 (Form ID: 666628) ===
フィールド名 → form_item ID の対応:
  申請タイトル           → title (text)
  関連グループ           → related_group (text, search popup)
  稟議の種類             → form_item3831493 (checkbox: 稟議/事後稟議/再稟議)
  契約締結日             → form_item3831494 (text, yyyy/mm/dd)
  内容                   → form_item3818321 (checkbox: 当社からの支払い/取引先からの受取)
  申請内容               → form_item3818329 (checkbox: 契約書/発注書/申込書/利用規約合意)
  取引先種別(新規/既存)  → form_item3818323 (select)
  プロジェクト名         → form_item3831525 (text)
  予算関連備考           → form_item3818328 (textarea)
  金額の範囲             → form_item3869371 (select)
  発注額                 → form_item3818325 (number)
  支払サイクル           → form_item3818340 (select)
  反社チェック           → form_item3818330 (radio)
  証券番号               → form_item3818331 (text)
  反社チェック完了番号   → form_item3818332 (text)
  秘密保持契約書         → form_item3831551 (select: YES/NO)
  取引基本契約書         → form_item3831552 (select: YES/NO)
  相見積もり             → form_item3822626 (radio: 未/済)
  締結方法               → form_item3818338 (radio)
  リーガルチェック       → form_item3831553 (radio: YES/NO)
  リーガルチェックURL    → form_item3818339 (text)
  支払手段               → form_item3818341 (select)

=== 支払依頼 / 請求書提出 (Form ID: 666591) ===
フィールド名 → name の対応:
  申請タイトル     → title (text)
  関連申請         → related_request_view_id (text, search popup)
  内容             → pay_content (textarea)
  --- 明細行(row=0, col=0) ---
  内訳             → account_title_part_0_0 (text, popup)
  計上日           → allocation_date_0_0 (text, calendar)
  金額             → specifics_amount_0_0 (number)
  内容(明細)       → pay_content_0_0 (text)
  取引先           → company_0_0 (text, search popup)
  支払日           → payment_date_0_0 (text, calendar)
  振込手数料       → bank_transfer_fee_type_0_0 (select: 0=当方負担/1=先方負担)
  源泉徴収税       → withholding_tax_calc_0_0 (select: 0=なし/2=あり(税抜)/1=あり(税込))
  グループ         → specifics_group_0_0 (text, popup)
  プロジェクト     → specifics_project_0_0 (text, popup)
  --- カスタムフィールド ---
  決済方法         → form_item3818255 (radio)
  取引先種別       → form_item3954869 (radio)
  通貨             → form_item3818256 (radio)
"""

from __future__ import annotations

from datetime import datetime

# ─── 契約・発注稟議: セレクタ定数 ───

CONTRACT_FIELDS = {
    "title": 'input[name="title"]',
    "related_group": 'input[name="related_group"]',
    "ringi_type": 'input[name="form_item3831493"]',        # checkbox
    "contract_date": 'input[name="form_item3831494"]',      # text yyyy/mm/dd
    "content_type": 'input[name="form_item3818321"]',       # checkbox
    "application_type": 'input[name="form_item3818329"]',   # checkbox
    "vendor_status": 'select[name="form_item3818323"]',     # select
    "project_name": 'input[name="form_item3831525"]',       # text
    "budget_note": 'textarea[name="form_item3818328"]',     # textarea
    "amount_range": 'select[name="form_item3869371"]',      # select
    "order_amount": 'input[name="form_item3818325"]',       # number
    "payment_cycle": 'select[name="form_item3818340"]',     # select
    "anti_social": 'input[name="form_item3818330"]',        # radio
    "stock_code": 'input[name="form_item3818331"]',         # text
    "anti_social_number": 'input[name="form_item3818332"]', # text
    "nda": 'select[name="form_item3831551"]',               # select
    "basic_agreement": 'select[name="form_item3831552"]',   # select
    "competitive_quote": 'input[name="form_item3822626"]',  # radio
    "signing_method": 'input[name="form_item3818338"]',     # radio
    "legal_check": 'input[name="form_item3831553"]',        # radio
    "legal_check_url": 'input[name="form_item3818339"]',    # text
    "payment_method": 'select[name="form_item3818341"]',    # select
    "draft_button": "button.grayButton",                    # 下書き保存
    "submit_button": 'button:has-text("提出する")',         # 提出する
}

# 契約・発注稟議 checkbox のインデックスマッピング
# form_item3831493 (稟議の種類): 0=稟議, 1=事後稟議, 2=再稟議
CONTRACT_RINGI_TYPE = {"稟議": 0, "事後稟議": 1, "再稟議": 2}

# form_item3818321 (内容): 0=当社からの支払い, 1=取引先からの受取
CONTRACT_CONTENT_TYPE = {"当社からの支払い（費用）": 0, "取引先からの受取（売上）": 1}

# form_item3818329 (申請内容): 0=契約書, 1=発注書, 2=申込書, 3=利用規約合意
CONTRACT_APP_TYPE = {"契約書": 0, "発注書": 1, "申込書": 2, "利用規約合意": 3}

# Select の value prefix (AngularJS)
SELECT_PREFIX = "string:"


# ─── 支払依頼: セレクタ定数 ───

PAYMENT_FIELDS = {
    "title": 'input[name="title"]',
    "related_request": 'input[name="related_request_view_id"]',
    "content": 'textarea[name="pay_content"]',
    # 明細行 (row 0)
    "breakdown": 'input[name="account_title_part_0_0"]',
    "recording_date": 'input[name="allocation_date_0_0"]',
    "amount": 'input[name="specifics_amount_0_0"]',
    "detail_content": 'input[name="pay_content_0_0"]',
    "vendor_search": 'input[name="company_0_0"]',
    "payment_date": 'input[name="payment_date_0_0"]',
    "transfer_fee": 'select[name="bank_transfer_fee_type_0_0"]',
    "withholding_tax": 'select[name="withholding_tax_calc_0_0"]',
    "group": 'input[name="specifics_group_0_0"]',
    "project": 'input[name="specifics_project_0_0"]',
    # カスタムフィールド (radio)
    "settlement_method": 'input[name="form_item3818255"]',
    "vendor_type": 'input[name="form_item3954869"]',
    "currency": 'input[name="form_item3818256"]',
    "draft_button": "button.grayButton",
    "submit_button": 'button:has-text("提出する")',
}

# 源泉徴収税の値マッピング
WITHHOLDING_TAX_VALUES = {
    "none": "0",
    "pretax": "2",      # あり(税抜)
    "posttax": "1",     # あり(税込)
}

# 振込手数料
TRANSFER_FEE_VALUES = {
    "当方負担": "0",
    "先方負担": "1",
}

# 決済方法 (form_item3818255) の radio value
SETTLEMENT_METHOD_VALUES = {
    "bank_transfer": "銀行振込",
    "credit_card": "クレカ(UPSIDER)",
    "shopfanpick": "Shopfanpick経由",
    "direct_debit": "口座引き落とし",
    "overseas_transfer": "海外送金",
    "payeasy": "Payeasy",
    "paypal": "PayPal",
}

# 取引先種別 (form_item3954869) の radio value
VENDOR_TYPE_VALUES = {
    "corporation": "法人",
    "individual": "個人",
    "corporation_overseas": "法人(海外)",
    "individual_overseas": "個人(海外)",
}

# 通貨 (form_item3818256) の radio value
CURRENCY_VALUES = {
    "JPY": "円",
    "KRW": "ウォン",
    "USD": "ドル",
}

# 支払手段 (form_item3818341) 契約・発注稟議用
CONTRACT_PAYMENT_METHOD_VALUES = {
    "bank_transfer": "string:銀行振込",
    "credit_card": "string:クレジットカード",
    "paypal": "string:Paypal",
    "bill": "string:納付書",
    "other": "string:その他",
}


# ─── タイトル生成 ───

def generate_contract_title(data: dict) -> str:
    """契約・発注稟議の申請タイトルを自動生成する。
    フォーマット: YYYYMMDD_取引先名_件名
    """
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    vendor = data.get("vendor_name", "")
    subject = data.get("subject", "") or data.get("item_description", "")
    parts = [p for p in [date_str, vendor, subject] if p]
    return "_".join(parts)


def generate_payment_title(data: dict) -> str:
    """支払依頼の申請タイトルを自動生成する。
    フォーマット: YYYY年MM月_取引会社名_内容
    """
    now = datetime.now()
    date_str = now.strftime("%Y年%m月")
    vendor = data.get("vendor_name", "")
    desc = data.get("description", "")
    parts = [p for p in [date_str, vendor, desc[:30]] if p]
    return "_".join(parts)


# ─── マッピング関数 ───

def map_to_contract_form(extracted_data: dict, budget_url: str = "") -> dict:
    """PDF抽出データを契約・発注稟議フォームのフィールドにマッピングする。

    Returns:
        Jobcanフォームに入力するためのデータ dict
    """
    # 取引種別から申請内容チェックボックスのインデックスを決定
    transaction_type = extracted_data.get("transaction_type", "発注")
    app_type_map = {"契約": "契約書", "発注": "発注書", "申込": "申込書"}
    app_type_label = app_type_map.get(transaction_type, "発注書")

    # 発注額から金額の範囲を判定
    amount = extracted_data.get("amount_excluding_tax") or 0
    if amount >= 5_000_000:
        amount_range = "string:500万円以上"
    else:
        amount_range = "string:予算内"

    return {
        "title": generate_contract_title(extracted_data),
        "ringi_type": "稟議",  # デフォルト: 稟議
        "contract_date": extracted_data.get("delivery_date", ""),  # yyyy/mm/dd
        "content_type": "当社からの支払い（費用）",  # デフォルト
        "application_type": app_type_label,
        "vendor_status": "string:既存",  # デフォルト
        "project_name": "",  # 予算申請から取得
        "budget_note": budget_url,  # 予算関連備考に予算申請URLを記入
        "amount_range": amount_range,
        "order_amount": str(int(amount)) if amount else "",
        "payment_cycle": "string:30日",  # デフォルト
        "anti_social": "非上場企業（反社チェック実施）",  # デフォルト
        "nda": "string:YES",
        "basic_agreement": "string:NO",
        "competitive_quote": "未",
        "signing_method": "電子契約",  # デフォルト
        "legal_check": "NO",
        "payment_method": CONTRACT_PAYMENT_METHOD_VALUES.get(
            extracted_data.get("payment_method", "bank_transfer"),
            "string:銀行振込",
        ),
        # PDF抽出データ（プレビュー用に保持）
        "_vendor_name": extracted_data.get("vendor_name", ""),
        "_subject": extracted_data.get("subject", ""),
        "_item_description": extracted_data.get("item_description", ""),
        "_amount_excluding_tax": extracted_data.get("amount_excluding_tax"),
        "_amount_including_tax": extracted_data.get("amount_including_tax"),
        "_delivery_date": extracted_data.get("delivery_date", ""),
        "_vendor_type": extracted_data.get("vendor_type", "corporation"),
        "_period_start": extracted_data.get("period_start", ""),
        "_period_end": extracted_data.get("period_end", ""),
    }


def map_to_payment_form(extracted_data: dict, contract_url: str = "") -> dict:
    """PDF抽出データを支払依頼フォームのフィールドにマッピングする。

    Returns:
        Jobcanフォームに入力するためのデータ dict
    """
    return {
        "title": generate_payment_title(extracted_data),
        "related_request_url": contract_url,
        "content": extracted_data.get("description", ""),
        # 明細行
        "detail_content": extracted_data.get("description", ""),
        "amount": extracted_data.get("amount"),
        "recording_date": extracted_data.get("recording_date", ""),
        "payment_date": extracted_data.get("payment_date", ""),
        "vendor_name": extracted_data.get("vendor_name", ""),
        # カスタムフィールド
        "settlement_method": SETTLEMENT_METHOD_VALUES.get(
            extracted_data.get("payment_method", "bank_transfer"), "銀行振込"
        ),
        "vendor_type": VENDOR_TYPE_VALUES.get(
            extracted_data.get("vendor_type", "corporation"), "法人"
        ),
        "currency": CURRENCY_VALUES.get(
            extracted_data.get("currency", "JPY"), "円"
        ),
        "withholding_tax": WITHHOLDING_TAX_VALUES.get(
            extracted_data.get("tax_withholding", "none"), "0"
        ),
        "transfer_fee": "0",  # デフォルト: 当方負担
        "breakdown_items": extracted_data.get("breakdown_items", []),
    }
