#!/bin/bash

# Çalıştığı dizine geç
cd "$(dirname "$0")"

echo "=========================================="
echo "🚀 Uçuş Takip Sistemi Başlatılıyor..."
echo "=========================================="

# Docker Desktop'ı kontrol et ve aç (Mac için)
echo "🐳 Docker Desktop başlatılıyor (Eğer kapalıysa)..."
open -a Docker

echo "⏳ Docker motorunun hazır olması bekleniyor (Bu işlem birkaç saniye sürebilir)..."
while ! docker info > /dev/null 2>&1; do
    sleep 2
done
echo "✅ Docker motoru hazır!"

# 1. Veritabanını (Docker) ayağa kaldır
echo "📦 Veritabanı başlatılıyor (Docker)..."
cd backend
docker-compose up -d
cd ..

# 2. Arka plan süreçlerini temizle (Eğer daha önce açık kalmışlarsa)
echo "🧹 Eski süreçler temizleniyor..."
pkill -f "uvicorn main:app"
pkill -f "uvicorn simulator_service.simulator_main:app"
# Portları kullanan processleri de düşürebiliriz ama pkill yeterli olacaktır.

# Python sanal ortamının (venv) yolunu belirle
VENV_ACTIVATE="./backend/venv/bin/activate"

# 3. Ana Backend'i Başlat (Port 8000)
echo "⚙️ Ana Backend (Port 8000) başlatılıyor..."
(
    cd backend
    source venv/bin/activate
    uvicorn main:app --port 8000 --reload
) &
BACKEND_PID=$!

# 4. Simülatör Servisini Başlat (Port 8001)
echo "✈️ Simülatör Servisi (Port 8001) başlatılıyor..."
(
    cd backend/simulator_service
    source ../venv/bin/activate
    uvicorn simulator_main:app --port 8001 --reload
) &
SIMULATOR_PID=$!

# 5. Frontend'i Başlat (Port 5173)
echo "🎨 Frontend (Port 5173) başlatılıyor..."
(
    cd flight-tracker
    npm run dev
) &
FRONTEND_PID=$!

echo "=========================================="
echo "✅ Tüm sistemler başarıyla başlatıldı!"
echo "   - Frontend:   http://localhost:5173"
echo "   - Simülatör:  http://localhost:8001/ui"
echo "   - Backend:    http://localhost:8000/docs"
echo "=========================================="
echo "🔴 Sistemi durdurmak için bu pencerede CTRL+C tuşlarına basın."

# Kapatma sinyallerini (CTRL+C) yakala ve alt süreçleri de kapat
trap "echo 'Sistemler kapatılıyor...'; kill $BACKEND_PID $SIMULATOR_PID $FRONTEND_PID; exit" SIGINT SIGTERM EXIT

# Arka plan işlemlerinin bitmesini bekle (Kapanmasını engeller)
wait
