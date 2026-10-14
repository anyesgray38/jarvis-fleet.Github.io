#!/usr/bin/env bash
set -euo pipefail

BUCKET="${1:?usage: $0 BUCKET PREFIX EXPECTED_TOTAL_BYTES}"
PREFIX="${2:?usage: $0 BUCKET PREFIX EXPECTED_TOTAL_BYTES}"
EXPECTED_TOTAL_BYTES="${3:?usage: $0 BUCKET PREFIX EXPECTED_TOTAL_BYTES}"
REGION="${AWS_DEFAULT_REGION:-us-east-2}"
MARKER_KEY="$PREFIX/.aegis-upload-complete.json"
MARKER_FILE="$(mktemp /tmp/aegis-upload-complete.XXXXXX)"

export AWS_DEFAULT_REGION="$REGION"
export AWS_SDK_UA_APP_ID="${AWS_SDK_UA_APP_ID:-AWSSkill-AWSCloudFormation}"

cleanup() {
  find "$(dirname "$MARKER_FILE")" -maxdepth 1 -name "$(basename "$MARKER_FILE")" -type f -delete
}
trap cleanup EXIT

while true; do
  active_upload_ids="$(aws s3api list-multipart-uploads \
    --bucket "$BUCKET" \
    --prefix "$PREFIX/" \
    --query 'Uploads[].UploadId' \
    --output text)"
  active_count=0
  if [[ -n "$active_upload_ids" && "$active_upload_ids" != "None" ]]; then
    active_count=1
  fi
  object_bytes="$(aws s3api list-objects-v2 \
    --bucket "$BUCKET" \
    --prefix "$PREFIX/" \
    --query 'sum(Contents[].Size)' \
    --output text)"
  uploader_running=0
  if pgrep -f '/tmp/aegis-upload-hf-gguf-to-s3.sh' >/dev/null 2>&1; then
    uploader_running=1
  fi

  if [[ "$active_count" == "0" && "$object_bytes" == "$EXPECTED_TOTAL_BYTES" ]]; then
    completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf '{"status":"complete","completed_at_utc":"%s","bucket":"%s","prefix":"%s","bytes":%s}\n' \
      "$completed_at" "$BUCKET" "$PREFIX" "$object_bytes" > "$MARKER_FILE"
    aws s3api put-object \
      --bucket "$BUCKET" \
      --key "$MARKER_KEY" \
      --region "$REGION" \
      --body "$MARKER_FILE" \
      --server-side-encryption AES256 >/dev/null
    printf 'upload finalized at %s\n' "$completed_at"
    exit 0
  fi

  if [[ "$uploader_running" == "0" && "$active_count" == "0" ]]; then
    printf 'uploader stopped before completion: objects=%s expected=%s\n' "$object_bytes" "$EXPECTED_TOTAL_BYTES" >&2
    exit 1
  fi
  sleep 120
done
