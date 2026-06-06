# TourAPI Korea Data Acquisition & Analytics Pipeline

이 프로젝트는 한국관광공사의 **TourAPI 4.0(KorService2)** 및 **관광 빅데이터 API(DataLabService)**를 활용하여 강원(GW) 및 경북(GB) 지역의 관광 명소, 축제 정보 및 관광객 방문 통계 데이터를 수집, 가공 및 통합하는 데이터 파이프라인입니다.

---

## 📌 주요 기능 (Key Features)

1. **지자체 통합 수집 (GW & GB)**
   - 강원 및 경북의 42개 행정구역(시군구)을 40개 대표 도시 단위(예: 포항시 남구·북구 통합 등)로 정형화하여 수집을 수행합니다.
2. **테마별 관광 데이터 수집 및 분류**
   - 수집 데이터를 6대 핵심 테마(`온천·휴양`, `바다·해안`, `역사·전통`, `미식·노포`, `자연·트레킹`, `예술·감성`)로 재분류하고 매핑합니다.
3. **대용량 상세정보 스크래핑 및 캐싱**
   - 관광지(Attractions)와 축제(Festivals)의 상세 공통 정보 및 소개 정보를 개별적으로 스크래핑하며, 네트워크 지연에 견고하게 예외처리 및 파일 기반의 캐싱(Checkpoint)을 수행합니다.
4. **1달 단위 월별 관광 빅데이터 수집 및 통계**
   - 일별 unique visitor 데이터를 합산 시 발생하는 중복 집계(Double Counting) 오류를 원천 차단하기 위해, API 호출을 **1달 단위로 구간화**하여 호출합니다.
   - 각 월의 **일평균 방문객 수(현지인, 외지인, 외국인 및 전체 합계)**를 계산하여 도시별 최종 데이터 파일에 병합 적재합니다.
5. **안정적인 API Key Rotation & Fail-Fast**
   - 여러 개의 디코딩된 API Key를 풀(Pool)로 관리하여 트래픽 제한(HTTP 429 또는 일일 쿼터 초과) 감지 시 자동으로 다음 키로 교체합니다.
   - 단순 파라미터 에러나 권한 오류 발생 시에는 키를 불필요하게 낭비하지 않고 즉시 에러를 표출하고 멈추는 **Fail-Fast** 전략을 사용합니다.

---

## 📂 프로젝트 디렉토리 구조 (Directory Structure)

> [!NOTE]
> 수집되는 원본 데이터, 캐시 데이터 및 대용량 결과 파일은 레포지토리 용량 관리와 보안을 위해 Git 추적에서 제외(`.gitignore`)되며, 로컬에서 실행 시 자동으로 생성됩니다.

```text
tour-api-korea/
├── data/                          # (Git-Ignored를 제외한 기준정보 구성)
│   ├── classification_dict.json   # 분류 코드 -> 테마 매핑 사전
│   ├── ldong_sigungu.json         # 수집 대상 행정 표준 코드 목록
│   ├── theme_mapping.json         # 테마 기준정보 정의
│   └── festival_mapping.json      # 축제 매핑 정의
│
├── scripts/
│   ├── scrape_list.py             # TourAPI를 통한 기초지자체별 명소/축제 리스트 수집
│   ├── group_lists_by_city.py     # 시군구별 파일들을 40개 대표 도시 기준으로 그룹화
│   ├── filter_existing_lists.py   # 테마 매핑 및 축제 재분류 오버라이드 적용
│   ├── scrape_attractions_only.py # 40개 도시 관광지 상세 정보 캐싱 수집 (Stage 2A)
│   ├── scrape_festivals_only.py   # 축제 상세 정보 캐싱 수집 (Stage 2B)
│   ├── merge_to_raw_detail.py     # 수집된 명소/축제 캐시를 raw/detail/ 폴더에 개별로 전개
│   ├── merge_to_final.py          # 리스트 파일과 개별 상세 JSON을 병합하여 raw/final/ 빌드
│   ├── scrape_and_aggregate_visitor.py # 2025년 월별 방문객 API 호출 및 일평균 계산/최종 병합
│   ├── normalize_details.py       # (사용자 영역) 최종 data/city/ 패키징을 위한 정규화 코드
│   ├── scrape_details.py          # 공통 스크래퍼 모듈 및 예외처리 정의
│   └── build_mapping_dict.py      # 분류 체계 구축 유틸리티
│
├── .gitignore                     # Git 관리 제외 대상 정의 파일
├── LICENSE                        # 오픈소스 라이선스
└── README.md                      # 본 가이드 문서
```

---

## ⚙️ 환경 설정 및 설치 (Setup & Installation)

### 1. 패키지 설치
Python 3.8 이상 환경에서 다음 의존 라이브러리를 설치합니다:
```bash
pip install requests pandas openpyxl
```

### 2. `.env` 파일 구성
프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 아래와 같이 인증키를 추가합니다. (이 파일은 `.gitignore`에 의해 커밋되지 않습니다.)
```env
TOUR_API_KEYS=decoded_key_1,decoded_key_2,decoded_key_3
```
> [!IMPORTANT]
> 반드시 공공데이터포털에서 발급받은 **디코딩된 키 (Decoded Key)**를 입력해야 합니다.
> Python `requests` 패키지가 파라미터 전달 시 자동으로 URL Encoding을 수행하므로, 이미 인코딩된 키를 입력하면 이중 인코딩이 발생하여 `SERVICEKEY_IS_NOT_REGISTERED_ERROR`가 발생합니다.

---

## 🚀 파이프라인 실행 방법 (Usage)

### Step 1: 리스트 수집 및 통합
1. 관광 명소 및 축제의 기본 리스트를 수집합니다.
   ```bash
   python scripts/scrape_list.py
   ```
2. 시군구 단위를 40개 도시 단위로 매핑하여 리스트를 재그룹화합니다.
   ```bash
   python scripts/group_lists_by_city.py
   ```
3. 테마 분류 사전 및 축제 테마 수동 오버라이드를 적용해 1차 필터링된 리스트를 빌드합니다.
   ```bash
   python scripts/filter_existing_lists.py
   ```

### Step 2: 상세 정보 스크래핑 (Stage 2)
1. 40개 도시의 관광지 상세 정보를 병렬 수집 및 캐싱합니다.
   ```bash
   python scripts/scrape_attractions_only.py
   ```
2. 대상 축제의 상세 정보를 개별 캐싱합니다.
   ```bash
   python scripts/scrape_festivals_only.py
   ```
   * *두 스크립트 모두 이미 수집된 캐시가 있을 경우 이를 건너뛰는 체크포인트 기능을 완벽히 지원합니다.*

### Step 3: 상세 정보 병합 및 빌드
1. 수집된 명소(3,709건)와 축제(106건) 캐시를 통합하여 단일 상세 JSON 세트(3,815개)로 전개합니다.
   ```bash
   python scripts/merge_to_raw_detail.py
   ```
2. 리스트 구조체와 개별 상세 정보를 엮어 `data/raw/final/{city_en}.json`에 통합 빌드합니다.
   ```bash
   python scripts/merge_to_final.py
   ```

### Step 4: 관광객 빅데이터 수집 및 통계 적재
1. 2025년 12개월 분량의 일별 방문객 빅데이터를 1달 단위 구간으로 나누어 호출 및 다운로드하고, 월별 일평균(현지인+외지인+외국인)을 산출하여 `data/raw/final/` 파일 내부의 `visitor_statistics` 필드에 바로 추가합니다.
   ```bash
   python scripts/scrape_and_aggregate_visitor.py
   ```
   * *이 과정에서 상세 로그 및 일별 수집 데이터는 `data/raw/visitor/` 경로에 로컬 저장되며, 가공 완료된 월별 일평균 통계의 통합본은 `data/visitor/monthly_visitor_averages.json`으로 저장됩니다.*

---

## 💡 주요 아키텍처 설계 의사결정

### 월별 일평균 방문객 계산의 타당성
- 관광 빅데이터(이동통신 데이터 기반)는 고유 방문자 수의 성격상, 일별 방문객 수를 단순 합산할 경우 기간 내 중복 방문자가 누적 합산되는 문제가 발생합니다.
- 이에 본 파이프라인은 기간을 1달 단위(`startYmd`/`endYmd`를 동일 월 내의 시작일과 종료일로 설정)로 끊어서 데이터를 받아오고, 각 월의 일수(28~31일)로 나눈 **월별 일평균 방문객 수(Monthly Daily Average)**를 최종 지표로 채택하여 데이터 정밀도를 극대화했습니다.
