
from db.mongo import get_collection


collection = get_collection()

def store_resume(payload: dict):
    """
    Store parsed resume in MongoDB
    """

    data = payload["data"]
    result = collection.insert_one(data)

    return {"inserted_id": str(result.inserted_id)}

def get_candidates(payload: dict):
    """
    Basic filtered search
    """

    filters = payload.get("filters", {})

    results = list(collection.find(filters, {"_id": 0}))
    return results