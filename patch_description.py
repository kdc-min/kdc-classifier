import json, requests, time

API_KEY = input("정보나루 API 인증키: ").strip()

def fetch_description(isbn13):
    """srchDtlList로 책소개 수집"""
    try:
        r = requests.get(
            'http://data4library.kr/api/srchDtlList',
            params={'authKey': API_KEY, 'isbn13': isbn13, 'format': 'json'},
            timeout=8
        )
        book = r.json()['response']['detail'][0]['book']
        return book.get('description', '').strip()
    except Exception:
        return ''

def fetch_keywords(isbn13):
    """keywordList로 핵심 키워드 수집 (description 없을 때 대체)"""
    try:
        r = requests.get(
            'http://data4library.kr/api/keywordList',
            params={'authKey': API_KEY, 'isbn13': isbn13,
                    'additionalYN': 'Y', 'format': 'json'},
            timeout=8
        )
        keywords = r.json()['response']['keywords']
        kw_list = [k['keyword'] for k in
                   sorted(keywords, key=lambda x: float(x.get('weight', 0)), reverse=True)[:10]]
        return ' · '.join(kw_list) if kw_list else ''
    except Exception:
        return ''

with open('books_cache.json', encoding='utf-8') as f:
    cache = json.load(f)

books = cache['books']
total = len(books)

for i, book in enumerate(books):
    if book.get('description') is not None:
        print(f"[{i+1:3}/{total}] SKIP {book['title'][:30]}")
        continue

    isbn13 = book.get('isbn13', '').strip()
    if not isbn13:
        book['description'] = ''
        book['keywords'] = ''
        print(f"[{i+1:3}/{total}] NO_ISBN {book['title'][:30]}")
        continue

    desc = fetch_description(isbn13)
    kw   = fetch_keywords(isbn13) if not desc else ''

    book['description'] = desc
    book['keywords']    = kw

    status = 'OK' if desc else ('KW' if kw else 'FAIL')
    preview = (desc or kw)[:40]
    print(f"[{i+1:3}/{total}] {status} {book['title'][:25]:25} | {preview}")
    time.sleep(0.15)

with open('books_cache.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

desc_count = sum(1 for b in books if b.get('description'))
kw_count   = sum(1 for b in books if b.get('keywords') and not b.get('description'))
none_count = sum(1 for b in books if not b.get('description') and not b.get('keywords'))
print(f"\n완료: 책소개 {desc_count}권 | 키워드만 {kw_count}권 | 없음 {none_count}권")
