from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

# Docker'da çalıştırdığımız PostGIS veritabanı bağlantı adresi
SQLALCHEMY_DATABASE_URL = "postgresql://flightuser:flightpassword@localhost:5432/flightdb"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
