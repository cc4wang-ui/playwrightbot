# Payment Request Form URL & Related Request Linking Logic

## 1. Payment Request Form URL

Defined in `src/config.py`:

```python
JOBCAN_BASE_URL = "https://ssl.wf.jobcan.jp"
JOBCAN_PAYMENT_FORM_ID = "666591"   # Payment Request / Invoice Submission
```

The actual form URL is constructed in `src/jobcan_filler.py` → `navigate_to_new_payment()`:

```
https://ssl.wf.jobcan.jp/#/request/new/666591/
```

> **Note:** The Contract/Purchase Order Approval form uses a separate Form ID `666628`:
> `https://ssl.wf.jobcan.jp/#/request/new/666628/`

---

## 2. Related Request Linking Logic

The payment request form supports linking to a previously approved **Contract/Purchase Order Approval** request. This is handled by the `_search_related_request()` method in `src/jobcan_filler.py`.

### Overview (Data Flow)

```
app.py (Streamlit UI)
  │  User inputs the Jobcan URL of the approved Contract/Purchase Order
  │  e.g. "https://ssl.wf.jobcan.jp/#/requests/2308"
  ▼
src/field_mapping.py — map_to_payment_form()
  │  Stores the URL as `related_request_url` in the form data dict
  ▼
src/jobcan_filler.py — fill_payment_form()
  │  Calls _search_related_request() with the URL
  ▼
_search_related_request()
  │  Extracts the request ID from the URL, searches and selects it in the Jobcan modal
  ▼
Jobcan form: Related request is linked
```

### Step-by-Step Process

#### Step 1 — Extract Request ID from URL

The method uses a regex to extract the numeric ID from the Jobcan URL:

```python
# Regex: /requests?/(\d+)
# Example: "https://ssl.wf.jobcan.jp/#/requests/2308" → "2308"
match = re.search(r"/requests?/(\d+)", url_or_id)
search_id = match.group(1) if match else url_or_id
```

If the input is already a plain numeric ID (not a URL), it is used as-is.

#### Step 2 — Select "Link" Radio Button

Jobcan's payment request form has a radio button pair: **紐付する (Link)** / **紐付しない (Don't Link)**.

The automation clicks "紐付する" to reveal the related request search field:

```python
# Selectors tried (in order):
#   input[type='radio'][value='bind']
#   label:has-text('紐付する') input[type='radio']
#   input[ng-model*='related'][value='true']
```

#### Step 3 — Open Search Modal & Enter Request ID

1. Click the search trigger button next to `input[name="related_request_view_id"]`
2. Wait for the modal dialog to appear
3. Expand "詳細検索" (Advanced Search) section if collapsed
4. Locate the "申請ID (完全一致)" (Request ID, exact match) input field
5. Fill in the extracted request ID (e.g. `2308`)

> The input is done via JavaScript (`evaluate`) to properly trigger AngularJS data binding (`$apply`).

#### Step 4 — Execute Search

Click the "検索" (Search) button inside the modal. Falls back to pressing Enter if the button is not found.

#### Step 5 — Select Search Result

The search results appear as cards with format:

```
【契約・発注稟議】 Title...    [完了] [詳細]
ID：2308  申請日時：...  申請者：...
```

The automation:
1. Scans all visible elements for text containing `ID：{search_id}`
2. Traverses up to 8 ancestor elements to find one with `ng-click` attribute
3. Clicks the `ng-click` element to select the related request
4. Falls back to Playwright selectors (`[ng-repeat*='request']`, `.modal tbody tr`, etc.) if JS approach fails

---

## 3. Key Files Reference

| File | Role |
|---|---|
| `src/config.py` | Base URL, Form IDs, credentials (env vars) |
| `src/field_mapping.py` | Maps PDF-extracted data → Jobcan form fields; defines all CSS selectors & field constants |
| `src/jobcan_filler.py` | Playwright-based browser automation: login, navigation, form filling, related request search |
| `app.py` | Streamlit Web UI: PDF upload → Gemini extraction → preview → auto-fill |

## 4. Form Field Mapping (Payment Request — Form ID: 666591)

| Field | HTML name | Type |
|---|---|---|
| Title | `title` | text |
| Related Request | `related_request_view_id` | text + search popup |
| Content | `pay_content` | textarea |
| Breakdown | `account_title_part_0_0` | text + popup |
| Recording Date | `allocation_date_0_0` | calendar |
| Amount | `specifics_amount_0_0` | number |
| Detail Content | `pay_content_0_0` | text |
| Vendor | `company_0_0` | text + search popup |
| Payment Date | `payment_date_0_0` | calendar |
| Transfer Fee | `bank_transfer_fee_type_0_0` | select (0=Payer / 1=Payee) |
| Withholding Tax | `withholding_tax_calc_0_0` | select (0=None / 2=Pre-tax / 1=Post-tax) |
| Group | `specifics_group_0_0` | text + popup |
| Project | `specifics_project_0_0` | text + popup |
| Settlement Method | `form_item3818255` | radio |
| Vendor Type | `form_item3954869` | radio |
| Currency | `form_item3818256` | radio |
