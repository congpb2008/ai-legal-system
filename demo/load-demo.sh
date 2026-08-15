#!/usr/bin/env bash
# Load the demo dataset into a running Legal Knowledge Platform instance.
#
# Prerequisites:
#   - The server is running (see docs/user-guide/en/02-quick-start.md)
#   - curl and python3 are available
#
# Usage:
#   bash demo/load-demo.sh [BASE_URL]
#
# Default BASE_URL: http://localhost:8080
#
# This script:
#   1. Logs in (any credentials work in the MVP)
#   2. Creates a demo vault "Demo Legal Documents" (DEPARTMENT)
#   3. Uploads the sample decision document
#
# Note: The MVP does not automatically process uploaded documents. After
# upload, the document is registered but may not be searchable until
# processing is manually triggered via the Admin panel (⚙️ Quản trị).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="${1:-http://localhost:8080}"
USERNAME="${DEMO_USERNAME:-admin}"
PASSWORD="${DEMO_PASSWORD:-admin}"
DOC_FILE="${SCRIPT_DIR}/sample-decision-15-2026.pdf"

echo "=== Legal Knowledge Platform — Demo Dataset Loader ==="
echo "Base URL: ${BASE_URL}"
echo "Document: ${DOC_FILE}"

if [ ! -f "${DOC_FILE}" ]; then
  echo "ERROR: Sample document not found: ${DOC_FILE}"
  echo "Generate it first with: python3 demo/generate-sample-doc.py"
  exit 1
fi

# 1. Login
echo ""
echo "[1/3] Logging in as '${USERNAME}'..."
LOGIN_RESP=$(curl -s -X POST "${BASE_URL}/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"${USERNAME}\", \"password\": \"${PASSWORD}\"}")

TOKEN=$(echo "${LOGIN_RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token'])" 2>/dev/null || echo "")
if [ -z "${TOKEN}" ]; then
  echo "ERROR: Login failed. Is the server running at ${BASE_URL}?"
  echo "Response: ${LOGIN_RESP}"
  exit 1
fi
echo "  Login OK."

# 2. Create vault
echo "[2/3] Creating demo vault..."
VAULT_RESP=$(curl -s -X POST "${BASE_URL}/api/v1/vaults" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"name": "Demo Legal Documents", "vault_type": "DEPARTMENT", "description": "Demo dataset for the Legal Knowledge Platform"}')

VAULT_ID=$(echo "${VAULT_RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])" 2>/dev/null || echo "")
if [ -z "${VAULT_ID}" ]; then
  echo "ERROR: Vault creation failed."
  echo "Response: ${VAULT_RESP}"
  exit 1
fi
echo "  Vault created: ${VAULT_ID}"

# 3. Upload document
echo "[3/3] Uploading sample document..."
BASE64=$(base64 -w0 "${DOC_FILE}")
UPLOAD_RESP=$(curl -s -X POST "${BASE_URL}/api/v1/uploads" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d "{
    \"filename\": \"sample-decision-15-2026.pdf\",
    \"content_base64\": \"${BASE64}\",
    \"title\": \"Quyết định 15/2026/QĐ-NH — Quy chế mua sắm máy chủ\",
    \"document_type\": \"DECISION\",
    \"issuing_authority\": \"Ngân hàng Nhà nước Việt Nam\",
    \"document_number\": \"15/2026/QĐ-NH\",
    \"vault_id\": \"${VAULT_ID}\"
  }")

DOC_ID=$(echo "${UPLOAD_RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['document_id'])" 2>/dev/null || echo "")
if [ -z "${DOC_ID}" ]; then
  echo "ERROR: Upload failed."
  echo "Response: ${UPLOAD_RESP}"
  exit 1
fi
echo "  Document uploaded: ${DOC_ID}"

echo ""
echo "=== Demo dataset loaded successfully ==="
echo ""
echo "Next steps:"
echo "  1. Open the Web UI: ${BASE_URL}"
echo "  2. The document is registered but NOT yet searchable (MVP limitation)."
echo "  3. To make it searchable, trigger processing via the Admin panel:"
echo "     - Go to ⚙️ Quản trị (Admin)"
echo "     - Click Re-index, Re-embed, and Re-parse"
echo "  4. Then search for: 'quy định mua sắm máy chủ'"
echo ""
echo "Suggested demo questions:"
echo "  - 'Quy định cấu hình tối thiểu của máy chủ là gì?'"
echo "  - 'Trách nhiệm của Phòng Công nghệ Thông tin là gì?'"
echo "  - 'Gói thầu nào phải được Tổng Giám đốc phê duyệt?'"