"""PlaywrightによるJobcanフォーム自動入力モジュール

Jobcanワークフローの契約・発注稟議フォームと支払依頼フォームに
データを自動入力する。

JobcanはAngularJSベースのSPAで、カスタムポップアップ（ドロップダウン、
カレンダー、検索モーダル）を多用しているため、それぞれ専用のハンドリングが必要。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from playwright.sync_api import Page, sync_playwright, TimeoutError as PwTimeout

from src.config import (
    COOKIE_PATH,
    JOBCAN_BASE_URL,
    JOBCAN_CONTRACT_FORM_ID,
    JOBCAN_LOGIN_URL,
    JOBCAN_PASSWORD,
    JOBCAN_PAYMENT_FORM_ID,
    JOBCAN_EMAIL,
)
from src.field_mapping import (
    CONTRACT_APP_TYPE,
    CONTRACT_CONTENT_TYPE,
    CONTRACT_FIELDS,
    CONTRACT_RINGI_TYPE,
    PAYMENT_FIELDS,
    SELECT_PREFIX,
)

logger = logging.getLogger(__name__)


class JobcanFiller:
    """Jobcanフォーム自動入力クラス"""

    def __init__(self, headless: bool = False, email: str = "", password: str = ""):
        self.headless = headless
        self.email = email or JOBCAN_EMAIL
        self.password = password or JOBCAN_PASSWORD
        self._playwright = None
        self._browser = None
        self._context = None
        self.page: Page | None = None

    def start(self):
        """ブラウザを起動する"""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)

        # Cookie復元を試みる
        if COOKIE_PATH.exists():
            try:
                self._context = self._browser.new_context(
                    storage_state=str(COOKIE_PATH)
                )
            except Exception:
                self._context = self._browser.new_context()
        else:
            self._context = self._browser.new_context()

        self.page = self._context.new_page()
        self.page.set_default_timeout(30000)

    def stop(self):
        """ブラウザを閉じる"""
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def _save_cookies(self):
        """セッションCookieを保存する"""
        if self._context:
            try:
                self._context.storage_state(path=str(COOKIE_PATH))
            except Exception as e:
                logger.warning(f"Cookie保存に失敗: {e}")

    # ─── ログイン ───

    def login(self):
        """Jobcanにログインする。

        id.jobcan.jp のSSO画面を経由し、ssl.wf.jobcan.jp にリダイレクトされる。
        Cookieが有効な場合はスキップされる。
        """
        # SSO経由でログイン: まずログインURLに直接アクセス
        # Cookieが有効ならssl.wf.jobcan.jpにリダイレクト、無効ならログインフォームが表示
        self.page.goto(JOBCAN_LOGIN_URL)
        self.page.wait_for_load_state("domcontentloaded")
        self.page.wait_for_timeout(3000)

        # ログインページにいる場合（リダイレクトされなかった）
        if "id.jobcan.jp" in self.page.url:
            logger.info("ログイン画面を検出。ログインを実行します。")

            # メールアドレスとパスワードを入力
            self.page.fill('input[name="user[email]"]', self.email)
            self.page.fill('input[name="user[password]"]', self.password)
            self.page.click('input[type="submit"], button[type="submit"]')

            # ログイン後のリダイレクトを待つ（ssl.wf.jobcan.jpに戻るまで）
            try:
                self.page.wait_for_url("**/ssl.wf.jobcan.jp/**", timeout=15000)
            except PwTimeout:
                # URLベースの待機が失敗した場合はタイムアウトで待つ
                self.page.wait_for_timeout(5000)

            self._save_cookies()
            logger.info(f"ログイン完了。現在のURL: {self.page.url}")
        else:
            logger.info("ログイン済み（Cookieが有効）。")

    # ─── ナビゲーション ───

    def navigate_to_new_contract(self):
        """契約・発注稟議の新規申請画面を開く"""
        url = f"{JOBCAN_BASE_URL}/#/request/new/{JOBCAN_CONTRACT_FORM_ID}/"
        self.page.goto(url)
        self.page.wait_for_load_state("domcontentloaded")
        self.page.wait_for_timeout(2000)  # AngularJSのレンダリング待ち
        logger.info(f"契約・発注稟議フォームを開きました: {url}")

    def navigate_to_new_payment(self):
        """支払依頼の新規申請画面を開く"""
        url = f"{JOBCAN_BASE_URL}/#/request/new/{JOBCAN_PAYMENT_FORM_ID}/"
        self.page.goto(url)
        self.page.wait_for_load_state("domcontentloaded")
        self.page.wait_for_timeout(2000)
        logger.info(f"支払依頼フォームを開きました: {url}")

    # ─── 共通ヘルパーメソッド ───

    def _fill_text(self, selector: str, value: str):
        """テキストフィールドに入力する"""
        if not value:
            return
        try:
            el = self.page.locator(selector)
            el.click()
            el.fill(str(value))
            self.page.wait_for_timeout(200)
        except Exception as e:
            logger.warning(f"テキスト入力失敗 [{selector}]: {e}")

    def _fill_number(self, selector: str, value):
        """数値フィールドに入力する"""
        if value is None:
            return
        try:
            el = self.page.locator(selector)
            el.click()
            el.fill(str(int(value)))
            self.page.wait_for_timeout(200)
        except Exception as e:
            logger.warning(f"数値入力失敗 [{selector}]: {e}")

    def _select_option(self, selector: str, value: str):
        """HTML <select> ドロップダウンから選択する。

        Jobcanのselectは value が "string:xxx" 形式。
        """
        if not value:
            return
        try:
            self.page.select_option(selector, value)
            self.page.wait_for_timeout(300)
        except Exception as e:
            logger.warning(f"セレクト選択失敗 [{selector}] value={value}: {e}")

    def _click_radio(self, name: str, value: str):
        """ラジオボタンを選択する。

        name属性とvalue属性で特定してクリック。
        """
        if not value:
            return
        try:
            selector = f'input[name="{name}"][value="{value}"]'
            el = self.page.locator(selector)
            # ラジオボタンが直接クリックできない場合は親要素をクリック
            if el.count() > 0:
                el.first.click(force=True)
                self.page.wait_for_timeout(300)
            else:
                logger.warning(f"ラジオボタンが見つかりません: {selector}")
        except Exception as e:
            logger.warning(f"ラジオ選択失敗 [name={name}, value={value}]: {e}")

    def _click_checkbox_by_index(self, name: str, index: int):
        """チェックボックスをインデックスで選択する。

        同じname属性の複数チェックボックスのうち、指定インデックスのものをクリック。
        """
        try:
            checkboxes = self.page.locator(f'input[name="{name}"]')
            if checkboxes.count() > index:
                checkboxes.nth(index).click(force=True)
                self.page.wait_for_timeout(300)
            else:
                logger.warning(
                    f"チェックボックス index={index} が範囲外 "
                    f"(name={name}, count={checkboxes.count()})"
                )
        except Exception as e:
            logger.warning(f"チェックボックス選択失敗 [name={name}, index={index}]: {e}")

    def _fill_date_field(self, selector: str, date_str: str):
        """日付フィールドに入力する。

        Jobcanの日付フィールドはクリックするとカレンダーポップアップが開く。
        直接テキストを入力し、Escキーでカレンダーを閉じる。
        日付形式: yyyy/mm/dd
        """
        if not date_str:
            return
        # YYYY-MM-DD → YYYY/MM/DD に変換
        date_str = date_str.replace("-", "/")
        try:
            el = self.page.locator(selector)
            el.click()
            self.page.wait_for_timeout(500)
            # 既存のテキストをクリアして入力
            el.fill("")
            el.type(date_str, delay=50)
            # カレンダーポップアップを閉じる
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)
        except Exception as e:
            logger.warning(f"日付入力失敗 [{selector}]: {e}")

    def _close_modal(self):
        """開いているモーダルを閉じる（共通ヘルパー）"""
        try:
            # 閉じるボタンを探す
            close_selectors = [
                ".modal .close",
                ".modal-header .close",
                "button.close",
                ".modal button:has-text('×')",
                ".modal button:has-text('閉じる')",
            ]
            for sel in close_selectors:
                btn = self.page.locator(sel)
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.click()
                    self.page.wait_for_timeout(500)
                    return
            # 閉じるボタンが見つからない場合はEscキー
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)
        except Exception:
            try:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(500)
            except Exception:
                pass

    def _wait_for_modal(self, timeout: int = 5000):
        """モーダルが表示されるまで待機する"""
        try:
            self.page.locator(".modal.in, .modal.show, .modal[style*='display: block']").first.wait_for(
                state="visible", timeout=timeout
            )
        except PwTimeout:
            # フォールバック: 少し待つ
            self.page.wait_for_timeout(1500)

    def _search_related_request(self, trigger_selector: str, url_or_id: str):
        """関連申請を検索・選択する。

        Jobcanの支払依頼フォームでは:
        1. 「紐付する/紐付しない」ラジオボタンがある
        2. 「紐付する」を選択すると検索フィールドが表示される
        3. 検索ボタンクリック → ポップアップで申請ID検索 → 結果選択
        URLから申請IDを抽出し、申請IDフィールドで検索する。
        """
        if not url_or_id:
            return

        # URLから申請IDを抽出（例: https://ssl.wf.jobcan.jp/#/requests/2308 → 2308）
        import re
        match = re.search(r"/requests?/(\d+)", url_or_id)
        search_id = match.group(1) if match else url_or_id

        try:
            # Step 1: 「紐付する」ラジオボタンを選択（関連申請フィールドを表示させる）
            bind_radio = self.page.locator(
                "input[type='radio'][value='bind'], "
                "label:has-text('紐付する') input[type='radio'], "
                "input[ng-model*='related'][value='true']"
            )
            if bind_radio.count() > 0:
                bind_radio.first.click(force=True)
                self.page.wait_for_timeout(1000)
                logger.info("「紐付する」を選択しました")
            else:
                # ラジオボタンが見つからない場合、ラベルを直接クリック
                bind_label = self.page.locator("label:has-text('紐付する')")
                if bind_label.count() > 0:
                    bind_label.first.click()
                    self.page.wait_for_timeout(1000)
                    logger.info("「紐付する」ラベルをクリックしました")

            # Step 2: 関連申請の検索ボタン（虫眼鏡アイコン等）をクリック
            # trigger_selector は input[name="related_request_view_id"]
            trigger = self.page.locator(trigger_selector)
            # inputの隣にある検索ボタンを探す
            search_trigger = self.page.locator(
                f'{trigger_selector} + button, '
                f'{trigger_selector} + .input-group-btn button, '
                f'{trigger_selector} ~ button, '
                f'{trigger_selector} ~ a'
            )
            if search_trigger.count() > 0 and search_trigger.first.is_visible():
                search_trigger.first.click()
            elif trigger.count() > 0 and trigger.first.is_visible():
                trigger.click()
            else:
                # 「申請書検索」リンクやボタンを直接探す
                search_link = self.page.locator(
                    "a:has-text('申請書検索'), "
                    "button:has-text('申請書検索'), "
                    "a:has-text('検索'), "
                    ".search-btn"
                )
                if search_link.count() > 0:
                    search_link.first.click()
                else:
                    logger.warning("関連申請の検索トリガーが見つかりません")
                    return
            self._wait_for_modal()

            # Step 3: モーダル内のコンテンツを探す
            modal = self.page.locator(".modal.in, .modal.show, .modal[style*='display: block']")
            if modal.count() == 0:
                modal = self.page.locator(".modal")

            # 「詳細検索」を開く（折りたたまれている場合）
            detail_toggle = modal.locator(
                "text=詳細検索, a:has-text('詳細検索'), "
                "span:has-text('詳細検索'), button:has-text('詳細検索')"
            )
            if detail_toggle.count() > 0:
                try:
                    detail_toggle.first.click()
                    self.page.wait_for_timeout(800)
                except Exception:
                    pass

            # Step 4: 「申請ID（完全一致）」フィールドにIDを入力する
            # ※ 上部の「申請タイトル」検索欄ではなく、詳細検索内の「申請ID」欄に入力する
            # ページ全体からplaceholderテキストで特定（.modalスコープに依存しない）
            filled = self.page.evaluate(f"""() => {{
                // ページ全体のinputを走査（.modalセレクタに依存しない）
                const allInputs = document.querySelectorAll('input');
                for (const input of allInputs) {{
                    const ph = input.placeholder || '';
                    // 「申請ID」「完全一致」を含むplaceholderのinputを探す
                    if (ph.includes('申請ID') || ph.includes('完全一致')) {{
                        input.focus();
                        // AngularJSのデータバインディングに対応
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        ).set;
                        nativeInputValueSetter.call(input, '{search_id}');
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        // AngularJS の $apply をトリガー
                        if (window.angular) {{
                            try {{
                                var scope = angular.element(input).scope();
                                if (scope && scope.$apply) scope.$apply();
                            }} catch(e) {{}}
                        }}
                        return true;
                    }}
                }}
                return false;
            }}""")

            if filled:
                logger.info(f"申請IDフィールドに入力しました（JS）: {search_id}")
            else:
                # フォールバック: Playwrightのlocatorでplaceholderを直接指定
                id_field = self.page.locator(
                    'input[placeholder*="申請ID"], '
                    'input[placeholder*="完全一致"]'
                )
                if id_field.count() > 0:
                    id_field.first.click()
                    id_field.first.fill(search_id)
                    logger.info(f"申請IDフィールドに入力しました（locator）: {search_id}")
                else:
                    logger.warning(f"申請IDフィールドが見つかりません。フォールバックを試行")
                    # 最後の手段: 全inputから2番目（1番目はタイトル検索）
                    visible_inputs = self.page.locator(
                        "input:visible"
                    )
                    count = visible_inputs.count()
                    logger.info(f"可視inputフィールド数: {count}")
                    # placeholderでフィルタリング
                    for i in range(count):
                        ph = visible_inputs.nth(i).get_attribute("placeholder") or ""
                        logger.info(f"  input[{i}] placeholder: '{ph}'")
                        if "申請ID" in ph or "完全一致" in ph:
                            visible_inputs.nth(i).click()
                            visible_inputs.nth(i).fill(search_id)
                            filled = True
                            logger.info(f"input[{i}]に入力しました: {search_id}")
                            break
                    if not filled:
                        logger.warning("申請IDフィールドが見つかりません")
                        self._close_modal()
                        return

            self.page.wait_for_timeout(500)

            # Step 5: 「検索」ボタンをクリック
            # ページ全体から可視の「検索」ボタンを探す（.modalスコープに依存しない）
            clicked_search = self.page.evaluate("""() => {
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    const text = (btn.textContent || '').trim();
                    if (text === '検索' && btn.offsetParent !== null) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }""")
            if clicked_search:
                logger.info("「検索」ボタンをクリックしました（JS）")
            else:
                # Playwrightフォールバック
                search_btn = self.page.locator("button:has-text('検索'):visible")
                if search_btn.count() > 0:
                    search_btn.first.click()
                    logger.info("「検索」ボタンをクリックしました（locator）")
                else:
                    self.page.keyboard.press("Enter")
                    logger.info("Enterキーで検索を実行しました")
            self.page.wait_for_timeout(3000)

            # Step 6: 検索結果をクリックして選択する
            # Jobcanの申請書検索の検索結果はカード形式:
            #   「N件 の検索結果」
            #   【契約・発注稟議】 タイトル...    [完了] [詳細]
            #   ID：2308 申請日時：... 申請者：...
            # タイトル部分(またはカード全体)をクリックすると関連申請として選択される
            self.page.wait_for_timeout(500)
            clicked = False

            # 方法1: JavaScriptで検索結果を探してクリック
            try:
                clicked = self.page.evaluate(f"""() => {{
                    // ページ全体でIDテキストを含む要素を探す（.modalに依存しない）
                    const allElements = document.querySelectorAll('*');
                    let bestTarget = null;
                    let bestLen = Infinity;
                    for (const el of allElements) {{
                        // inputやbuttonは除外
                        if (['INPUT','BUTTON','SELECT','TEXTAREA'].includes(el.tagName)) continue;
                        // 非表示要素は除外
                        if (el.offsetParent === null && el.tagName !== 'BODY') continue;
                        const text = el.textContent || '';
                        // 「ID：{search_id}」または「ID : {search_id}」を含む
                        if ((text.includes('ID：{search_id}') || text.includes('ID : {search_id}')
                             || text.includes('ID:{search_id}'))
                            && !text.includes('件 の検索結果')
                            && text.length < bestLen
                            && text.length > 10) {{
                            // テキスト長が短い（＝より具体的な）要素を優先
                            bestLen = text.length;
                            bestTarget = el;
                        }}
                    }}
                    if (bestTarget) {{
                        // ng-clickを持つ祖先要素を探す
                        let target = bestTarget;
                        let p = bestTarget;
                        for (let i = 0; i < 8; i++) {{
                            if (p.getAttribute && p.getAttribute('ng-click')) {{
                                target = p;
                                break;
                            }}
                            p = p.parentElement;
                            if (!p) break;
                        }}
                        target.click();
                        return true;
                    }}
                    return false;
                }}""")
            except Exception as e:
                logger.warning(f"JS検索結果クリック失敗: {e}")
                clicked = False

            if clicked:
                self.page.wait_for_timeout(1500)
                logger.info(f"関連申請を選択しました: ID={search_id}")
            else:
                # 方法2: Playwrightセレクタでフォールバック
                fallback_selectors = [
                    "[ng-repeat*='request']",
                    "[ng-repeat*='result']",
                    "[ng-click*='select']",
                    ".modal tbody tr",
                ]
                for sel in fallback_selectors:
                    try:
                        result = modal.locator(sel)
                        if result.count() > 0 and result.first.is_visible():
                            result.first.click()
                            self.page.wait_for_timeout(1500)
                            clicked = True
                            logger.info(f"関連申請を選択しました（フォールバック）: ID={search_id}")
                            break
                    except Exception:
                        continue

            if not clicked:
                logger.warning(f"関連申請の検索結果が見つかりません: ID={search_id}")
                self._close_modal()
        except Exception as e:
            self._close_modal()
            logger.warning(f"関連申請の検索失敗 [{trigger_selector}]: {e}")

    def _search_vendor(self, trigger_selector: str, vendor_name: str):
        """取引先を検索・選択する。

        取引先検索ポップアップでテキスト検索して最初の結果を選択。
        """
        if not vendor_name:
            return
        try:
            # トリガー要素の隣にある検索ボタンをクリック
            trigger = self.page.locator(trigger_selector)
            search_trigger = self.page.locator(
                f'{trigger_selector} + button, '
                f'{trigger_selector} + .input-group-btn button, '
                f'{trigger_selector} ~ button'
            )
            if search_trigger.count() > 0 and search_trigger.first.is_visible():
                search_trigger.first.click()
            else:
                trigger.click()
            self._wait_for_modal()

            modal = self.page.locator(".modal.in, .modal.show, .modal[style*='display: block']")
            if modal.count() == 0:
                modal = self.page.locator(".modal")

            # 検索フィールドに入力
            search_input = modal.locator(
                "input[type='text'], input[type='search'], input:not([type])"
            ).first
            search_input.fill(vendor_name)

            # 検索ボタンまたはEnterで検索
            search_btn = modal.locator(
                "button:has-text('検索'), "
                "input[type='submit'][value*='検索'], "
                "a:has-text('検索')"
            )
            if search_btn.count() > 0:
                search_btn.first.click()
            else:
                search_input.press("Enter")
            self.page.wait_for_timeout(2500)

            # 検索結果の最初の行をクリック
            result_selectors = [
                "tbody tr td",
                "tbody tr",
                ".search-result-item",
                ".list-group-item",
                "table tr:not(:first-child)",
            ]
            for sel in result_selectors:
                result = modal.locator(sel)
                if result.count() > 0 and result.first.is_visible():
                    result.first.click()
                    self.page.wait_for_timeout(1000)
                    logger.info(f"取引先を選択しました: {vendor_name}")
                    return

            logger.warning(f"取引先の検索結果が見つかりません: {vendor_name}")
            self._close_modal()
        except Exception as e:
            self._close_modal()
            logger.warning(f"取引先検索失敗 [{trigger_selector}]: {e}")

    def _upload_file(self, pdf_path: str | Path):
        """ファイルを添付する。

        Jobcanのファイル添付フロー:
        1. 「添付ファイルを追加する」ボタンをクリック
        2. input[type="file"] にファイルをセット
        3. 「ファイル登録」ダイアログが表示される → 「登録する」ボタンをクリック
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {pdf_path}")

        try:
            # Step 1: 「添付ファイルを追加する」ボタンがあればクリック
            add_btn_selectors = [
                "button:has-text('添付ファイルを追加')",
                "a:has-text('添付ファイルを追加')",
                "button:has-text('添付ファイル')",
                "a:has-text('添付ファイル')",
                "button:has-text('ファイルを追加')",
                ".file-upload-btn",
                "button:has-text('ファイルを選択')",
            ]
            for sel in add_btn_selectors:
                btn = self.page.locator(sel)
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.click()
                    self.page.wait_for_timeout(1000)
                    break

            # Step 2: input[type="file"] にファイルをセット
            file_input = self.page.locator("input[type='file']").first
            file_input.set_input_files(str(pdf_path))
            self.page.wait_for_timeout(2000)
            logger.info(f"ファイルを選択しました: {pdf_path.name}")

            # Step 3: 「ファイル登録」ダイアログの「登録する」ボタンをクリック
            register_btn_selectors = [
                ".modal button:has-text('登録する')",
                ".modal button:has-text('登録')",
                "button:has-text('登録する')",
                ".modal input[type='submit'][value*='登録']",
                ".modal .btn-primary",
            ]
            for sel in register_btn_selectors:
                btn = self.page.locator(sel)
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.click()
                    self.page.wait_for_timeout(2000)
                    logger.info("「登録する」ボタンをクリックしました")
                    break
            else:
                logger.warning("「登録する」ボタンが見つかりません。ダイアログを手動で確認してください。")

            logger.info(f"ファイルを添付しました: {pdf_path.name}")
        except Exception as e:
            logger.warning(f"ファイル添付失敗: {e}")

    def take_screenshot(self, save_path: str | Path = None) -> bytes:
        """現在の画面のスクリーンショットを撮る"""
        if save_path:
            return self.page.screenshot(path=str(save_path), full_page=True)
        return self.page.screenshot(full_page=True)

    # ─── 契約・発注稟議フォーム入力 ───

    def fill_contract_form(self, form_data: dict, pdf_path: str | Path = None):
        """契約・発注稟議フォームにデータを入力する。

        Args:
            form_data: field_mapping.map_to_contract_form() の戻り値
            pdf_path: 添付する発注書PDFのパス
        """
        page = self.page
        logger.info("契約・発注稟議フォームへの入力を開始します")

        # 1. 申請タイトル
        logger.info("[1/19] 申請タイトルを入力中...")
        self._fill_text(CONTRACT_FIELDS["title"], form_data.get("title", ""))

        # 2. 稟議の種類 (checkbox)
        logger.info("[2/19] 稟議の種類を選択中...")
        ringi_type = form_data.get("ringi_type", "稟議")
        idx = CONTRACT_RINGI_TYPE.get(ringi_type, 0)
        self._click_checkbox_by_index("form_item3831493", idx)

        # 3. 契約締結日
        logger.info("[3/19] 契約締結日を入力中...")
        self._fill_date_field(
            CONTRACT_FIELDS["contract_date"],
            form_data.get("contract_date", ""),
        )

        # 4. 内容 (checkbox: 当社からの支払い/取引先からの受取)
        logger.info("[4/19] 内容を選択中...")
        content_type = form_data.get("content_type", "当社からの支払い（費用）")
        idx = CONTRACT_CONTENT_TYPE.get(content_type, 0)
        self._click_checkbox_by_index("form_item3818321", idx)

        # 5. 申請内容 (checkbox: 契約書/発注書/申込書/利用規約合意)
        logger.info("[5/19] 申請内容を選択中...")
        app_type = form_data.get("application_type", "発注書")
        idx = CONTRACT_APP_TYPE.get(app_type, 1)
        self._click_checkbox_by_index("form_item3818329", idx)

        # 6. 取引先種別(新規/既存)
        logger.info("[6/19] 取引先種別を選択中...")
        self._select_option(
            CONTRACT_FIELDS["vendor_status"],
            form_data.get("vendor_status", "string:既存"),
        )

        # 7. プロジェクトまたは予算項目名
        logger.info("[7/19] プロジェクト名を入力中...")
        self._fill_text(
            CONTRACT_FIELDS["project_name"],
            form_data.get("project_name", ""),
        )

        # 8. 予算関連備考
        logger.info("[8/19] 予算関連備考を入力中...")
        self._fill_text(
            CONTRACT_FIELDS["budget_note"],
            form_data.get("budget_note", ""),
        )

        # 9. 金額の範囲
        logger.info("[9/19] 金額の範囲を選択中...")
        self._select_option(
            CONTRACT_FIELDS["amount_range"],
            form_data.get("amount_range", "string:予算内"),
        )

        # 10. 発注額
        logger.info("[10/19] 発注額を入力中...")
        self._fill_number(
            CONTRACT_FIELDS["order_amount"],
            form_data.get("order_amount", ""),
        )

        # 11. 支払サイクル
        logger.info("[11/19] 支払サイクルを選択中...")
        self._select_option(
            CONTRACT_FIELDS["payment_cycle"],
            form_data.get("payment_cycle", "string:30日"),
        )

        # 12. 反社チェック (radio)
        logger.info("[12/19] 反社チェックを選択中...")
        self._click_radio(
            "form_item3818330",
            form_data.get("anti_social", "非上場企業（反社チェック実施）"),
        )

        # 13. 秘密保持契約書
        logger.info("[13/19] 秘密保持契約書を選択中...")
        self._select_option(
            CONTRACT_FIELDS["nda"],
            form_data.get("nda", "string:YES"),
        )

        # 14. 取引基本契約書
        logger.info("[14/19] 取引基本契約書を選択中...")
        self._select_option(
            CONTRACT_FIELDS["basic_agreement"],
            form_data.get("basic_agreement", "string:NO"),
        )

        # 15. 相見積もり (radio)
        logger.info("[15/19] 相見積もりを選択中...")
        self._click_radio(
            "form_item3822626",
            form_data.get("competitive_quote", "未"),
        )

        # 16. 締結方法 (radio)
        logger.info("[16/19] 締結方法を選択中...")
        self._click_radio(
            "form_item3818338",
            form_data.get("signing_method", "電子契約"),
        )

        # 17. リーガルチェック (radio)
        logger.info("[17/19] リーガルチェックを選択中...")
        self._click_radio(
            "form_item3831553",
            form_data.get("legal_check", "NO"),
        )

        # 18. 支払手段 (select)
        logger.info("[18/19] 支払手段を選択中...")
        self._select_option(
            CONTRACT_FIELDS["payment_method"],
            form_data.get("payment_method", "string:銀行振込"),
        )

        # 19. ファイル添付
        if pdf_path:
            logger.info("[19/19] 発注書を添付中...")
            self._upload_file(pdf_path)

        logger.info("契約・発注稟議フォームの入力完了")

    def _click_draft_button(self):
        """下書き保存ボタンをクリックする（共通）。

        Jobcanの下書き保存ボタンは画面下部にあり、
        「下書き保存」テキストを含むボタン。
        """
        draft_selectors = [
            "button:has-text('下書き保存')",
            "a:has-text('下書き保存')",
            "button.grayButton",
            "input[type='button'][value*='下書き']",
            "button[ng-click*='draft']",
        ]
        for sel in draft_selectors:
            btn = self.page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                self.page.wait_for_load_state("domcontentloaded")
                self.page.wait_for_timeout(3000)
                logger.info("下書き保存しました")
                return
        raise Exception("下書き保存ボタンが見つかりません")

    def save_contract_draft(self):
        """契約・発注稟議を下書き保存する"""
        try:
            self._click_draft_button()
            logger.info("契約・発注稟議を下書き保存しました")
        except Exception as e:
            logger.error(f"下書き保存失敗: {e}")
            raise

    # ─── 支払依頼フォーム入力 ───

    def fill_payment_form(self, form_data: dict, pdf_path: str | Path = None):
        """支払依頼/請求書フォームにデータを入力する。

        Args:
            form_data: field_mapping.map_to_payment_form() の戻り値
            pdf_path: 添付する請求書PDFのパス
        """
        page = self.page
        logger.info("支払依頼フォームへの入力を開始します")
        errors = []

        # 1. 申請タイトル
        logger.info("[1/14] 申請タイトルを入力中...")
        self._fill_text(PAYMENT_FIELDS["title"], form_data.get("title", ""))

        # 2. 関連申請の検索（URLから申請IDを抽出して検索）
        related_url = form_data.get("related_request_url", "")
        if related_url:
            logger.info("[2/14] 関連申請を検索中...")
            try:
                self._search_related_request(
                    PAYMENT_FIELDS["related_request"], related_url
                )
            except Exception as e:
                errors.append(f"関連申請の検索: {e}")
                logger.warning(f"関連申請の検索をスキップしました: {e}")

        # 3. 内容
        logger.info("[3/14] 内容を入力中...")
        self._fill_text(PAYMENT_FIELDS["content"], form_data.get("content", ""))

        # 4. 明細行: 計上日
        logger.info("[4/14] 計上日を入力中...")
        self._fill_date_field(
            PAYMENT_FIELDS["recording_date"],
            form_data.get("recording_date", ""),
        )

        # 5. 明細行: 金額
        logger.info("[5/14] 金額を入力中...")
        self._fill_number(
            PAYMENT_FIELDS["amount"],
            form_data.get("amount"),
        )

        # 6. 明細行: 内容
        logger.info("[6/14] 明細内容を入力中...")
        self._fill_text(
            PAYMENT_FIELDS["detail_content"],
            form_data.get("detail_content", ""),
        )

        # 7. 明細行: 取引先の検索
        vendor_name = form_data.get("vendor_name", "")
        if vendor_name:
            logger.info(f"[7/14] 取引先を検索中: {vendor_name}")
            try:
                self._search_vendor(
                    PAYMENT_FIELDS["vendor_search"], vendor_name
                )
            except Exception as e:
                errors.append(f"取引先の検索: {e}")
                logger.warning(f"取引先の検索をスキップしました: {e}")

        # 8. 明細行: 支払日
        logger.info("[8/14] 支払日を入力中...")
        self._fill_date_field(
            PAYMENT_FIELDS["payment_date"],
            form_data.get("payment_date", ""),
        )

        # 9. 明細行: 振込手数料
        logger.info("[9/14] 振込手数料を設定中...")
        self._select_option(
            PAYMENT_FIELDS["transfer_fee"],
            form_data.get("transfer_fee", "0"),
        )

        # 10. 明細行: 源泉徴収税
        logger.info("[10/14] 源泉徴収税を設定中...")
        self._select_option(
            PAYMENT_FIELDS["withholding_tax"],
            form_data.get("withholding_tax", "0"),
        )

        # 11. 決済方法 (radio)
        logger.info("[11/14] 決済方法を選択中...")
        self._click_radio(
            "form_item3818255",
            form_data.get("settlement_method", "銀行振込"),
        )

        # 12. 取引先種別 (radio)
        logger.info("[12/14] 取引先種別を選択中...")
        self._click_radio(
            "form_item3954869",
            form_data.get("vendor_type", "法人"),
        )

        # 13. 通貨 (radio)
        logger.info("[13/14] 通貨を選択中...")
        self._click_radio(
            "form_item3818256",
            form_data.get("currency", "円"),
        )

        # 14. 請求書ファイル添付
        if pdf_path:
            logger.info("[14/14] 請求書を添付中...")
            self._upload_file(pdf_path)

        if errors:
            logger.warning(f"支払依頼フォーム入力完了（一部スキップ: {len(errors)}件）")
            for err in errors:
                logger.warning(f"  - {err}")
        else:
            logger.info("支払依頼フォームの入力完了")

    def save_payment_draft(self):
        """支払依頼を下書き保存する"""
        try:
            self._click_draft_button()
            logger.info("支払依頼を下書き保存しました")
        except Exception as e:
            logger.error(f"下書き保存失敗: {e}")
            raise
