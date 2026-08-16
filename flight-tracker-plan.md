# Uçuş Takip Sistemi — Proje Planı

> Bu bir Endorfyn ödevi. Amaç: web arayüzlü bir uçuş takip (flight tracking) sistemi.
> **Önemli not (kendine hatırlat):** AI'dan kod yardımı almak serbest (Şafak onayladı), AMA her parçanın
> mantığını anlaman şart. "Kopyala-yapıştır-çalıştı-geç" değil; "çalıştır-anla-sahiplen". Teslimde
> her şeyi açıklayabilmelisin. Test edilen şey full-stack bilgin değil — öğrenme hızın, AI'ı akıllı
> kullanman ve sistemi anlaman.

---

## Ödevin Tam Tanımı

Web arayüzlü bir uçuş takip uygulaması. Üç ana parça: **frontend (React)**, **backend (REST)**, **database**.

**Frontend'de olacaklar:**
- Bir harita (Leaflet)
- Uçuş planlamak için bir panel
- Haritada gösterilen zamanı ayarlayan bir slider (zaman çubuğu)
- Uçuşlar harita üzerinde: uçak ikonu + başlangıç/bitiş işaretleri (nokta) + rota (kesikli çizgi)
- Aynı anda birden çok uçuş gösterilebilmeli
- Uçak ikonuna tıklayınca bilgi paneli açılmalı (başlangıç saati, ID, nereden, nereye)
- Görsel iyileştirmeler serbest

**Backend'de olacaklar:**
- Planlanan uçuşlar database'e yazılmalı
- Frontend istedikçe uçuş bilgileri database'den çekilip iletilmeli
- Bağımsız bir simülatör backend'e bağlanacak:
  - Bir REST ucundan planlanan uçuşları **sorgulayacak**
  - Başka bir REST ucuna o uçuşlar için **konum bilgisi gönderecek**
  - Sen bu konum bilgilerini database'e yazacaksın
  - Sonra haritadaki uçuşları bu konumlarla güncelleyeceksin

**Zaman mantığı (en zor kısım):**
- Slider geçmiş bir tarihi gösterirken simülatörden veri gelmeye devam edebilir
- Gelen veri database'e yazılır AMA ekranda gösterilen zamana ait değilse haritada gösterilmez
- Çözüm için **Canlı Mod / Geri Oynatım Modu** ayrımı yapılabilir (yöntem serbest)

---

## Teknoloji Kararı

| Katman | Seçim | Neden |
|---|---|---|
| Frontend | **React + react-leaflet** | React istendi. react-leaflet = Leaflet'in React hali (Leaflet zaten biliniyor) |
| Backend | **Python + FastAPI** | Python biliniyor. FastAPI REST için modern, hızlı, kolay |
| Database | **SQLite** (başlangıç) → gerekirse PostgreSQL | SQLite kurulumsuz, dosya tabanlı, öğrenmek için ideal |
| IDE | **VS Code** (Claude Code eklentisiyle ideal) | Çok dosyalı proje, terminalden çıkmadan çalışma |

**Not:** Backend için Node.js/Express de alternatif ama Python biliniyorsa FastAPI daha hızlı ilerletir.

---

## Ön Bilgi: Zaten Bilinenler vs Yeni Öğrenilecekler

**Elde olanlar (bu ödevin yarısı):**
- Leaflet, harita, tile mantığı
- GeoJSON, koordinat, geometri tipleri (nokta, çizgi/rota = LineString)
- Marker, popup (tıklayınca bilgi gösterme)
- Database'e yazma/okuma mantığı (Firebase'den)
- Python, C

**Yeni öğrenilecekler:**
- React (component, state, props)
- react-leaflet (Leaflet'in React sarmalı)
- Kendi REST backend'i (FastAPI)
- Simülatör entegrasyonu (REST uçları)
- Gerçek zamanlı konum güncelleme
- Zaman modu (canlı / geri oynatım) — en zor

---

## React — Minimum Temel (kullanınca oturur)

- **Component:** Arayüz parçası. `<Map />`, `<Panel />`, `<Slider />` gibi. Her biri ayrı dosya/fonksiyon.
- **State:** Component'in hafızası. Değişince ekran otomatik güncellenir. (Örn: "seçili uçuş", "gösterilen zaman")
- **Props:** Component'ler arası veri geçişi. Ana component → alt component'e veri gönderir.
- Derinlemesine teori gerekmez; yaparak öğrenilecek.

---

## Fazlar — Dikey Dilimlerle İlerleme

> Kural: Her faz **çalışan bir şey** üretir. "Önce hepsini araştır, sonra birleştir" YAPMA.
> Küçük ama uçtan uca çalışan parçalar yap, üstüne koy. Her fazı çalıştır, anla, sonra sıradaki.

### Faz 0 — Kurulum
- [ ] Node.js kontrol (`node --version`, `npm --version`); yoksa kur (`brew install node` ya da nodejs.org)
- [ ] Vite ile React projesi: `npm create vite@latest flight-tracker -- --template react`
- [ ] `cd flight-tracker && npm install && npm run dev` → varsayılan sayfa çıksın (`localhost:5173`)
- [ ] Leaflet ekle: `npm install leaflet react-leaflet`
- **Çıktı:** Boş React projesi ayakta

### Faz 1 — Frontend İskelet: Harita
- [ ] Varsayılan React sayfasını temizle
- [ ] `react-leaflet` ile bir harita göster (`<MapContainer>`, `<TileLayer>`) — OpenStreetMap tile
- [ ] Harita Türkiye/Ankara merkezli çıksın
- **Çıktı:** React içinde çalışan harita
- **Öğrenilen:** react-leaflet, ilk component

### Faz 2 — Uçuş Gösterimi (elle, statik)
- [ ] Elle tanımlı bir uçuş verisi (ID, başlangıç noktası, bitiş noktası, başlangıç saati)
- [ ] Haritada göster: başlangıç/bitiş marker'ları + rota (kesikli polyline) + uçak ikonu
- [ ] Birden fazla uçuşu aynı anda gösterebil
- **Çıktı:** Haritada statik uçuşlar (uçak + rota + noktalar)
- **Öğrenilen:** react-leaflet marker/polyline, özel ikon, kesikli çizgi (dashArray)

### Faz 3 — Uçak Tıklama → Bilgi Paneli
- [ ] Uçak ikonuna tıklanınca yan panel açılsın
- [ ] Panelde: ID, başlangıç saati, nereden, nereye
- [ ] "Seçili uçuş" bir **state** olacak; tıklayınca değişecek, panel güncellenecek
- **Çıktı:** Tıklanabilir uçaklar + bilgi paneli
- **Öğrenilen:** React state, event, component'ler arası iletişim

### Faz 4 — Uçuş Planlama Paneli
- [ ] Kullanıcı yeni uçuş planlayabilsin: başlangıç, bitiş, ID, başlangıç saati giren bir form/panel
- [ ] Planlanan uçuş haritaya eklensin (henüz sadece frontend'de)
- **Çıktı:** Kullanıcı uçuş planlayabiliyor
- **Öğrenilen:** React form, state'e ekleme

### Faz 5 — Backend + Database
- [ ] FastAPI backend kur (`pip install fastapi uvicorn`)
- [ ] SQLite database: uçuşlar tablosu (id, başlangıç, bitiş, başlangıç_saati, rota...)
- [ ] REST uçları:
  - `POST /flights` → planlanan uçuşu database'e yaz
  - `GET /flights` → uçuşları çek
- [ ] Frontend'i backend'e bağla: planlama → POST, gösterim → GET
- **Çıktı:** Uçuşlar database'de kalıcı, frontend'den yazılıp okunuyor
- **Öğrenilen:** FastAPI, REST endpoint, SQLite, frontend-backend iletişimi (fetch)

### Faz 6 — Simülatör REST Uçları
> **DİKKAT:** Simülatörün beklediği format Şafak'a sorulmalı (endpoint isimleri, veri yapısı).
> Format belliyse ona uy; belli değilse mantıklı bir tasarım yap ve dokümante et.
- [ ] `GET /flights/planned` (ya da benzeri) → simülatör planlanan uçuşları sorgular
- [ ] `POST /flights/positions` (ya da benzeri) → simülatör konum bilgisi gönderir
- [ ] Gelen konum bilgileri database'e yazılır (konumlar tablosu: uçuş_id, konum, zaman)
- **Çıktı:** Simülatör backend'e bağlanıp konum gönderebiliyor
- **Öğrenilen:** REST API tasarımı, dış sistem entegrasyonu

### Faz 7 — Gerçek Zamanlı Konum Güncelleme
- [ ] Frontend periyodik olarak (ya da WebSocket ile) konum verisini çeksin
- [ ] Haritadaki uçak ikonları gelen konumlarla hareket etsin
- **Çıktı:** Uçaklar canlı hareket ediyor
- **Öğrenilen:** Periyodik güncelleme (polling) ya da WebSocket, harita üzerinde konum güncelleme

### Faz 8 — Zaman Slider + Canlı/Geri Oynatım Modu (EN ZOR)
- [ ] Slider ile gösterilen zaman ayarlanabilsin
- [ ] **Canlı Mod:** slider "şimdi"deyse, gelen son konumlar gösterilir
- [ ] **Geri Oynatım Modu:** slider geçmişteyse, o ana ait konumlar database'den çekilip gösterilir
- [ ] Simülatörden veri gelmeye devam etse bile, gösterilen zamana ait değilse haritada gösterilmez
      (ama database'e yine yazılır)
- **Çıktı:** Zaman kontrolü + iki mod
- **Öğrenilen:** Zaman bazlı veri filtreleme, mod yönetimi (state), geçmiş sorgulama

---

## Genel Mimari (Akış)

```
┌─────────────┐        REST         ┌─────────────┐        ┌──────────┐
│  Frontend   │ ◄─────────────────► │   Backend   │ ◄────► │ Database │
│  (React +   │  GET/POST flights   │  (FastAPI)  │  SQL   │ (SQLite) │
│   Leaflet)  │  GET positions      │             │        │          │
└─────────────┘                     └─────────────┘        └──────────┘
                                          ▲
                                          │ REST
                                          │ (planlanan uçuşları sorgular,
                                          │  konum gönderir)
                                    ┌─────────────┐
                                    │  Simülatör  │  (bağımsız, dışarıdan)
                                    └─────────────┘
```

- Frontend uçuş planlar → Backend database'e yazar
- Simülatör planlanan uçuşları sorgular → konum gönderir → Backend database'e yazar
- Frontend konumları çeker → haritada uçakları günceller
- Zaman slider'ı hangi anın gösterileceğini belirler (canlı / geçmiş)

---

## Kritik Hatırlatmalar

1. **Simülatör formatını Şafak'a sor** — backend'i o belirleyecek. Yanlış tasarlarsan baştan yazarsın. (Faz 6'dan önce netleştir.)
2. **Deadline yok** ama açık uçlu bırakma — kendine bir hedef koy, yoksa asılı kalır.
3. **Faz faz git** — her fazı çalıştır, gör, anla. Hepsini birden AI'a yaptırma.
4. **Her parçayı sahiplen** — teslimde "şu şöyle çalışıyor, mimariyi ben kurdum, kod yardımı AI'dan" diyebilmelisin.
5. **Yarısını zaten biliyorsun** (harita, GeoJSON, database mantığı) — panik yok, yeni olan React + kendi backend + zaman modu.
6. **Uçuş = savunma bağlantısı:** uçak konumu (nokta), rota (LineString), bilgi (properties) — bu, daha önce konuşulan "hedef takibi / komuta kontrol" mantığının aynısı.

---

## İlk Adım

1. Şafak'a simülatör formatını sor (Faz 6 için, ama şimdiden netleşsin)
2. `node --version` kontrol
3. Faz 0'a başla (React projesi kur)
4. Faz faz ilerle, her fazı çalıştırıp anla

Başarılar. Her fazda "bu ne yapıyor, neden böyle" diye dur — sahiplen, kopyalama.
