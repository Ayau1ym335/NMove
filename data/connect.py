from sqlalchemy import create_engine, text

# 1. Define your connection string
# Format: postgresql://username:password@host:port/database
DATABASE_URL = "postgresql://postgres:Ayaulym^2011@localhost:5432/stridex"

# 2. Create the Engine (The central source of the connection)
engine = create_engine(DATABASE_URL)

def check_connection():
    try:
        # 3. Connect and execute
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            print(f"Success! Database version: {result.fetchone()[0]}")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    check_connection()