"""Cache existing Unsplash demo photos locally; do not imply unique Taobao photos."""
import concurrent.futures
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import config
from app.database import connection
from app.seed_data import SAMPLE_PROFILES,PRODUCT_TEMPLATES


def cache():
    with connection() as db:
        urls={r['image_url'] for r in db.execute("SELECT image_url FROM products WHERE image_url LIKE 'https://images.unsplash.com/%'")}
        urls|={r['avatar_url'] for r in db.execute("SELECT avatar_url FROM users WHERE avatar_url LIKE 'https://images.unsplash.com/%'")}
    urls|={p[3] for p in SAMPLE_PROFILES}
    urls|={item[3] for items in PRODUCT_TEMPLATES.values() for item in items}
    frontend=config.ROOT/'static/js/app.js'
    urls|=set(re.findall(r'https://images\.unsplash\.com/photo-[a-zA-Z0-9-]+(?:\?[^\s\x27\x22<>]*)?',frontend.read_text()))
    normalized={u:u.split('?')[0] for u in urls}
    images=config.ROOT/'static/images/catalog';images.mkdir(exist_ok=True)
    results={};failures=[]
    def download(base):
        filename=hashlib.sha256(base.encode()).hexdigest()[:16]+'.jpg'
        target=images/filename
        if not target.exists():
            request=urllib.request.Request(base+'?auto=format&fit=crop&w=650&q=82&fm=jpg',headers={'User-Agent':'Shopee-MUSE-Research-Demo/1.0'})
            with urllib.request.urlopen(request,timeout=30) as response:
                content=response.read(4_000_001)
                if not response.headers.get('Content-Type','').startswith('image/') or len(content)>4_000_000:
                    raise ValueError('Invalid image response')
                target.write_bytes(content)
        return base,'/static/images/catalog/'+filename
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        pending={pool.submit(download,base):base for base in set(normalized.values())}
        for future in concurrent.futures.as_completed(pending):
            try:
                base,path=future.result();results[base]=path
            except Exception as exc:
                failures.append({'source':pending[future],'error':str(exc)})
    with connection(write=True) as db:
        for url,base in normalized.items():
            if base in results:
                db.execute('UPDATE products SET image_url=? WHERE image_url=?',(results[base],url))
                db.execute('UPDATE users SET avatar_url=? WHERE avatar_url=?',(results[base],url))
        # Correct legacy randomly assigned merchandising photos using the supplied templates.
        for items in PRODUCT_TEMPLATES.values():
            for item in items:
                base=item[3].split('?')[0]
                if base in results:
                    db.execute('UPDATE products SET image_url=? WHERE name LIKE ?',
                               (results[base],item[0]+' (Model #%'))
    (images/'sources.json').write_text(json.dumps(results,indent=2))
    source=frontend.read_text()
    for url,base in normalized.items():
        if base in results:
            source=source.replace(url,results[base])
    frontend.write_text(source)
    print(json.dumps({'cached_photos':len(results),'failures':failures},ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__=='__main__':
    cache()
