# Dashboard Development Guide V1.0

---
**Version:** 1.0
**Created:** 2025-11-13
**Last Updated:** 2025-11-13
**Phase:** 9 (Dashboard & Visualization)
**Purpose:** Comprehensive implementation guide for React + Next.js trading dashboard
**Target Audience:** Frontend developers implementing the analytics dashboard
**Related ADRs:** ADR-084 (Dashboard Framework Choice)
**Related Requirements:** REQ-ANALYTICS-004 (Dashboard Implementation)
**Related Documents:** ANALYTICS_ARCHITECTURE_GUIDE_V1.0.md, PERFORMANCE_TRACKING_GUIDE_V1.0.md
---

## Table of Contents

1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [Dashboard Architecture](#dashboard-architecture)
4. [Component Library](#component-library)
5. [Real-Time Integration](#real-time-integration)
6. [API Integration](#api-integration)
7. [Chart Components](#chart-components)
8. [State Management](#state-management)
9. [Performance Optimization](#performance-optimization)
10. [Deployment](#deployment)
11. [Testing Strategy](#testing-strategy)
12. [Security Best Practices](#security-best-practices)

---

## 1. Overview

### Purpose

The Precog trading dashboard provides real-time visibility into trading performance, position monitoring, and edge detection across multiple sports prediction markets.

**Key Features:**
- **Real-time position monitoring** (WebSocket <200ms latency)
- **Performance analytics** (P&L trends, win rates, Sharpe ratios)
- **Edge visualization** (market opportunities, strategy performance)
- **Model evaluation** (prediction accuracy, calibration charts)
- **A/B test dashboards** (strategy comparison, statistical significance)

### Tech Stack Summary

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Framework** | Next.js | 14.x | Server-side rendering + SPA |
| **UI Library** | React | 18.x | Component-based UI |
| **Language** | TypeScript | 5.x | Type safety |
| **Styling** | TailwindCSS | 3.x | Utility-first CSS |
| **Charts** | Plotly.js | 2.x | Interactive financial charts |
| **Real-Time** | Socket.IO Client | 4.x | WebSocket integration |
| **State** | React Context + SWR | - | Global state + data fetching |
| **Testing** | Jest + React Testing Library | - | Unit + integration tests |

---

## 2. Technology Stack

### Installation

```bash
# Create Next.js app with TypeScript
npx create-next-app@latest precog-dashboard --typescript --tailwind --app

cd precog-dashboard

# Install dependencies
npm install plotly.js-dist-min socket.io-client swr axios
npm install -D @types/plotly.js @types/socket.io-client

# Install testing dependencies
npm install -D jest @testing-library/react @testing-library/jest-dom
```

### Project Structure

```
precog-dashboard/
├── src/
│   ├── app/                    # Next.js 14 App Router
│   │   ├── layout.tsx          # Root layout (navigation, providers)
│   │   ├── page.tsx            # Home (dashboard overview)
│   │   ├── positions/
│   │   │   └── page.tsx        # Position monitoring page
│   │   ├── performance/
│   │   │   └── page.tsx        # Performance analytics page
│   │   ├── edges/
│   │   │   └── page.tsx        # Edge detection page
│   │   ├── models/
│   │   │   └── page.tsx        # Model evaluation page
│   │   └── abtests/
│   │       └── page.tsx        # A/B testing page
│   ├── components/
│   │   ├── charts/             # Plotly chart components
│   │   ├── cards/              # Metric cards, stat displays
│   │   ├── tables/             # Data tables (positions, trades)
│   │   └── realtime/           # WebSocket components
│   ├── hooks/
│   │   ├── useWebSocket.ts     # WebSocket connection hook
│   │   ├── usePerformance.ts   # Performance data hook
│   │   └── usePositions.ts     # Position data hook
│   ├── lib/
│   │   ├── api.ts              # REST API client
│   │   ├── websocket.ts        # WebSocket client
│   │   └── utils.ts            # Helper functions
│   └── types/
│       ├── trade.ts            # Trade types
│       ├── position.ts         # Position types
│       └── performance.ts      # Performance metric types
├── public/
├── tests/
├── next.config.js
├── tailwind.config.js
└── package.json
```

---

## 3. Dashboard Architecture

### Page Structure

```typescript
// src/app/layout.tsx - Root Layout
import { Providers } from '@/components/providers';
import { Navigation } from '@/components/navigation';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="flex h-screen">
            {/* Sidebar Navigation */}
            <Navigation />

            {/* Main Content Area */}
            <main className="flex-1 overflow-y-auto p-6 bg-gray-50">
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
```

### Dashboard Pages

#### 1. Home Page (Overview Dashboard)

**URL:** `/`
**Purpose:** High-level overview of trading performance

```typescript
// src/app/page.tsx
import { MetricCard } from '@/components/cards/MetricCard';
import { RecentTradesTable } from '@/components/tables/RecentTradesTable';
import { PerformanceChart } from '@/components/charts/PerformanceChart';
import { usePerformance } from '@/hooks/usePerformance';
import { usePositions } from '@/hooks/usePositions';

export default function HomePage() {
  const { performance, isLoading } = usePerformance('all_time');
  const { positions } = usePositions({ status: 'open' });

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-6">
      {/* Key Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard
          title="Net P&L"
          value={`$${performance.net_pnl.toFixed(2)}`}
          change={performance.pnl_change_pct}
          trend={performance.net_pnl > 0 ? 'up' : 'down'}
        />
        <MetricCard
          title="Win Rate"
          value={`${(performance.win_rate * 100).toFixed(1)}%`}
          target={60}
        />
        <MetricCard
          title="Open Positions"
          value={positions.length}
        />
        <MetricCard
          title="Sharpe Ratio"
          value={performance.sharpe_ratio.toFixed(2)}
        />
      </div>

      {/* Performance Chart */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Performance Trend</h2>
        <PerformanceChart data={performance.daily_pnl} />
      </div>

      {/* Recent Trades */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Recent Trades</h2>
        <RecentTradesTable limit={10} />
      </div>
    </div>
  );
}
```

#### 2. Position Monitoring Page

**URL:** `/positions`
**Purpose:** Real-time position tracking with WebSocket updates

```typescript
// src/app/positions/page.tsx
import { usePositions } from '@/hooks/usePositions';
import { useWebSocket } from '@/hooks/useWebSocket';
import { PositionCard } from '@/components/cards/PositionCard';

export default function PositionsPage() {
  const { positions, updatePosition } = usePositions({ status: 'open' });

  // Subscribe to real-time position updates
  useWebSocket('position_update', (data) => {
    updatePosition(data.position_id, data);
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Open Positions</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {positions.map((position) => (
          <PositionCard key={position.position_id} position={position} />
        ))}
      </div>
    </div>
  );
}
```

#### 3. Performance Analytics Page

**URL:** `/performance`
**Purpose:** Detailed performance breakdowns by strategy, model, league

```typescript
// src/app/performance/page.tsx
import { PerformanceBreakdown } from '@/components/charts/PerformanceBreakdown';
import { StrategyComparisonTable } from '@/components/tables/StrategyComparisonTable';
import { usePerformance } from '@/hooks/usePerformance';

export default function PerformancePage() {
  const { performance } = usePerformance('daily', { groupBy: 'strategy' });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Performance Analytics</h1>

      {/* Strategy Performance Breakdown */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Strategy Performance</h2>
        <PerformanceBreakdown data={performance} groupBy="strategy" />
      </div>

      {/* Comparison Table */}
      <StrategyComparisonTable data={performance} />
    </div>
  );
}
```

---

## 4. Component Library

### Metric Card Component

```typescript
// src/components/cards/MetricCard.tsx
interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  trend?: 'up' | 'down' | 'neutral';
  target?: number;
}

export function MetricCard({ title, value, change, trend, target }: MetricCardProps) {
  const trendColor = trend === 'up' ? 'text-green-600' :
                     trend === 'down' ? 'text-red-600' : 'text-gray-600';

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-sm font-medium text-gray-600 mb-2">{title}</h3>
      <div className="flex items-baseline justify-between">
        <p className="text-3xl font-bold">{value}</p>
        {change !== undefined && (
          <span className={`text-sm font-semibold ${trendColor}`}>
            {change > 0 ? '+' : ''}{change.toFixed(2)}%
          </span>
        )}
      </div>
      {target !== undefined && (
        <div className="mt-2">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Target: {target}</span>
            <span>{((parseFloat(value as string) / target) * 100).toFixed(0)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full"
              style={{ width: `${Math.min((parseFloat(value as string) / target) * 100, 100)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
```

### Position Card Component

```typescript
// src/components/cards/PositionCard.tsx
import { Position } from '@/types/position';

interface PositionCardProps {
  position: Position;
}

export function PositionCard({ position }: PositionCardProps) {
  const pnlColor = position.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600';

  return (
    <div className="bg-white rounded-lg shadow p-4 border-l-4 border-blue-500">
      <div className="flex justify-between items-start mb-2">
        <h3 className="font-semibold text-lg">{position.ticker}</h3>
        <span className={`text-sm font-bold ${pnlColor}`}>
          ${position.unrealized_pnl.toFixed(2)}
        </span>
      </div>

      <div className="space-y-1 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-600">Side:</span>
          <span className="font-medium">{position.side}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Quantity:</span>
          <span className="font-medium">{position.quantity}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Entry Price:</span>
          <span className="font-medium">${position.entry_price.toFixed(4)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Current Price:</span>
          <span className="font-medium">${position.current_price.toFixed(4)}</span>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-200">
        <div className="flex justify-between text-xs text-gray-500">
          <span>Strategy: {position.strategy_name} v{position.strategy_version}</span>
          <span>{position.league}</span>
        </div>
      </div>
    </div>
  );
}
```

---

## 5. Real-Time Integration

### WebSocket Hook

```typescript
// src/hooks/useWebSocket.ts
import { useEffect, useRef } from 'react';
import { io, Socket } from 'socket.io-client';

const WEBSOCKET_URL = process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:8000';

export function useWebSocket(event: string, callback: (data: any) => void) {
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    // Initialize WebSocket connection
    if (!socketRef.current) {
      socketRef.current = io(WEBSOCKET_URL, {
        transports: ['websocket'],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
      });

      socketRef.current.on('connect', () => {
        console.log('[WebSocket] Connected:', socketRef.current?.id);
      });

      socketRef.current.on('disconnect', () => {
        console.log('[WebSocket] Disconnected');
      });
    }

    // Subscribe to event
    socketRef.current.on(event, callback);

    // Cleanup on unmount
    return () => {
      socketRef.current?.off(event, callback);
    };
  }, [event, callback]);

  return socketRef.current;
}
```

### Real-Time Position Hook

```typescript
// src/hooks/usePositions.ts
import { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from './useWebSocket';
import { Position } from '@/types/position';
import { fetchPositions } from '@/lib/api';

interface UsePositionsOptions {
  status?: 'open' | 'monitoring' | 'exited';
  realtime?: boolean;
}

export function usePositions(options: UsePositionsOptions = {}) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Fetch initial positions
  useEffect(() => {
    fetchPositions(options.status)
      .then((data) => {
        setPositions(data);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err);
        setIsLoading(false);
      });
  }, [options.status]);

  // Update position in state
  const updatePosition = useCallback((positionId: number, updates: Partial<Position>) => {
    setPositions((prev) =>
      prev.map((p) =>
        p.position_id === positionId ? { ...p, ...updates } : p
      )
    );
  }, []);

  // Subscribe to real-time updates
  useWebSocket('position_update', (data: Position) => {
    if (options.realtime !== false) {
      updatePosition(data.position_id, data);
    }
  });

  return { positions, isLoading, error, updatePosition };
}
```

---

## 6. API Integration

### REST API Client

```typescript
// src/lib/api.ts
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Performance API
export async function fetchPerformance(
  aggregationLevel: string,
  filters?: Record<string, any>
) {
  const { data } = await apiClient.get('/performance', {
    params: { aggregation_level: aggregationLevel, ...filters },
  });
  return data;
}

// Positions API
export async function fetchPositions(status?: string) {
  const { data } = await apiClient.get('/positions', {
    params: { status },
  });
  return data;
}

// Trades API
export async function fetchRecentTrades(limit: number = 20) {
  const { data } = await apiClient.get('/trades/recent', {
    params: { limit },
  });
  return data;
}

// Edges API
export async function fetchActiveEdges() {
  const { data } = await apiClient.get('/edges/active');
  return data;
}
```

### SWR Data Fetching

```typescript
// src/hooks/usePerformance.ts
import useSWR from 'swr';
import { fetchPerformance } from '@/lib/api';

export function usePerformance(
  aggregationLevel: string,
  filters?: Record<string, any>
) {
  const { data, error, isLoading } = useSWR(
    [`/performance`, aggregationLevel, filters],
    () => fetchPerformance(aggregationLevel, filters),
    {
      refreshInterval: 60000, // Refresh every 60 seconds
      revalidateOnFocus: false,
    }
  );

  return {
    performance: data,
    isLoading,
    error,
  };
}
```

---

## 7. Chart Components

### Performance Line Chart (Plotly)

```typescript
// src/components/charts/PerformanceChart.tsx
import dynamic from 'next/dynamic';
import { useMemo } from 'react';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

interface PerformanceChartProps {
  data: Array<{ date: string; net_pnl: number }>;
}

export function PerformanceChart({ data }: PerformanceChartProps) {
  const chartData = useMemo(() => {
    return [{
      x: data.map((d) => d.date),
      y: data.map((d) => d.net_pnl),
      type: 'scatter',
      mode: 'lines+markers',
      name: 'Net P&L',
      line: { color: '#3B82F6', width: 2 },
      marker: { size: 6 },
    }];
  }, [data]);

  const layout = useMemo(() => ({
    title: 'Daily P&L Trend',
    xaxis: { title: 'Date' },
    yaxis: { title: 'Net P&L ($)', tickformat: '$.2f' },
    hovermode: 'x unified',
    height: 400,
  }), []);

  return (
    <Plot
      data={chartData}
      layout={layout}
      config={{ responsive: true }}
      className="w-full"
    />
  );
}
```

---

## 8. State Management

### Global Providers

```typescript
// src/components/providers.tsx
'use client';

import { SWRConfig } from 'swr';
import { createContext, useContext, useState } from 'react';

// Global settings context
interface SettingsContextValue {
  refreshInterval: number;
  setRefreshInterval: (interval: number) => void;
}

const SettingsContext = createContext<SettingsContextValue | undefined>(undefined);

export function Providers({ children }: { children: React.ReactNode }) {
  const [refreshInterval, setRefreshInterval] = useState(60000);

  return (
    <SettingsContext.Provider value={{ refreshInterval, setRefreshInterval }}>
      <SWRConfig
        value={{
          refreshInterval,
          revalidateOnFocus: false,
          revalidateOnReconnect: true,
        }}
      >
        {children}
      </SWRConfig>
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const context = useContext(SettingsContext);
  if (!context) throw new Error('useSettings must be used within Providers');
  return context;
}
```

---

## 9. Performance Optimization

### Code Splitting & Lazy Loading

```typescript
// Lazy load heavy chart components
import dynamic from 'next/dynamic';

const PerformanceChart = dynamic(() => import('@/components/charts/PerformanceChart'), {
  loading: () => <ChartSkeleton />,
  ssr: false, // Disable SSR for Plotly (browser-only)
});
```

### Memoization

```typescript
import { useMemo } from 'react';

function ExpensiveComponent({ data }) {
  // Memoize expensive calculations
  const processedData = useMemo(() => {
    return data.map((item) => ({
      ...item,
      computedValue: expensiveCalculation(item),
    }));
  }, [data]);

  return <ChartComponent data={processedData} />;
}
```

---

## 10. Deployment

### Environment Variables

```bash
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_WS_URL=http://localhost:8000
```

### Production Build

```bash
npm run build
npm run start
```

---

## 11. Testing Strategy

### Component Tests

```typescript
// tests/components/MetricCard.test.tsx
import { render, screen } from '@testing-library/react';
import { MetricCard } from '@/components/cards/MetricCard';

describe('MetricCard', () => {
  it('renders title and value', () => {
    render(<MetricCard title="Net P&L" value="$1234.56" />);
    expect(screen.getByText('Net P&L')).toBeInTheDocument();
    expect(screen.getByText('$1234.56')).toBeInTheDocument();
  });
});
```

---

## 12. Security Best Practices

### API Authentication

```typescript
// Add JWT token to API requests
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

---

**END OF DASHBOARD_DEVELOPMENT_GUIDE_V1.0.md**
