#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 RESULT_FILE OUTPUT_FILE REVIEWER MODEL" >&2
  exit 2
fi

result_file=$1
output_file=$2
reviewer=$3
model=$4

jq -e '
  (type == "object") and
  (.description | type == "string" and length > 0 and length <= 500 and (test("[\\r\\n]") | not)) and
  (.result_status | IN("COMPLETE", "INCOMPLETE")) and
  (.comment_body | type == "string" and length > 0 and length <= 60000)
' "$result_file" > /dev/null

jq -c --arg reviewer "$reviewer" --arg model "$model" \
  '. + {reviewer: $reviewer, model: $model}' "$result_file" > "$output_file"

# A schema-valid soft failure must trigger the independent fallback.
jq -e '.result_status == "COMPLETE"' "$output_file" > /dev/null
