#!/usr/bin/env bash
set -euo pipefail

# Stream the complete GGUF release from Hugging Face to S3 without staging the
# whole model on the source machine. A single bounded temporary chunk is used
# for each multipart upload part.

BUCKET="${1:?usage: $0 BUCKET PREFIX}"
PREFIX="${2:?usage: $0 BUCKET PREFIX}"
REGION="${AWS_DEFAULT_REGION:-us-east-2}"
SOURCE_BASE="https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF/resolve/main"
PART_SIZE=$((128 * 1024 * 1024))
MIN_MULTIPART_SIZE=$((5 * 1024 * 1024))
RESUME_UPLOAD_ID="${RESUME_UPLOAD_ID:-}"
RESUME_KEY="${RESUME_KEY:-}"

export AWS_DEFAULT_REGION="$REGION"
export AWS_SDK_UA_APP_ID="${AWS_SDK_UA_APP_ID:-AWSSkill-SageMaker}"

WORK_DIR="$(mktemp -d /tmp/aegis-hf-s3-upload.XXXXXX)"
ACTIVE_UPLOAD_ID=""
ACTIVE_KEY=""

cleanup() {
  if [[ -n "$ACTIVE_UPLOAD_ID" ]]; then
    aws s3api abort-multipart-upload \
      --bucket "$BUCKET" \
      --key "$ACTIVE_KEY" \
      --upload-id "$ACTIVE_UPLOAD_ID" >/dev/null 2>&1 || true
  fi
  find "$WORK_DIR" -mindepth 1 -maxdepth 1 -type f -delete
  rmdir "$WORK_DIR"
}
trap cleanup EXIT

files=(
  ".gitattributes"
  "FastMTP-PROVENANCE.json"
  "FastMTP-PROVENANCE.json.sig"
  "HauhauCS-FastMTP-Ed25519-PUBLIC.pem"
  "HauhauCS-FastMTP-llama.cpp.patch"
  "HauhauCS-RELEASE-MANIFEST.json"
  "HauhauCS-RELEASE-MANIFEST.json.sig"
  "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf"
  "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ2_M.gguf"
  "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ3_M.gguf"
  "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ3_XS.gguf"
  "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-IQ4_XS.gguf"
  "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q2_K_P.gguf"
  "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q3_K_P.gguf"
  "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q4_K_P.gguf"
  "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q5_K_P.gguf"
  "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q6_K_P.gguf"
  "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q8_K_P.gguf"
  "README.md"
  "SHA256SUMS"
  "mmproj-Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-BF16.gguf"
)

remote_size() {
  local file="$1"
  curl -fsSIL --retry 4 --retry-all-errors "$SOURCE_BASE/$file?download=true" \
    | awk 'BEGIN { IGNORECASE=1 } /^x-linked-size:/ { gsub("\\r", ""); size=$2 } /^content-length:/ { gsub("\\r", ""); if ($2 != "0") size=$2 } END { if (size == "") exit 1; print size }' \
    | tail -n 1
}

upload_small() {
  local file="$1"
  local key="$PREFIX/$file"
  local local_file="$WORK_DIR/small"
  curl -fsSL --retry 4 --retry-all-errors "$SOURCE_BASE/$file?download=true" -o "$local_file"
  aws s3 cp "$local_file" "s3://$BUCKET/$key" \
    --region "$REGION" \
    --sse AES256 \
    --only-show-errors
  printf 'uploaded %s (%s bytes)\n' "$key" "$(stat -c '%s' "$local_file")"
}

upload_large() {
  local file="$1"
  local key="$PREFIX/$file"
  local total="$2"
  local upload_id
  local parts_file="$WORK_DIR/parts"
  local chunk="$WORK_DIR/chunk"
  local start
  local part_number
  : > "$parts_file"

  if [[ "$key" == "$RESUME_KEY" && -n "$RESUME_UPLOAD_ID" ]]; then
    upload_id="$RESUME_UPLOAD_ID"
    local expected_part=1
    local existing_part existing_etag
    while read -r existing_part existing_etag; do
      [[ -z "$existing_part" ]] && continue
      if [[ "$existing_part" != "$expected_part" ]]; then
        printf 'cannot resume non-contiguous multipart upload for %s\n' "$key" >&2
        return 1
      fi
      existing_etag="${existing_etag#\"}"
      existing_etag="${existing_etag%\"}"
      printf '{"ETag":"%s","PartNumber":%s}\n' "$existing_etag" "$existing_part" >> "$parts_file"
      expected_part=$((expected_part + 1))
    done < <(aws s3api list-parts \
      --bucket "$BUCKET" \
      --key "$key" \
      --region "$REGION" \
      --upload-id "$upload_id" \
      --query 'Parts[].[PartNumber,ETag]' \
      --output text)
    start=$(((expected_part - 1) * PART_SIZE))
    part_number="$expected_part"
    printf 'resuming %s at part %s (%s bytes already staged)\n' "$key" "$part_number" "$start"
  else
    upload_id="$(aws s3api create-multipart-upload \
      --bucket "$BUCKET" \
      --key "$key" \
      --region "$REGION" \
      --server-side-encryption AES256 \
      --metadata source="Hugging Face: HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF" \
      --query UploadId \
      --output text)"
    start=0
    part_number=1
  fi
  ACTIVE_UPLOAD_ID="$upload_id"
  ACTIVE_KEY="$key"

  while (( start < total )); do
    local end=$((start + PART_SIZE - 1))
    if (( end >= total )); then
      end=$((total - 1))
    fi
    local expected=$((end - start + 1))

    curl -fsSL --retry 4 --retry-all-errors \
      --range "$start-$end" \
      "$SOURCE_BASE/$file?download=true" \
      -o "$chunk"
    local actual
    actual="$(stat -c '%s' "$chunk")"
    if [[ "$actual" != "$expected" ]]; then
      printf 'range size mismatch for %s part %s: expected %s, got %s\n' \
        "$file" "$part_number" "$expected" "$actual" >&2
      return 1
    fi

    local etag
    etag="$(aws s3api upload-part \
      --bucket "$BUCKET" \
      --key "$key" \
      --region "$REGION" \
      --upload-id "$upload_id" \
      --part-number "$part_number" \
      --body "$chunk" \
      --query ETag \
      --output text)"
    etag="${etag#\"}"
    etag="${etag%\"}"
    printf '{"ETag":"%s","PartNumber":%s}\n' "$etag" "$part_number" >> "$parts_file"

    printf 'uploaded %s part %s (%s-%s of %s bytes)\n' \
      "$file" "$part_number" "$start" "$end" "$total"
    start=$((end + 1))
    part_number=$((part_number + 1))
  done

  local parts_json
  parts_json="$(paste -sd, "$parts_file")"
  aws s3api complete-multipart-upload \
    --bucket "$BUCKET" \
    --key "$key" \
    --region "$REGION" \
    --upload-id "$upload_id" \
    --multipart-upload "{\"Parts\":[${parts_json}]}" >/dev/null
  ACTIVE_UPLOAD_ID=""
  ACTIVE_KEY=""

  local stored
  stored="$(aws s3api head-object --bucket "$BUCKET" --key "$key" --region "$REGION" --query ContentLength --output text)"
  if [[ "$stored" != "$total" ]]; then
    printf 'post-upload size mismatch for %s: expected %s, got %s\n' "$key" "$total" "$stored" >&2
    return 1
  fi
  printf 'verified %s (%s bytes)\n' "$key" "$stored"
}

aws s3api head-bucket --bucket "$BUCKET" --region "$REGION"
printf 'source=%s\n' "$SOURCE_BASE"
printf 'destination=s3://%s/%s\n' "$BUCKET" "$PREFIX"
printf 'part_size=%s MiB\n' "$((PART_SIZE / 1024 / 1024))"

for file in "${files[@]}"; do
  if aws s3api head-object --bucket "$BUCKET" --key "$PREFIX/$file" --region "$REGION" >/dev/null 2>&1; then
    printf 'already verified, skipping %s\n' "$PREFIX/$file"
    continue
  fi
  total="$(remote_size "$file")"
  if (( total >= MIN_MULTIPART_SIZE )); then
    upload_large "$file" "$total"
  else
    upload_small "$file"
  fi
done

printf 'complete: s3://%s/%s\n' "$BUCKET" "$PREFIX"
