# Site Layout Frontend

Next.js frontend for the automated site layout tool.

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Map Rendering**: Deck.gl + Mapbox GL
- **State Management**: Zustand
- **Data Fetching**: TanStack Query (React Query)

## Getting Started

### Prerequisites

- Node.js 18+ and pnpm

### Installation

```bash
pnpm install
```

### Development

```bash
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build

```bash
pnpm build
pnpm start
```

## Environment Variables

Copy `.env.example` to `.env.local` and configure:

- `NEXT_PUBLIC_API_URL`: Backend API URL
- `NEXT_PUBLIC_MAPBOX_TOKEN`: Mapbox access token

## Deployment

Deployed automatically to Vercel on push to main branch.
