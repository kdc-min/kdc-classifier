import json, base64, time, urllib.request

HEADERS = {
    'Referer': 'https://www.aladin.co.kr/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

def fetch_image_as_base64(url):
    if not url: return ''
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            ct = resp.headers.get('Content-Type', 'image/jpeg').split(';')[0]
            if 'image' not in ct: return ''
            data = resp.read()
        return f"data:{ct};base64,{base64.b64encode(data).decode()}"
    except Exception:
        return ''

with open('books_cache.json', encoding='utf-8') as f:
    cache = json.load(f)

books = cache['books']
total = len(books)
for i, book in enumerate(books):
    if book.get('bookImageB64'):
        continue
    url = book.get('bookImageURL', '')
    b64 = fetch_image_as_base64(url)
    book['bookImageB64'] = b64
    status = 'OK' if b64 else 'FAIL'
    print(f"[{i+1:3}/{total}] {status} {book['title'][:40]}")
    time.sleep(0.05)

with open('books_cache.json', 'w', encoding='utf-8') as f:
    json.dump(cache, f, ensure_ascii=False, indent=2)

success = sum(1 for b in books if b.get('bookImageB64'))
print(f"\n완료: {success}/{total}권 이미지 저장")
