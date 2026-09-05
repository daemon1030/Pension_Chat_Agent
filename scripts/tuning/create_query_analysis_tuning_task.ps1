[CmdletBinding()]
param(
    [string]$ClovaApiKey = $env:CLOVA_API_KEY,
    [string]$ObjectAccessKey = $env:NCP_OBJECT_ACCESS_KEY,
    [string]$ObjectSecretKey = $env:NCP_OBJECT_SECRET_KEY,
    [string]$TuningBucket = $env:TUNING_BUCKET,
    [string]$TuningFilePath = $env:TUNING_FILE_PATH,
    [string]$TuningModel = $env:TUNING_MODEL,
    [string]$TaskName = "pension-query-answer-v1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Paste the three values below for local execution only. Do not commit this file afterward.
$EmbeddedClovaApiKey = "nv-ef4f66f68e3b40e2ad75955ac41d31e90qOE"
$EmbeddedObjectAccessKey = "ncp_iam_BPAMKR3Dq4TEdyr8OFGE"
$EmbeddedObjectSecretKey = "ncp_iam_BPKMKRFKBY7f9mX9MHVrX1gYZ0HJ86jneq"

function Read-SecretValue {
    param([Parameter(Mandatory = $true)][string]$Prompt)

    $secureValue = Read-Host -Prompt $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Get-DotEnvValue {
    param([Parameter(Mandatory = $true)][string]$Name)

    $envPath = Join-Path $PSScriptRoot "..\..\.env"
    if (-not (Test-Path -LiteralPath $envPath)) {
        return $null
    }

    $pattern = "^\s*{0}\s*=\s*(.*)\s*$" -f [regex]::Escape($Name)
    foreach ($line in Get-Content -LiteralPath $envPath -Encoding UTF8) {
        if ($line -match $pattern) {
            return $Matches[1]
        }
    }
    return $null
}

function Normalize-RequestValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )

    # Credential values cannot contain control characters. Clipboard pastes may include them.
    $normalized = ($Value -replace '[\x00-\x1F\x7F]', '').Trim()
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        throw "$Name is empty after removing whitespace and control characters."
    }
    return $normalized
}

if ([string]::IsNullOrWhiteSpace($ClovaApiKey)) {
    $ClovaApiKey = $EmbeddedClovaApiKey
}
if ([string]::IsNullOrWhiteSpace($ClovaApiKey)) {
    $ClovaApiKey = $env:CLOVASTUDIO_API_KEY
}
if ([string]::IsNullOrWhiteSpace($ClovaApiKey)) {
    $ClovaApiKey = Get-DotEnvValue -Name "CLOVASTUDIO_API_KEY"
}
if ([string]::IsNullOrWhiteSpace($ClovaApiKey)) {
    $ClovaApiKey = Read-SecretValue -Prompt "CLOVA Studio API key"
}
if ([string]::IsNullOrWhiteSpace($ObjectAccessKey)) {
    $ObjectAccessKey = $EmbeddedObjectAccessKey
}
if ([string]::IsNullOrWhiteSpace($ObjectAccessKey)) {
    $ObjectAccessKey = Get-DotEnvValue -Name "NCP_OBJECT_ACCESS_KEY"
}
if ([string]::IsNullOrWhiteSpace($ObjectAccessKey)) {
    $ObjectAccessKey = Read-SecretValue -Prompt "Object Storage Access Key"
}
if ([string]::IsNullOrWhiteSpace($ObjectSecretKey)) {
    $ObjectSecretKey = $EmbeddedObjectSecretKey
}
if ([string]::IsNullOrWhiteSpace($ObjectSecretKey)) {
    $ObjectSecretKey = Get-DotEnvValue -Name "NCP_OBJECT_SECRET_KEY"
}
if ([string]::IsNullOrWhiteSpace($ObjectSecretKey)) {
    $ObjectSecretKey = Read-SecretValue -Prompt "Object Storage Secret Key"
}
if ([string]::IsNullOrWhiteSpace($TuningBucket)) {
    $TuningBucket = "tuningdata1"
}
if ([string]::IsNullOrWhiteSpace($TuningFilePath)) {
    $TuningFilePath = "hyperclova_answer_train_457.jsonl"
}
if ([string]::IsNullOrWhiteSpace($TuningModel)) {
    $TuningModel = "HCX-DASH-002"
}

$ClovaApiKey = Normalize-RequestValue -Name "CLOVA Studio API key" -Value $ClovaApiKey
$ObjectAccessKey = Normalize-RequestValue -Name "Object Storage Access Key" -Value $ObjectAccessKey
$ObjectSecretKey = Normalize-RequestValue -Name "Object Storage Secret Key" -Value $ObjectSecretKey
$TuningBucket = Normalize-RequestValue -Name "Tuning bucket" -Value $TuningBucket
$TuningFilePath = Normalize-RequestValue -Name "Tuning file path" -Value $TuningFilePath
$TuningModel = Normalize-RequestValue -Name "Tuning model" -Value $TuningModel
$TaskName = Normalize-RequestValue -Name "Task name" -Value $TaskName

$headers = @{
    "Authorization" = "Bearer $ClovaApiKey"
    "X-NCP-CLOVASTUDIO-REQUEST-ID" = [guid]::NewGuid().ToString()
}
$body = @{
    name = $TaskName
    model = $TuningModel
    tuningType = "PEFT"
    trainEpochs = "4"
    learningRate = "1.0E-5"
    validationSplitRatio = 0.1
    loraR = 8
    loraAlpha = 64
    trainingDatasetBucket = $TuningBucket
    trainingDatasetFilePath = $TuningFilePath
    trainingDatasetAccessKey = $ObjectAccessKey
    trainingDatasetSecretKey = $ObjectSecretKey
} | ConvertTo-Json -Compress

Invoke-RestMethod `
    -Method Post `
    -Uri "https://clovastudio.stream.ntruss.com/tuning/v2/tasks" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body
