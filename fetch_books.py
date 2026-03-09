#!/usr/bin/env python3
"""
fetch_books.py  (v2 — 균형 수집)
정보나루 Open API에서 KDC별 도서 데이터를 균형 있게 수집합니다.

전략:
  1) dtl_kdc 세부 코드별로 요청 → 분야 내 다양성 확보
  2) pageNo 1~2 순회 (최대 200건/세부코드)
  3) 분야별 TARGET 달성 시 조기 종료 → 과다 수집 방지
  4) 분야별 최소 80건, 전체 ~1,000건 목표

Usage:
  python fetch_books.py --key <authKey>
  python fetch_books.py --key <authKey> --refresh
  python fetch_books.py --key <authKey> --kdc 2 4 9   # 특정 분야만 보강
"""

import argparse
import json
import os
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime

CACHE_FILE = "books_cache.json"
API_URL    = "https://data4library.kr/api/loanItemSrch"
PER_PAGE   = 100  # API 최대 허용치

# ─────────────────────────────────────────────────────────────────────────────
# 분야별 수집 목표 (TARGET) 및 세부주제(dtl_kdc) 코드 목록
# 저수집 분야(2·4·9)는 세부코드를 더 세분화해서 여러 번 요청
# ─────────────────────────────────────────────────────────────────────────────
KDC_PLAN = {
    "0": {
        "name": "총류",
        "target": 60,
        "dtl_list": ["4", "5", "0", "1", "2", "3", "6", "7", "8", "9"],
        "use_keyword": True,
        "keywords": ["파이썬", "코딩", "자바스크립트", "인공지능", "데이터과학",
                     "컴퓨터", "프로그래밍", "알고리즘"],
    },
    "1": {
        "name": "철학",
        "target": 120,
        "dtl_list": ["10", "15", "16", "18", "19", "11", "12", "13", "14", "17"],
        # 철학일반/동양철학/서양철학/심리학/윤리학 우선
    },
    "2": {
        "name": "종교",
        "target": 80,   # 현재 15건 → 대폭 보강
        "dtl_list": ["23", "22", "20", "21", "28", "24", "25", "26", "27", "29"],
        # 기독교·불교가 압도적으로 많음, 나머지도 순회
    },
    "3": {
        "name": "사회과학",
        "target": 130,
        "dtl_list": ["33", "32", "37", "34", "36", "35", "31", "38", "39", "30"],
        # 사회학/경제학/교육학/정치학/법학 우선
    },
    "4": {
        "name": "자연과학",
        "target": 80,   # 현재 15건 → 대폭 보강
        "dtl_list": ["47", "41", "49", "48", "42", "43", "44", "45", "46", "40"],
        # 생물/수학/동물/식물/물리/화학 우선
    },
    "5": {
        "name": "기술과학",
        "target": 100,
        "dtl_list": ["51", "59", "56", "52", "53", "54", "55", "57", "58", "50"],
        # 의학/가정학/전기전자/농학 우선
    },
    "6": {
        "name": "예술",
        "target": 100,
        "dtl_list": ["69", "67", "65", "68", "63", "61", "62", "64", "66", "60"],
        # 오락운동/음악/회화/연극/공예 우선
    },
    "7": {
        "name": "언어",
        "target": 80,
        "dtl_list": ["71", "74", "72", "73", "75", "76", "77", "78", "79", "70"],
        # 한국어/영어/중국어/일본어 우선
    },
    "8": {
        "name": "문학",
        "target": 200,  # 인기도서가 가장 많은 분야, 충분히 확보
        "dtl_list": ["81", "84", "83", "82", "85", "86", "87", "88", "89", "80"],
        # 한국문학/영미문학/일본문학/중국문학 우선
    },
    "9": {
        "name": "역사",
        "target": 80,   # 현재 16건 → 대폭 보강
        "dtl_list": ["99", "91", "98", "92", "94", "93", "95", "96", "97", "90"],
        # 전기/아시아역사/지리 우선
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────────────────────────────────────

def normalize_title(title: str) -> str:
    t = re.sub(r'\([^)]*\)\s*', '', title)
    t = re.sub(r'\s*=.*', '', t)
    t = re.sub(r'\s*:.*', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def http_get_json(url: str, timeout: int = 15) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_image_url(doc: dict) -> str:
    url = str(doc.get("bookImageURL", "")).strip()
    if url.startswith("http://"):
        url = "https://" + url[7:]
    return url


def fetch_detail_image(key: str, isbn13: str) -> str:
    """srchDtlList fallback으로 이미지 URL 재조회"""
    if not isbn13:
        return ""
    try:
        params = {"authKey": key, "isbn13": isbn13, "format": "json"}
        url = "https://data4library.kr/api/srchDtlList?" + urllib.parse.urlencode(params)
        data = http_get_json(url, timeout=10)
        raw = str(
            data.get("response", {})
                .get("detail", [{}])[0]
                .get("book", {})
                .get("bookImageURL", "")
        ).strip()
        if raw.startswith("http://"):
            raw = "https://" + raw[7:]
        return raw
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# 핵심 수집 함수
# ─────────────────────────────────────────────────────────────────────────────

def fetch_by_dtl_kdc(key: str, dtl_kdc: str, max_pages: int = 2) -> list[dict]:
    """특정 dtl_kdc 코드로 최대 max_pages 페이지 수집"""
    results = []
    for page in range(1, max_pages + 1):
        params = {
            "authKey": key,
            "format":   "json",
            "dtl_kdc":  dtl_kdc,
            "pageSize": PER_PAGE,
            "pageNo":   page,
        }
        url = API_URL + "?" + urllib.parse.urlencode(params)
        try:
            data = http_get_json(url)
        except Exception as e:
            print(f"      ⚠ dtl_kdc={dtl_kdc} page={page} 오류: {e}")
            break

        docs = data.get("response", {}).get("docs", [])
        if not docs:
            break  # 더 이상 결과 없음

        for item in docs:
            doc = item.get("doc", item)
            class_no = str(doc.get("class_no", "")).strip()
            if not class_no or not class_no[0].isdigit():
                continue

            isbn13 = str(doc.get("isbn13", "")).strip()
            cover  = extract_image_url(doc)
            if not cover and isbn13:
                cover = fetch_detail_image(key, isbn13)
                time.sleep(0.1)

            results.append({
                "title":        str(doc.get("bookname", "")).strip(),
                "author":       str(doc.get("authors", "")).strip(),
                "publisher":    str(doc.get("publisher", "")).strip(),
                "pub_year":     str(doc.get("publication_year", "")).strip(),
                "class_no":     class_no,
                "class_nm":     str(doc.get("class_nm", "")).strip(),
                "isbn13":       isbn13,
                "bookImageURL": cover,
            })

        # 결과가 pageSize 미만이면 다음 페이지 없음
        if len(docs) < PER_PAGE:
            break

        time.sleep(0.3)

    return results


def fetch_by_kdc(key: str, kdc: str, max_pages: int = 2) -> list[dict]:
    """kdc 주류 코드로 요청 (dtl_kdc가 0건일 때 대체 사용)"""
    results = []
    for page in range(1, max_pages + 1):
        params = {
            "authKey": key,
            "format":   "json",
            "kdc":      kdc,
            "pageSize": PER_PAGE,
            "pageNo":   page,
        }
        url = API_URL + "?" + urllib.parse.urlencode(params)
        try:
            data = http_get_json(url)
        except Exception as e:
            print(f"      ⚠ kdc={kdc} page={page} 오류: {e}")
            break

        docs = data.get("response", {}).get("docs", [])
        if not docs:
            break

        for item in docs:
            doc = item.get("doc", item)
            class_no = str(doc.get("class_no", "")).strip()
            if not class_no or not class_no[0].isdigit():
                continue

            isbn13 = str(doc.get("isbn13", "")).strip()
            cover  = extract_image_url(doc)
            if not cover and isbn13:
                cover = fetch_detail_image(key, isbn13)
                time.sleep(0.1)

            results.append({
                "title":        str(doc.get("bookname", "")).strip(),
                "author":       str(doc.get("authors", "")).strip(),
                "publisher":    str(doc.get("publisher", "")).strip(),
                "pub_year":     str(doc.get("publication_year", "")).strip(),
                "class_no":     class_no,
                "class_nm":     str(doc.get("class_nm", "")).strip(),
                "isbn13":       isbn13,
                "bookImageURL": cover,
            })

        if len(docs) < PER_PAGE:
            break

        time.sleep(0.3)

    return results


def fetch_by_keyword(key: str, keyword: str, max_pages: int = 2) -> list[dict]:
    """srchBooks API로 키워드 검색"""
    SRCH_URL = "https://data4library.kr/api/srchBooks"
    results = []
    for page in range(1, max_pages + 1):
        params = {
            "authKey":  key,
            "keyword":  keyword,
            "sort":     "loan",
            "order":    "desc",
            "pageSize": PER_PAGE,
            "pageNo":   page,
            "format":   "json",
        }
        url = SRCH_URL + "?" + urllib.parse.urlencode(params)
        try:
            data = http_get_json(url)
        except Exception as e:
            print(f"      ⚠ keyword={keyword} page={page} 오류: {e}")
            break

        docs = data.get("response", {}).get("docs", [])
        if not docs:
            break

        for item in docs:
            doc = item.get("doc", item)
            class_no = str(doc.get("class_no", "")).strip()
            if not class_no or not class_no[0].isdigit():
                continue

            isbn13 = str(doc.get("isbn13", "")).strip()
            cover  = extract_image_url(doc)
            if not cover and isbn13:
                cover = fetch_detail_image(key, isbn13)
                time.sleep(0.1)

            results.append({
                "title":        str(doc.get("bookname", "")).strip(),
                "author":       str(doc.get("authors", "")).strip(),
                "publisher":    str(doc.get("publisher", "")).strip(),
                "pub_year":     str(doc.get("publication_year", "")).strip(),
                "class_no":     class_no,
                "class_nm":     str(doc.get("class_nm", "")).strip(),
                "isbn13":       isbn13,
                "bookImageURL": cover,
            })

        if len(docs) < PER_PAGE:
            break

        time.sleep(0.3)

    return results


def collect_kdc_domain(key: str, kdc_digit: str, plan: dict,
                       existing_isbns: set, existing_series: set) -> list[dict]:
    """
    한 KDC 주류 전체를 dtl_kdc 순으로 수집.
    target 달성 시 조기 종료.
    """
    target      = plan["target"]
    dtl_list    = plan["dtl_list"]
    name        = plan["name"]
    use_keyword = plan.get("use_keyword", False)
    keywords    = plan.get("keywords", [])
    collected   = []
    seen_isbn   = set(existing_isbns)   # 전역 중복 방지
    seen_ser    = set(existing_series)  # 시리즈 중복 방지

    print(f"\n  [{kdc_digit}xx {name}] 목표 {target}건")

    def _dedup_and_append(raw: list[dict], kdc_filter: str | None = None) -> int:
        added = 0
        for book in raw:
            if book['title'].strip().startswith('Why?'):
                continue
            if kdc_filter and str(book.get("class_no", ""))[:1] != kdc_filter:
                continue
            isbn = book.get("isbn13")
            isbn_key = isbn if isbn else f"{book['title']}|{book['author']}"
            if isbn_key in seen_isbn:
                continue
            first_word = book["author"].split()[0] if book["author"] else ""
            ser_key = normalize_title(book["title"]) + "|" + first_word
            if ser_key in seen_ser:
                continue
            seen_isbn.add(isbn_key)
            seen_ser.add(ser_key)
            collected.append(book)
            added += 1
            if len(collected) >= target:
                break
        return added

    if use_keyword:
        for kw in keywords:
            if len(collected) >= target:
                print(f"    → 목표 달성, 조기 종료")
                break

            raw = fetch_by_keyword(key, kw, max_pages=2)
            added = _dedup_and_append(raw, kdc_filter=kdc_digit)
            print(f"    keyword={kw!r}: {len(raw):3}건 수신 → +{added}건 추가 "
                  f"(누계 {len(collected)}/{target})")
            time.sleep(0.4)
    else:
        for dtl in dtl_list:
            if len(collected) >= target:
                print(f"    → 목표 달성, 조기 종료")
                break

            raw = fetch_by_dtl_kdc(key, dtl, max_pages=2)
            added = _dedup_and_append(raw)
            print(f"    dtl_kdc={dtl:>2}: {len(raw):3}건 수신 → +{added}건 추가 "
                  f"(누계 {len(collected)}/{target})")
            time.sleep(0.4)

    return collected


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="정보나루 KDC 도서 균형 수집기 v2")
    parser.add_argument("--key",     required=True, help="정보나루 API 인증키")
    parser.add_argument("--refresh", action="store_true",
                        help="기존 캐시 무시하고 전체 재수집")
    parser.add_argument("--kdc",     nargs="+", metavar="DIGIT",
                        help="특정 주류만 보강 (예: --kdc 2 4 9)")
    args = parser.parse_args()

    # ── 기존 캐시 로드 ───────────────────────────────────────────────────────
    existing_books: list[dict] = []
    if os.path.exists(CACHE_FILE) and not args.refresh:
        with open(CACHE_FILE, encoding="utf-8") as f:
            cache = json.load(f)
        existing_books = cache.get("books", [])
        print(f"[INFO] 기존 캐시 로드: {len(existing_books)}건")
        if not args.kdc:
            print("[INFO] --refresh 또는 --kdc 없이는 기존 캐시를 그대로 유지합니다.")
            print("       전체 재수집: --refresh  /  분야 보강: --kdc 2 4 9")
            return
    elif args.refresh:
        print("[INFO] --refresh: 기존 캐시 무시, 전체 재수집")

    # ── 수집 대상 결정 ──────────────────────────────────────────────────────
    target_digits = args.kdc if args.kdc else list(KDC_PLAN.keys())

    # 기존 책의 isbn/series 집합 (전역 중복 방지)
    global_isbns  : set[str] = set()
    global_series : set[str] = set()
    for b in existing_books:
        isbn = b.get("isbn13")
        global_isbns.add(isbn if isbn else f"{b['title']}|{b['author']}")
        fw = b["author"].split()[0] if b.get("author") else ""
        global_series.add(normalize_title(b["title"]) + "|" + fw)

    # ── 수집 실행 ────────────────────────────────────────────────────────────
    new_books: list[dict] = []
    for digit in target_digits:
        if digit not in KDC_PLAN:
            print(f"[WARN] KDC {digit} 은 계획에 없습니다, 스킵")
            continue

        # 보강 모드: 이미 target 이상이면 스킵
        if args.kdc:
            current_count = sum(
                1 for b in existing_books
                if str(b.get("class_no", ""))[:1] == digit
            )
            target = KDC_PLAN[digit]["target"]
            if current_count >= target:
                print(f"  [{digit}xx] 이미 {current_count}건 ≥ 목표 {target}건, 스킵")
                continue
            # 목표 = 부족분만 채우기
            KDC_PLAN[digit]["target"] = target - current_count
            print(f"  [{digit}xx] 현재 {current_count}건 → {target - current_count}건 추가 필요")

        books = collect_kdc_domain(
            args.key, digit, KDC_PLAN[digit],
            global_isbns, global_series
        )
        new_books.extend(books)

        # 수집한 것들도 전역 집합에 추가 (분야 간 중복 방지)
        for b in books:
            isbn = b.get("isbn13")
            global_isbns.add(isbn if isbn else f"{b['title']}|{b['author']}")
            fw = b["author"].split()[0] if b.get("author") else ""
            global_series.add(normalize_title(b["title"]) + "|" + fw)

    # ── 병합 및 저장 ─────────────────────────────────────────────────────────
    if args.kdc:
        all_books = existing_books + new_books
    else:
        all_books = new_books  # --refresh면 새 것만

    # 분야별 통계 출력
    print("\n" + "=" * 50)
    print("📊 최종 분야별 수집량")
    print("=" * 50)
    for digit, plan in KDC_PLAN.items():
        cnt = sum(1 for b in all_books if str(b.get("class_no", ""))[:1] == digit)
        bar = "█" * (cnt // 5)
        flag = " ⚠" if cnt < 50 else ""
        print(f"  {digit}xx {plan['name']:6}: {cnt:4}건  {bar}{flag}")
    print(f"\n  합계: {len(all_books)}건")
    print("=" * 50)

    cache_out = {
        "fetched_at": datetime.now().isoformat(),
        "total":      len(all_books),
        "books":      all_books,
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_out, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료! 총 {len(all_books)}건 → {CACHE_FILE} 저장됨")
    print(f"   다음 단계: python patch_images.py && python patch_description.py")


if __name__ == "__main__":
    main()
