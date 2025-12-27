from sqlalchemy import text
from app.db.session import engine

def migrate():
    with engine.connect() as connection:
        print("Migrating database...")
        try:
            connection.execute(text("ALTER TABLE resumes MODIFY content LONGTEXT;"))
            print("Successfully modified 'content' column to LONGTEXT.")
        except Exception as e:
            print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
