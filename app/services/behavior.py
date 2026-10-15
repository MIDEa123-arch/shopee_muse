def record_behavior(db,user,product,action):
    # New accounts use a separate negative namespace; never borrow another user's Taobao ID.
    raw_uid=user['raw_user_id'] if user['raw_user_id'] is not None else -user['id']
    db.execute('''INSERT INTO user_behavior_history(user_id,raw_user_id,product_id,raw_item_id,action_type)
        VALUES (?,?,?,?,?)''',(user['id'],raw_uid,product['id'],product['raw_item_id'],action))
