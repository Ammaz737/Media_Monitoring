# News Monitor — Next.js Frontend

Component-based dashboard for the News Monitor Flask API.

## Prerequisites

- Flask backend running: `python main.py --mode web` (port **5000**)
- Node.js 18+

## Run

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Environment

Copy `.env.local`:

```
NEXT_PUBLIC_API_URL=http://127.0.0.1:5000
NEXT_PUBLIC_SOCKET_URL=http://127.0.0.1:5000
```

## Pages

| Route | Features |
|-------|----------|
| `/` | Dashboard — stats, activity tabs, live chart, start/stop monitor |
| `/search` | Text + audio search with filters |
| `/alerts` | All / unread / read alerts, mark as read |
| `/settings` | Read-only config from `/api/config` |

## Stack

- Next.js 14 (App Router)
- Tailwind CSS + shadcn-style components
- Recharts (live activity)
- Socket.IO client (real-time updates)
