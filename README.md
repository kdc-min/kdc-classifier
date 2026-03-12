# KDC CLASSIFIER
> 한국십진분류법(KDC) 학습 실습 게임: 인기 대출 도서 데이터를 활용한 단계별 분류 퀴즈

🔗 **[바로 플레이하기 →](https://kdc-min.github.io/kdc-classifier/)**

![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-배포중-c82000?style=flat&logo=github&labelColor=1a1209)
![Vanilla JS](https://img.shields.io/badge/Vanilla%20JS-서버없음-c87800?style=flat&labelColor=1a1209)
![License](https://img.shields.io/badge/License-MIT-blue?style=flat&labelColor=1a1209)

---

## 소개

실제 인기 대출 도서의 표지·제목·저자·책소개를 보고  
KDC(한국십진분류법) 분류번호를 단계적으로 선택하는 학습 게임입니다.

도서관 사서 시험 준비, KDC 개념 학습, 그냥 재미 — 모두 가능합니다.

---

## 주요 기능

- **연습 모드** — 분야·문제 수 자유 선택, 오답 시 계속 시도 가능
- **실전 모드** — 하트 5개, 틀리면 감소, 0이 되면 종료. 최고 점수 기록
- **MY RECORD** — 게임 기록, 분야별 정답률, 최근 10게임 바 차트
- **824권 도서 데이터** — 실제 인기 대출 도서 기반, 표지 이미지 포함
- **Web Audio BGM** — 외부 파일 없이 Web Audio API로 구현한 오리지널 BGM

---

## 기술 스택

| 항목 | 내용 |
|------|------|
| 프론트엔드 | Vanilla JS, HTML/CSS (단일 파일) |
| 도서 데이터 | 도서관 정보나루 Open API (공공 도서관 대출 데이터) |
| KDC 트리 | 국립중앙도서관 Linked Open Data API (14,023 노드 → HTML 인라인) |
| 이미지 | base64 인라인 (CDN 핫링크 차단 우회) |
| 오디오 | Web Audio API (외부 의존 없음) |
| 저장소 | localStorage (서버 없음, 사용자 간 완전 분리) |
| 배포 | GitHub Pages |

---

## 데이터 파이프라인

### KDC 트리 구조 (초기 셋업, 1회 실행)

```
국립중앙도서관 Linked Open Data API
    ↓
archive/KDC 추출.ipynb   # 주류 10개(000~900) BFS 탐색 → 14,023 노드 수집
    ↓
kdc_all_data.json        # KDC 전체 트리 (코드·명칭·부모·자식 관계)
    ↓
build.py                 # PARENT_MAP / NAME_MAP / CHILDREN_MAP → index.html 인라인 삽입
```

> KDC 트리는 초기 셋업 시 1회 수집 후 `index.html`에 직접 인라인되어 있습니다. 재실행 불필요.

### 도서 데이터

```
도서관 정보나루 API
    ↓
fetch_books.py       # KDC 분야별 인기 도서 수집 (824권)
    ↓
patch_images.py      # 표지 이미지 → base64 변환
    ↓
patch_description.py # 책소개 · 키워드 수집
    ↓
books_cache.json     # index.html이 fetch()로 로드
```

### 도서 수집 현황

| 분야 | 권수 |
|------|------|
| 0xx 총류 | 36 |
| 1xx 철학 | 118 |
| 2xx 종교 | 78 |
| 3xx 사회과학 | 128 |
| 4xx 자연과학 | 68 |
| 5xx 기술과학 | 87 |
| 6xx 예술 | 98 |
| 7xx 언어 | 77 |
| 8xx 문학 | 92 |
| 9xx 역사 | 42 |
| **합계** | **824** |

---

## 로컬 실행

```bash
# 1. 저장소 클론
git clone https://github.com/kdc-min/kdc-classifier.git
cd kdc-classifier

# 2. 로컬 서버 실행 (file:// 직접 열기는 fetch 차단됨)
python -m http.server 8000

# 3. 브라우저에서 접속
# http://localhost:8000
```

### 도서 데이터 갱신 (선택)

```bash
# 도서관 정보나루 API 키 필요 (https://www.data4library.kr/)
python fetch_books.py --key <authKey>
python patch_images.py
python patch_description.py
```

---

## 라이선스

MIT © 2026 Minhyuk Kwon

---

## 개발자

**Minhyuk Kwon** · [@kdc-min](https://github.com/kdc-min)

> 이 프로젝트는 [Claude Sonnet 4.6](https://www.anthropic.com/claude) (Anthropic)과의 협업으로 개발되었습니다. 바이브 코딩(Vibe Coding)을 했다는 뜻입니다.

---

*도서 데이터: [도서관 정보나루 (data4library.kr)](https://www.data4library.kr/)*  
*KDC 분류 체계: [국립중앙도서관 Linked Open Data](https://lod.nl.go.kr/)*
