from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")

db = client["employee_registry"]

def get_collection():
    """
    Returns the resumes collection
    """
    return db["employee_resume_data"]