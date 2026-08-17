import os
from sqlalchemy import create_engine
from models import Base

# DB bağlantısı
SQLALCHEMY_DATABASE_URL = "postgresql://flightuser:flightpassword@localhost:5432/flightdb"
engine = create_engine(SQLALCHEMY_DATABASE_URL)

print("🧹 Veritabanındaki tüm tablolar ve kayıtlar siliniyor...")
Base.metadata.drop_all(bind=engine)

print("🏗️ Tablolar sıfırdan ve bomboş olarak tekrar oluşturuluyor...")
Base.metadata.create_all(bind=engine)

print("✅ Veritabanı başarıyla ilk günkü tertemiz haline getirildi!")
