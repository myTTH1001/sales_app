from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.orm import Session

DATABASE_URL = "postgresql://postgres:04102000@localhost:5432/sales_db"

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

# 👇 THÊM HÀM NÀY
def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()