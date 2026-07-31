import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base
import models_db
Base.metadata.create_all(bind=engine)

from sqlalchemy.orm import sessionmaker
Session = sessionmaker(bind=engine)
db = Session()

from models_db import DBDecision, DBTransaction, DBFeedback, DBLatency, DBExternalData, DBPolicy
print("=== DB TABLE COUNTS ===")
print(f"Decisions:     {db.query(DBDecision).count()}")
print(f"Transactions:  {db.query(DBTransaction).count()}")
print(f"Feedback:      {db.query(DBFeedback).count()}")
print(f"Latencies:     {db.query(DBLatency).count()}")
print(f"ExternalData:  {db.query(DBExternalData).count()}")
print(f"Policies:      {db.query(DBPolicy).count()}")
db.close()

# Check the DB file
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "policylens.db")
if os.path.exists(db_path):
    size_kb = os.path.getsize(db_path) / 1024
    print(f"\nDB file: {db_path}")
    print(f"DB size: {size_kb:.1f} KB")
else:
    print(f"\nDB file NOT found at: {db_path}")

print("=== DONE ===")
