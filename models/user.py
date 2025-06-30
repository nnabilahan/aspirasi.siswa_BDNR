from flask import session
from bson.objectid import ObjectId

def insert_user(db, username, password, role):
    return db.users.insert_one({
        "username": username,
        "password": password,  # Note: Belum terenkripsi, disarankan pakai hashing
        "role": role
    })

def get_user_by_username(db, username):
    return db.users.find_one({"username": username})

def get_user_by_id(db, user_id):
    return db.users.find_one({"_id": ObjectId(user_id)})
