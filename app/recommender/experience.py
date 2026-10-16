"""Observable input evidence for the demo; never claims to explain model weights."""
import json
from collections import Counter

from app.database import connection, public_product

ACTIONS=('click','favorite','add_to_cart','purchase')
ACTION_LABELS={'click':'Đã xem','favorite':'Đã lưu','add_to_cart':'Đã thêm giỏ','purchase':'Đã mua thử'}


def original_profile(db,user_id):
    row=db.execute('SELECT features_json FROM muse_user_features WHERE user_id=?',(user_id,)).fetchone()
    return json.loads(row[0]) if row else None


def experience_summary(user_id):
    with connection() as db:
        source=original_profile(db,user_id) if user_id else None
        groups=Counter(x for x in source['151_2_180'] if x) if source else Counter()
        original_count=sum(groups.values())
        if user_id and not source:
            groups.update(int(r[0]) for r in db.execute('''SELECT p.source_category_id
                FROM user_behavior_history h JOIN products p ON p.id=h.product_id WHERE h.user_id=?
                AND h.action_type IN ('click','favorite','add_to_cart','purchase')
                AND p.source_category_id IS NOT NULL ORDER BY h.id DESC LIMIT 1000''',(user_id,)))
        group_rows={int(r['source_category_id']):dict(r) for r in db.execute('''SELECT p.source_category_id,
            p.category_id,c.name,COUNT(*) available_count FROM products p JOIN categories c ON c.id=p.category_id
            WHERE p.id <= 20000 AND p.source_feature_complete=1 AND p.stock>0 GROUP BY p.category_id''')}
        top=[]
        for raw,count in groups.most_common(6):
            if raw in group_rows:
                row=group_rows[raw]
                top.append({'id':row['category_id'],'name':row['name'],'events':count,'available_count':row['available_count']})
        recent=[{**public_product(r),'action_label':ACTION_LABELS[r['action_type']]} for r in db.execute('''
            SELECT p.*,h.id event_id,h.action_type,h.created_at event_time,c.name category_name
            FROM user_behavior_history h JOIN products p ON p.id=h.product_id
            JOIN categories c ON c.id=p.category_id WHERE h.user_id=?
            AND h.action_type IN ('click','favorite','add_to_cart','purchase') ORDER BY h.id DESC LIMIT 6''',(user_id,))] if user_id else []
        live_count=db.execute("SELECT COUNT(*) FROM user_behavior_history WHERE user_id=? AND action_type IN ('click','favorite','add_to_cart','purchase')",(user_id,)).fetchone()[0] if user_id else 0
        seeds=[]
        if source:
            ids=list(dict.fromkeys(x for x in reversed(source['150_2_180']) if x))[:24]
            if ids:
                rows={r['raw_item_id']:public_product(r) for r in db.execute('''SELECT p.*,c.name category_name
                    FROM products p JOIN categories c ON c.id=p.category_id
                    WHERE p.stock>0 AND p.raw_item_id IN ('''+','.join('?'*len(ids))+')',ids)}
                seeds=[rows[raw] for raw in ids if raw in rows][:4]
        return {'imported':source is not None,'original_events':original_count,'live_events':live_count,
                'top_groups':top,'recent':recent,'history_examples':seeds,
                'group_evidence_source':'original' if source else 'live',
                'evidence_note':'Tần suất nhóm trong dữ liệu đầu vào, không phải trọng số hay lời giải thích nhân quả của model.'}
