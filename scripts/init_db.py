"""Initialize the database – creates all tables."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from database import init_db

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")