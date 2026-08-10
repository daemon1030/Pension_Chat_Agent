# 데이터셋 전처리 생성파일

[parser.py](/Users/shindongmin/Desktop/미래에셋/src/preprocessing/parser.py): PyMuPDF 기반 페이지별 추출, PDF 메타데이터, SHA-256 계산, 텍스트 레이어 상태 판정

[cleaner.py](/Users/shindongmin/Desktop/미래에셋/src/preprocessing/cleaner.py): 개행과 탭을 보존하는 최소 정제

[schemas.py](/Users/shindongmin/Desktop/미래에셋/src/preprocessing/schemas.py): 
문서·페이지·메타데이터·반복 문구 후보 Pydantic 모델

[preprocess.py](/Users/shindongmin/Desktop/미래에셋/scripts/preprocess.py): PDF 재귀 순회, 검증, 중복 후보 표시, JSON 저장 CLI

[test_cleaner.py](/Users/shindongmin/Desktop/미래에셋/tests/preprocessing/test_cleaner.py): 원문 보존 및 최소 정제 테스트

[test_parser.py](/Users/shindongmin/Desktop/미래에셋/tests/preprocessing/test_parser.py): 페이지 추출, 페이지 번호, 해시, 무텍스트 PDF 테스트

[test_preprocess.py](/Users/shindongmin/Desktop/미래에셋/tests/preprocessing/test_preprocess.py): 전체 파이프라인 및 중복 후보 통합 테스트

[pyproject.toml](/Users/shindongmin/Desktop/미래에셋/pyproject.toml), [uv.lock](/Users/shindongmin/Desktop/미래에셋/uv.lock): PyMuPDF, Pydantic, pytest 의존성