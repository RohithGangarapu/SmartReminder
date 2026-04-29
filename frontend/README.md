# SmartReminder Frontend

Simple React frontend for the SmartReminder backend.

## Run

1. Install dependencies:
   `npm install`
2. Start dev server:
   `npm run dev`

## Backend

- During development, `/api` requests are proxied to `http://127.0.0.1:8000`.
- If you serve frontend separately, copy `.env.example` to `.env` and set `VITE_API_BASE_URL`.

## Main flows

- Register or login
- Create, edit, delete tasks
- Extract task title and datetime from natural language
- Connect Gmail
- Connect Google Calendar and sync tasks
- Connect WhatsApp
