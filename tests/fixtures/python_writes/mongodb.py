"""MongoDB regression fixture."""


def insert_user(collection, user):
    collection.insert_one(user)


def update_user(collection, user_id, updates):
    collection.update_one({"_id": user_id}, {"$set": updates})
