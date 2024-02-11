import sqlite3
import time
import config
import bcrypt
import hashlib
import random
import salt

database = sqlite3.connect(config.sqlite_path, check_same_thread=False)

def get_user(user: str, passw: str):
    cur = database.cursor()
    passhash = hashlib.sha512((passw + salt.generate_user_salt(user + "@" + passw)).encode()).digest()
    cur.execute("SELECT id,password FROM users WHERE login=(?)", (user, ))
    d = cur.fetchone()
    cur.close()
    if d == None:
        return None
    if bcrypt.checkpw(passhash, d[1]):
        return d[0]
    else:
        return None
    
def gen_user(user, passw):
    cur = database.cursor()
    passhash = hashlib.sha512((passw + salt.generate_user_salt(user + "@" + passw)).encode()).digest()
    hashed = bcrypt.hashpw(passhash, bcrypt.gensalt())
    cur.execute("INSERT OR IGNORE INTO users VALUES ((?),(?),(?))", (random.getrandbits(16), user, hashed))
    cur.close()
    database.commit()

def get_free_subtask():
    close_dead_tasks()
    cur = database.cursor()
    cur.execute("SELECT * FROM subtasks WHERE processing_by IS NULL LIMIT 1")
    d = cur.fetchone()
    cur.close()
    if not(d):
        return d
    return dict(zip([i[0] for i in cur.description], d))

def get_task(task_id):
    close_dead_tasks()
    cur = database.cursor()
    cur.execute("SELECT * FROM subtasks WHERE id=(?)", (task_id, ))
    d = cur.fetchone()
    cur.close()
    if not(d):
        return d
    return dict(zip([i[0] for i in cur.description], d))

def private_task(task_id, user_id):
    task = get_task(task_id)
    if not(task):
        return {"ok": False, "desc": "invalid task id"}
    if task["processing_by"] != None:
        return {"ok": False, "desc": "task privated"}
    cur = database.cursor()
    cur.execute("UPDATE subtasks SET processing_by=?, last_ping=?, progress=0 WHERE id=(?)", (user_id, int(time.time()), task_id))
    cur.close()
    database.commit()
    return {"ok": True}

def ping_task(task_id, user_id, progress):
    close_dead_tasks()
    task = get_task(task_id)
    if not(task):
        return {"ok": False, "desc": "invalid task id"}
    if task["processing_by"] == None:
        return {"ok": False, "desc": "task is free"}
    if int(task["processing_by"]) != int(user_id):
        return {"ok": False, "desc": "no rights"}
    if int(task["last_ping"]) == -1:
        return {"ok": False, "desc": "task completed"}
    cur = database.cursor()
    cur.execute("UPDATE subtasks SET last_ping=?, progress=? WHERE id=(?)", (int(time.time()), progress, task_id))
    cur.close()
    database.commit()
    return {"ok": True}

def close_task(task_id, user_id):
    task = get_task(task_id)
    if not(task):
        return {"ok": False, "desc": "invalid task id"}
    if task["processing_by"] == None or task["progress"] == -1:
        return {"ok": False, "desc": "task is free"}
    if int(task["processing_by"]) != int(user_id):
        return {"ok": False, "desc": "no rights"}
    cur = database.cursor()
    cur.execute("UPDATE subtasks SET last_ping=-1, progress=-1 WHERE id=(?)", (task_id, ))
    cur.close()
    database.commit()
    return {"ok": True}

def load_networks(networks: list, task_id: int, user_id: int):
    cur = database.cursor()
    user_id = int(user_id)
    task_id = int(task_id)
    cur.executemany(f"INSERT INTO networks VALUES (?,?,?,?,?,?,{task_id},{user_id})", networks)
    cur.close()
    database.commit()

def close_dead_tasks():
    cur = database.cursor()
    cur.execute("UPDATE subtasks SET processing_by=NULL, last_ping=NULL, progress=NULL WHERE last_ping IS NOT NULL AND last_ping!=-1 AND last_ping < (?)", (int(time.time()) - 30, ))
    cur.close()
    database.commit()