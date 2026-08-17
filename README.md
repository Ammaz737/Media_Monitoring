# Media Monitoring

Real-time Urdu news monitoring: RTSP/YouTube streams → OCR (UTRNet) → alerts and dashboard.

## What it does

- Captures live video (RTSP or YouTube via `yt-dlp`)
- Extracts Urdu text from ticker/headline regions
- Stores results in PostgreSQL and triggers keyword alerts
- **Backend:** Flask API (`:5000`) · **Frontend:** Next.js (`:3000`)

## Requirements

- Python 3.10+
- PostgreSQL 14+ (local server or `DATABASE_URL`)
- Node.js 18+ (for dashboard)
- UTRNet weights: `best_norm_ED.pth` in  
  `UTRNet-High-Resolution-Urdu-Text-Recognition-main/UTRNet-High-Resolution-Urdu-Text-Recognition-main/`
- Optional: CUDA GPU (CPU works, slower OCR)

## Quick start

```bash
# Postgres (once): createdb news_monitor
# Optional: copy .env.example to .env and set DATABASE_URL

# Backend
cd news_monitor
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
pip install yt-dlp             # for YouTube URLs
# One-shot if you have an existing SQLite file:
python migrate_sqlite_to_postgres.py
# Schema is applied on startup (Alembic). Or: alembic upgrade head
python main.py --mode web      # http://127.0.0.1:5000

# Frontend (new terminal)
cd news_monitor/frontend
npm install
npm run dev                    # http://localhost:3000
```

Sign in at `/login` (default `admin` / `admin` — set `ADMIN_PASSWORD` in `.env`).

Open the dashboard → paste RTSP or YouTube live URL → **Start Monitoring**.

## Configuration

Edit `news_monitor/config.py`:

- `RTSP_CHANNELS` — broadcast stream URLs
- `TEXT_REGIONS` / `YOUTUBE_TEXT_REGIONS` — OCR crop areas
- `ALERTS_CONFIG['keywords']` — alert keywords (Urdu/English)

## Project layout

| Path | Role |
|------|------|
| `news_monitor/` | Core monitor, Flask API, database |
| `news_monitor/frontend/` | Next.js UI |
| `UTRNet-.../` | UTRNet model source (weights not in repo) |

## Not in Git (see `.gitignore`)

- `venv/`, `node_modules/`, `.next/`
- `best_norm_ED.pth`, local `.env`, old `news_monitor/data/*.db`
- Screenshots and local logs

## License

UTRNet code follows its upstream license in `UTRNet-High-Resolution-Urdu-Text-Recognition-main/`.
