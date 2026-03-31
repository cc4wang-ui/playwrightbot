"""Jobcan自動入力システム - Streamlit WebUI"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

import streamlit as st

from src.config import GEMINI_API_KEY, JOBCAN_EMAIL, JOBCAN_PASSWORD
from src.field_mapping import map_to_contract_form, map_to_payment_form
from src.pdf_extractor import extract_invoice, extract_purchase_order

# ログ設定
logging.basicConfig(level=logging.INFO)

st.set_page_config(page_title="Jobcan自動入力", page_icon="🤖", layout="wide")

st.title("🤖 Jobcan自動入力システム")
st.caption("発注書・請求書PDFからJobcanフォームを自動入力します")

# ─── サイドバー: 設定・ログイン情報 ───
with st.sidebar:
    st.header("⚙️ 設定")

    # Gemini API状態
    st.write(f"Gemini API: {'✅ 設定済み' if GEMINI_API_KEY else '❌ 未設定'}")
    st.divider()

    # Jobcan認証情報（各ユーザーが入力）
    st.subheader("🔑 Jobcanログイン")
    jobcan_email = st.text_input(
        "メールアドレス",
        value=JOBCAN_EMAIL,
        placeholder="your-email@mikai.co.jp",
        key="jobcan_email",
    )
    jobcan_password = st.text_input(
        "パスワード",
        value=JOBCAN_PASSWORD,
        type="password",
        key="jobcan_password",
    )

    if jobcan_email and jobcan_password:
        st.success("✅ Jobcan認証情報が入力されています")
    else:
        st.warning("⚠️ Jobcanのメールアドレスとパスワードを入力してください")

    st.divider()
    headless = st.checkbox("ヘッドレスモード（サーバー配置時はON）", value=True)
    st.caption("OFFにするとブラウザが画面に表示されます（デバッグ用）")

    auto_draft = st.checkbox("自動で下書き保存する", value=False)
    st.caption("ONにするとフォーム入力後に自動で下書き保存します")


def _get_filler():
    """サイドバーの認証情報でJobcanFillerを作成する"""
    from src.jobcan_filler import JobcanFiller

    return JobcanFiller(
        headless=headless,
        email=jobcan_email,
        password=jobcan_password,
    )


# ─── メインコンテンツ: タブ切り替え ───
tab1, tab2 = st.tabs(["📋 契約・発注稟議", "💰 支払依頼/請求書"])

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# タブ1: 契約・発注稟議
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab1:
    st.header("契約・発注稟議の自動入力")
    st.write("予算申請のリンクと発注書PDFから、契約・発注稟議フォームを自動入力します。")

    col1, col2 = st.columns(2)

    with col1:
        budget_url = st.text_input(
            "予算申請のJobcanリンク（予算関連備考に記載されます）",
            placeholder="https://ssl.wf.jobcan.jp/#/...",
            key="budget_url",
        )
        po_file = st.file_uploader("発注書PDF", type=["pdf"], key="po_file")

    # PDF解析実行
    if po_file and st.button("📄 発注書を解析する", key="extract_po"):
        with st.spinner("Gemini APIで発注書を解析中..."):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(po_file.read())
                tmp_path = tmp.name

            try:
                extracted = extract_purchase_order(tmp_path)
                st.session_state["po_extracted"] = extracted
                st.session_state["po_tmp_path"] = tmp_path
                st.success("✅ 解析完了!")
            except Exception as e:
                st.error(f"解析エラー: {e}")

    # 抽出データの表示・編集
    if "po_extracted" in st.session_state:
        with col2:
            st.subheader("抽出データ（編集可能）")
            edited_json = st.text_area(
                "JSON",
                value=json.dumps(
                    st.session_state["po_extracted"],
                    ensure_ascii=False,
                    indent=2,
                ),
                height=400,
                key="po_json_edit",
            )

        st.divider()

        # マッピング結果のプレビュー
        try:
            edited_data = json.loads(edited_json)
            form_data = map_to_contract_form(edited_data, budget_url)

            st.subheader("📝 Jobcanフォーム入力データ（プレビュー）")
            preview_col1, preview_col2 = st.columns(2)
            with preview_col1:
                st.write("**申請タイトル:**", form_data["title"])
                st.write("**取引先名:**", form_data.get("_vendor_name", ""))
                st.write("**件名:**", form_data.get("_subject", ""))
                st.write("**品名・摘要:**", form_data.get("_item_description", ""))
                st.write("**稟議の種類:**", form_data.get("ringi_type", ""))
                st.write("**申請内容:**", form_data.get("application_type", ""))
            with preview_col2:
                amount = form_data.get("_amount_excluding_tax")
                st.write(
                    "**発注額:**",
                    f"¥{amount:,}" if amount else "-",
                )
                st.write("**金額の範囲:**", form_data.get("amount_range", "").replace("string:", ""))
                st.write("**納期:**", form_data.get("_delivery_date", ""))
                st.write("**支払サイクル:**", form_data.get("payment_cycle", "").replace("string:", ""))
                st.write("**締結方法:**", form_data.get("signing_method", ""))
                st.write("**支払手段:**", form_data.get("payment_method", "").replace("string:", ""))

            st.divider()

            # Jobcan自動入力実行
            if not (jobcan_email and jobcan_password):
                st.warning("⬅️ サイドバーでJobcanの認証情報を入力してください")
            elif st.button(
                "🚀 Jobcanに自動入力する（契約・発注稟議）",
                key="fill_contract",
                type="primary",
            ):
                with st.spinner("Jobcanフォームに入力中..."):
                    try:
                        with _get_filler() as filler:
                            status = st.empty()
                            status.info("🔑 Jobcanにログイン中...")
                            filler.login()

                            status.info("📝 契約・発注稟議フォームを開いています...")
                            filler.navigate_to_new_contract()

                            status.info("✍️ フォームにデータを入力中...")
                            pdf_path = st.session_state.get("po_tmp_path")
                            filler.fill_contract_form(form_data, pdf_path=pdf_path)

                            if auto_draft:
                                status.info("💾 下書き保存中...")
                                filler.save_contract_draft()

                            status.info("📸 スクリーンショットを撮影中...")
                            screenshot = filler.take_screenshot()
                            st.image(screenshot, caption="入力完了後の画面")

                            if auto_draft:
                                status.success("✅ 自動入力 & 下書き保存完了!")
                            else:
                                status.success("✅ 自動入力完了! Jobcanで内容を確認して下書き保存してください。")

                    except Exception as e:
                        st.error(f"自動入力エラー: {e}")
                        import traceback
                        st.code(traceback.format_exc())

        except json.JSONDecodeError:
            st.warning("JSONの形式が正しくありません。修正してください。")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# タブ2: 支払依頼/請求書
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab2:
    st.header("支払依頼/請求書の自動入力")
    st.write("発注稟議のリンクと請求書PDFから、支払依頼フォームを自動入力します。")

    col1, col2 = st.columns(2)

    with col1:
        contract_url = st.text_input(
            "発注稟議のJobcanリンク（関連申請の検索に使用）",
            placeholder="https://ssl.wf.jobcan.jp/#/...",
            key="contract_url",
        )
        inv_file = st.file_uploader("請求書PDF", type=["pdf"], key="inv_file")

    # PDF解析実行
    if inv_file and st.button("📄 請求書を解析する", key="extract_inv"):
        with st.spinner("Gemini APIで請求書を解析中..."):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(inv_file.read())
                tmp_path_inv = tmp.name

            try:
                extracted = extract_invoice(tmp_path_inv)
                st.session_state["inv_extracted"] = extracted
                st.session_state["inv_tmp_path"] = tmp_path_inv
                st.success("✅ 解析完了!")
            except Exception as e:
                st.error(f"解析エラー: {e}")

    # 抽出データの表示・編集
    if "inv_extracted" in st.session_state:
        with col2:
            st.subheader("抽出データ（編集可能）")
            edited_inv_json = st.text_area(
                "JSON",
                value=json.dumps(
                    st.session_state["inv_extracted"],
                    ensure_ascii=False,
                    indent=2,
                ),
                height=400,
                key="inv_json_edit",
            )

        st.divider()

        try:
            edited_inv_data = json.loads(edited_inv_json)
            form_data = map_to_payment_form(edited_inv_data, contract_url)

            st.subheader("📝 Jobcanフォーム入力データ（プレビュー）")
            preview_col1, preview_col2 = st.columns(2)
            with preview_col1:
                st.write("**申請タイトル:**", form_data["title"])
                st.write("**支払先:**", form_data["vendor_name"])
                st.write("**内容:**", form_data["content"])
                st.write("**決済方法:**", form_data["settlement_method"])
                st.write("**取引先種別:**", form_data["vendor_type"])
            with preview_col2:
                amount = form_data.get("amount")
                st.write(
                    "**金額:**",
                    f"¥{amount:,}" if amount else "-",
                )
                st.write("**計上日:**", form_data.get("recording_date", ""))
                st.write("**支払日:**", form_data.get("payment_date", ""))
                st.write("**通貨:**", form_data["currency"])
                withholding_map = {"0": "なし", "2": "あり(税抜)", "1": "あり(税込)"}
                st.write(
                    "**源泉徴収:**",
                    withholding_map.get(form_data.get("withholding_tax", "0"), "なし"),
                )

            st.divider()

            # Jobcan自動入力実行
            if not (jobcan_email and jobcan_password):
                st.warning("⬅️ サイドバーでJobcanの認証情報を入力してください")
            elif st.button(
                "🚀 Jobcanに自動入力する（支払依頼）",
                key="fill_payment",
                type="primary",
            ):
                with st.spinner("Jobcanフォームに入力中..."):
                    try:
                        with _get_filler() as filler:
                            status = st.empty()
                            status.info("🔑 Jobcanにログイン中...")
                            filler.login()

                            status.info("📝 支払依頼フォームを開いています...")
                            filler.navigate_to_new_payment()

                            status.info("✍️ フォームにデータを入力中...")
                            pdf_path = st.session_state.get("inv_tmp_path")
                            filler.fill_payment_form(form_data, pdf_path=pdf_path)

                            if auto_draft:
                                status.info("💾 下書き保存中...")
                                filler.save_payment_draft()

                            status.info("📸 スクリーンショットを撮影中...")
                            screenshot = filler.take_screenshot()
                            st.image(screenshot, caption="入力完了後の画面")

                            if auto_draft:
                                status.success("✅ 自動入力 & 下書き保存完了!")
                            else:
                                status.success("✅ 自動入力完了! Jobcanで内容を確認して下書き保存してください。")

                    except Exception as e:
                        st.error(f"自動入力エラー: {e}")
                        import traceback
                        st.code(traceback.format_exc())

        except json.JSONDecodeError:
            st.warning("JSONの形式が正しくありません。修正してください。")
