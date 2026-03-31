#!/bin/bash
# ============================================
# Jobcan自動入力システム - サーバーセットアップスクリプト
# 対象: Ubuntu 20.04+ / CentOS 7+
# ============================================

set -e

echo "=========================================="
echo " Jobcan自動入力システム セットアップ"
echo "=========================================="

# ---------- OS判定 ----------
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    OS="unknown"
fi

echo "OS: $OS"

# ---------- Python 3.10+ インストール ----------
install_python() {
    echo ">>> Python 3.10+ をインストール中..."
    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        sudo apt-get update
        sudo apt-get install -y software-properties-common
        sudo add-apt-repository -y ppa:deadsnakes/ppa
        sudo apt-get update
        sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
        PYTHON=python3.11
    elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ]; then
        sudo yum install -y epel-release
        sudo yum install -y python3 python3-devel python3-pip
        PYTHON=python3
    else
        echo "未対応OS: $OS"
        exit 1
    fi
    echo "Python: $($PYTHON --version)"
}

# ---------- Playwright依存ライブラリ (headless Chromium) ----------
install_playwright_deps() {
    echo ">>> Playwright依存ライブラリをインストール中..."
    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        sudo apt-get install -y \
            libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
            libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
            libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
            libcairo2 libasound2 libatspi2.0-0 libwayland-client0 \
            fonts-noto-cjk
    elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ]; then
        sudo yum install -y \
            nss nspr atk at-spi2-atk cups-libs libdrm \
            libxkbcommon libXcomposite libXdamage libXfixes \
            libXrandr mesa-libgbm pango cairo alsa-lib \
            google-noto-sans-cjk-fonts
    fi
}

# ---------- アプリケーションセットアップ ----------
setup_app() {
    echo ">>> アプリケーションをセットアップ中..."

    # アプリディレクトリ
    APP_DIR="/opt/jobcan-auto"
    sudo mkdir -p $APP_DIR
    sudo chown $USER:$USER $APP_DIR

    # ファイルをコピー（このスクリプトの親ディレクトリから）
    SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
    cp -r "$SCRIPT_DIR/src" "$APP_DIR/"
    cp "$SCRIPT_DIR/app.py" "$APP_DIR/"
    cp "$SCRIPT_DIR/pyproject.toml" "$APP_DIR/"

    # .envファイル作成（APIキーのみ。Jobcan認証は各ユーザーがUI上で入力）
    if [ ! -f "$APP_DIR/.env" ]; then
        echo "# Gemini API Key（共通）" > "$APP_DIR/.env"
        echo "GEMINI_API_KEY=YOUR_API_KEY_HERE" >> "$APP_DIR/.env"
        echo ""
        echo "⚠️  $APP_DIR/.env にGemini APIキーを設定してください"
    fi

    # venv作成 & 依存インストール
    cd $APP_DIR
    $PYTHON -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install playwright google-genai streamlit Pillow python-dotenv

    # Playwright ブラウザインストール
    .venv/bin/playwright install chromium
    .venv/bin/playwright install-deps chromium 2>/dev/null || true

    echo ">>> アプリケーションのセットアップ完了"
}

# ---------- systemdサービス登録 ----------
setup_service() {
    echo ">>> systemdサービスを登録中..."

    sudo tee /etc/systemd/system/jobcan-auto.service > /dev/null << 'SYSTEMD_EOF'
[Unit]
Description=Jobcan自動入力システム (Streamlit)
After=network.target

[Service]
Type=simple
User=mikaiadmin
WorkingDirectory=/opt/jobcan-auto
Environment=PATH=/opt/jobcan-auto/.venv/bin:/usr/bin:/bin
ExecStart=/opt/jobcan-auto/.venv/bin/python -m streamlit run app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

    sudo systemctl daemon-reload
    sudo systemctl enable jobcan-auto
    sudo systemctl start jobcan-auto

    echo ">>> サービスが起動しました"
}

# ---------- 実行 ----------
install_python
install_playwright_deps
setup_app
setup_service

# サーバーIPを表示
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "=========================================="
echo " ✅ セットアップ完了!"
echo "=========================================="
echo ""
echo " アクセスURL: http://${SERVER_IP}:8501"
echo ""
echo " 社内の全員がブラウザからアクセス可能です。"
echo " 各ユーザーは画面左のサイドバーで"
echo " 自分のJobcanメール/パスワードを入力して使います。"
echo ""
echo " サービス管理:"
echo "   起動:   sudo systemctl start jobcan-auto"
echo "   停止:   sudo systemctl stop jobcan-auto"
echo "   状態:   sudo systemctl status jobcan-auto"
echo "   ログ:   sudo journalctl -u jobcan-auto -f"
echo "=========================================="
