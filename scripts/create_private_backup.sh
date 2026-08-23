#!/usr/bin/env bash
# إنشاء نسخة احتياطية مشفرة محلياً لـANTER. لا يطبع أو يحفظ كلمة مرور الأرشيف.
set -euo pipefail

show_help() {
  cat <<'EOF'
الاستخدام:
  bash scripts/create_private_backup.sh

ينشئ السكربت أرشيف 7z مشفراً في:
  ~/anter-private-backups/

يشمل ملفات المشروع، ملف البيئة المحلي إن وجد، قاعدة SQLite المحلية إن وجدت،
وسجل Git الكامل. لا يشمل قاعدة بيانات Render البعيدة.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  show_help
  exit 0
fi

if ! command -v 7z >/dev/null 2>&1; then
  if command -v pkg >/dev/null 2>&1; then
    echo 'جارٍ تثبيت p7zip اللازم لإنشاء الأرشيف المشفّر...'
    pkg install -y p7zip
  else
    echo 'تعذر العثور على 7z. ثبّت p7zip ثم أعد تشغيل السكربت.' >&2
    exit 1
  fi
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="${ANTER_BACKUP_DIR:-$HOME/anter-private-backups}"
ARCHIVE="$BACKUP_DIR/ANTER-private-backup-$STAMP.7z"

umask 077
mkdir -p "$BACKUP_DIR"
STAGING_DIR="$(mktemp -d "$BACKUP_DIR/.staging-$STAMP-XXXXXX")"

cleanup() {
  rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

mkdir -p "$STAGING_DIR/project-files"

# يحفظ مصدر المشروع بلا عناصر التشغيل المؤقتة أو الأسرار أو سجل Git المضمن منفصلاً.
tar -C "$PROJECT_DIR" \
  --exclude='.git' \
  --exclude='.env' \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='logs' \
  --exclude='instance/anter.db' \
  -cf - . | tar -C "$STAGING_DIR/project-files" -xf -

# يحفظ ملف البيئة منفصلاً وبصلاحية المالك فقط، إن كان موجوداً محلياً.
if [[ -f "$PROJECT_DIR/.env" ]]; then
  cp "$PROJECT_DIR/.env" "$STAGING_DIR/anter.env"
  chmod 600 "$STAGING_DIR/anter.env"
fi

# يحفظ قاعدة SQLite المحلية فقط. لا يمكنه نسخ PostgreSQL على Render من دون بيانات اتصال.
if [[ -f "$PROJECT_DIR/instance/anter.db" ]]; then
  cp "$PROJECT_DIR/instance/anter.db" "$STAGING_DIR/anter-local.db"
  chmod 600 "$STAGING_DIR/anter-local.db"
fi

# يحفظ سجل Git الكامل كملف bundle لاستعادته عند الضرورة.
git -C "$PROJECT_DIR" bundle create "$STAGING_DIR/ANTER-full-history.bundle" --all

printf 'اكتب كلمة مرور قوية للنسخة الاحتياطية (لن تظهر أثناء الكتابة): '
IFS= read -r -s BACKUP_PASSWORD
printf '\n'

if [[ -z "$BACKUP_PASSWORD" ]]; then
  echo 'ألغيت: كلمة مرور النسخة الاحتياطية لا يمكن أن تكون فارغة.' >&2
  exit 1
fi

echo 'جارٍ إنشاء الأرشيف المشفّر والتحقق من سلامته...'
7z a -t7z -mhe=on -p"$BACKUP_PASSWORD" "$ARCHIVE" "$STAGING_DIR" >/dev/null
7z t -p"$BACKUP_PASSWORD" "$ARCHIVE" >/dev/null
unset BACKUP_PASSWORD

echo 'تم إنشاء نسخة مشفّرة بنجاح.'
echo "المسار: $ARCHIVE"
ls -lh "$ARCHIVE"
echo 'انسخ هذا الملف إلى مكان خاص خارج الهاتف، ولا تشارك كلمة مرور الأرشيف.'
