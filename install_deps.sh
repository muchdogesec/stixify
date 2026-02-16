
set -e
python -m playwright install --with-deps chromium  --only-shell
apt update
apt install -y libreoffice
