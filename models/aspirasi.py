from bson.objectid import ObjectId

def insert_aspirasi(db, user_id, judul, isi, kategori, urgensi):
    return db.aspirasi.insert_one({
        "user_id": user_id,
        "judul": judul,
        "isi": isi,
        "kategori": kategori,
        "urgensi": urgensi,
        "status": "menunggu",
        "prioritas": None,
        "tanggapan": None
    })

def get_aspirasi_by_user(db, user_id):
    return list(db.aspirasi.find({"user_id": user_id}))

def get_all_aspirasi(db):
    return list(db.aspirasi.find())

def update_prioritas(db, asp_id, prioritas):
    return db.aspirasi.update_one(
        {"_id": ObjectId(asp_id)},
        {"$set": {"prioritas": prioritas, "status": "diperiksa"}}
    )

def update_tanggapan(db, asp_id, tanggapan):
    return db.aspirasi.update_one(
        {"_id": ObjectId(asp_id)},
        {"$set": {"tanggapan": tanggapan, "status": "ditanggapi"}}
    )
