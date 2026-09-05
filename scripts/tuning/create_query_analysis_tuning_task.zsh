#!/usr/bin/env zsh

# 질문 답변용 HyperCLOVA 튜닝 작업을 생성합니다.
# 키를 환경변수에 넣지 않았다면 실행 중에 숨김 입력으로 받습니다.

set -euo pipefail

if [[ -z "${CLOVA_API_KEY:-}" ]]; then
  read -r -s "CLOVA_API_KEY?CLOVA Studio API 키 입력: "
  echo
fi

if [[ -z "${NCP_OBJECT_ACCESS_KEY:-}" ]]; then
  read -r -s "NCP_OBJECT_ACCESS_KEY?Object Storage Access Key 입력: "
  echo
fi

if [[ -z "${NCP_OBJECT_SECRET_KEY:-}" ]]; then
  read -r -s "NCP_OBJECT_SECRET_KEY?Object Storage Secret Key 입력: "
  echo
fi

REQUEST_ID="${REQUEST_ID:-$(uuidgen)}"
TUNING_BUCKET="${TUNING_BUCKET:-tuningdata1}"
TUNING_FILE_PATH="${TUNING_FILE_PATH:-hyperclova_answer_train_457.jsonl}"
TUNING_MODEL="${TUNING_MODEL:-HCX-DASH-002}"

curl --fail-with-body --location --request POST \
  'https://clovastudio.stream.ntruss.com/tuning/v2/tasks' \
  --header 'Content-Type: application/json' \
  --header "Authorization: Bearer ${CLOVA_API_KEY}" \
  --header "X-NCP-CLOVASTUDIO-REQUEST-ID: ${REQUEST_ID}" \
  --data @- <<JSON
{
  "name": "pension-query-answer-v1",
  "model": "${TUNING_MODEL}",
  "tuningType": "PEFT",
  "trainEpochs": "4",
  "learningRate": "1.0E-5",
  "validationSplitRatio": 0.1,
  "loraR": 8,
  "loraAlpha": 64,
  "trainingDatasetBucket": "${TUNING_BUCKET}",
  "trainingDatasetFilePath": "${TUNING_FILE_PATH}",
  "trainingDatasetAccessKey": "${NCP_OBJECT_ACCESS_KEY}",
  "trainingDatasetSecretKey": "${NCP_OBJECT_SECRET_KEY}"
}
JSON
