import React, { useState, useEffect, useRef } from 'react';
import {
  Activity,
  Play,
  Square,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Clock,
  Database,
  Radio,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Layers,
  BarChart2,
} from 'lucide-react';
import { calcEngineApi } from '../../api/calcEngineApi';
import { IndicatorCard } from './IndicatorCard';
import { LiveSignalFeed } from './LiveSignalFeed';
import { StrategyConditionPanel } from './StrategyConditionPanel';
import { useToast } from '../../context/ToastContext';

const PRESET_SYMBOLS = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'RELIANCE', 'TCS', 'INFY', 'HDFCBANK'];
const TIMEFRAMES = [
  { id: '1m', label: '1 Min' },
  { id: '5m', label: '5 Min' },
  { id: '15m', label: '15 Min' },
  { id: '1h', label: '1 Hour' },
  { id: '1d', label: 'Daily' },
];

export const CalculationEnginePage = () => {
  const { addToast } = useToast?.() || { addToast: (msg) => console.log(msg) };

  // State
  const [selectedSymbol, setSelectedSymbol] = useState('NIFTY');
  const [customSymbol, setCustomSymbol] = useState('');
  const [timeframe, setTimeframe] = useState('5m');
  const [isRunning, setIsRunning] = useState(false);
  const [loading, setLoading] = useState(false);
  const [snapshot, setSnapshot] = useState(null);
  const [signals, setSignals] = useState([]);
  const [conditions, setConditions] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [lastTickTime, setLastTickTime] = useState(null);

  const wsRef = useRef(null);
  const symbolToUse = customSymbol.trim() ? customSymbol.trim().toUpperCase() : selectedSymbol;

  // 1. Fetch initial snapshot and conditions
  const loadData = async () => {
    setLoading(true);
    try {
      // Check status to see if engine is already running
      const statusRes = await calcEngineApi.getStatuses().catch(() => ({ data: [] }));
      const runningList = statusRes.data || [];
      const currentRunning = runningList.find((s) => s.symbol === symbolToUse && s.is_running);
      setIsRunning(!!currentRunning);

      // Fetch snapshot
      const snapRes = await calcEngineApi.getSnapshot(symbolToUse, timeframe);
      if (snapRes.data) {
        setSnapshot(snapRes.data);
      }

      // Fetch active conditions
      const condRes = await calcEngineApi.getConditions(symbolToUse).catch(() => ({ data: [] }));
      setConditions(condRes.data || []);

      // Fetch recent signals
      const sigRes = await calcEngineApi.getSignals(symbolToUse).catch(() => ({ data: [] }));
      setSignals(sigRes.data || []);
    } catch (err) {
      console.error('Error loading calculation engine data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [symbolToUse, timeframe]);

  // 2. WebSocket real-time subscription
  useEffect(() => {
    let ws = null;
    let reconnectTimeout = null;

    const connectWs = () => {
      try {
        const wsUrl = 'ws://localhost:8000/ws/calc-engine';
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          setWsConnected(true);
          console.log('CalcEngine WebSocket connected');
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);

            if (msg.type === 'TICK_UPDATE' && msg.symbol === symbolToUse) {
              setLastTickTime(new Date());
              setSnapshot((prev) => {
                if (!prev) return prev;
                return {
                  ...prev,
                  ltp: msg.ltp !== undefined ? msg.ltp : prev.ltp,
                  vwap: msg.vwap !== undefined ? msg.vwap : prev.vwap,
                };
              });
            } else if (msg.type === 'INDICATOR_SNAPSHOT' && msg.symbol === symbolToUse) {
              setSnapshot(msg.data);
              if (msg.recent_signals) {
                setSignals(msg.recent_signals);
              }
            } else if (msg.type === 'SIGNAL_EVENT') {
              const sig = msg.data;
              if (sig.symbol === symbolToUse) {
                setSignals((prev) => [sig, ...prev.slice(0, 49)]);
                addToast(`⚡ Signal Fired: ${sig.signal} on ${sig.symbol} (${sig.condition_text})`, 'success');
              }
            }
          } catch (e) {
            console.error('WebSocket parse error:', e);
          }
        };

        ws.onclose = () => {
          setWsConnected(false);
          reconnectTimeout = setTimeout(connectWs, 3000);
        };

        ws.onerror = () => {
          setWsConnected(false);
        };

        wsRef.current = ws;
      } catch (e) {
        console.error('WebSocket connect error:', e);
      }
    };

    connectWs();

    return () => {
      if (ws) ws.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [symbolToUse]);

  // Periodic polling fallback for UI freshness
  useEffect(() => {
    const interval = setInterval(() => {
      if (isRunning) {
        calcEngineApi.getSnapshot(symbolToUse, timeframe).then((res) => {
          if (res.data) setSnapshot(res.data);
        }).catch(() => {});

        calcEngineApi.getSignals(symbolToUse).then((res) => {
          if (res.data) setSignals(res.data);
        }).catch(() => {});
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [isRunning, symbolToUse, timeframe]);

  // Actions: Start & Stop Engine
  const handleStartEngine = async () => {
    setLoading(true);
    try {
      await calcEngineApi.startEngine({
        symbol: symbolToUse,
        timeframe,
        exchange: 'NSE_EQ',
      });
      setIsRunning(true);
      addToast(`Live calculation engine started for ${symbolToUse}!`, 'success');
      loadData();
    } catch (err) {
      console.error(err);
      addToast(`Failed to start engine: ${err.message || 'Unknown error'}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleStopEngine = async () => {
    setLoading(true);
    try {
      await calcEngineApi.stopEngine(symbolToUse);
      setIsRunning(false);
      addToast(`Engine stopped for ${symbolToUse}`, 'info');
    } catch (err) {
      console.error(err);
      addToast(`Failed to stop engine: ${err.message || 'Unknown error'}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  // Derive consensus / bias from indicators
  const getConsensusBias = () => {
    if (!snapshot || !snapshot.indicators || snapshot.indicators.length === 0) {
      return { label: 'CALCULATING', color: 'var(--text-muted)' };
    }
    const buys = snapshot.indicators.filter((i) => i.signal === 'BUY').length;
    const sells = snapshot.indicators.filter((i) => i.signal === 'SELL').length;

    if (buys >= sells + 2) return { label: 'STRONG BULLISH', color: 'var(--accent-emerald)', bg: 'rgba(16, 185, 129, 0.15)' };
    if (buys > sells) return { label: 'MODERATE BULLISH', color: 'var(--accent-emerald)', bg: 'rgba(16, 185, 129, 0.1)' };
    if (sells >= buys + 2) return { label: 'STRONG BEARISH', color: 'var(--accent-rose)', bg: 'rgba(244, 63, 94, 0.15)' };
    if (sells > buys) return { label: 'MODERATE BEARISH', color: 'var(--accent-rose)', bg: 'rgba(244, 63, 94, 0.1)' };
    return { label: 'NEUTRAL / RANGEBOUND', color: 'var(--accent-amber)', bg: 'rgba(245, 158, 11, 0.1)' };
  };

  const consensus = getConsensusBias();
  const vwapDiff = snapshot && snapshot.ltp && snapshot.vwap ? snapshot.ltp - snapshot.vwap : 0;
  const isAboveVwap = vwapDiff >= 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Hero Banner */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%)',
          backdropFilter: 'blur(16px)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '16px',
          padding: '24px 28px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, #38bdf8 0%, #0284c7 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 0 16px rgba(56, 189, 248, 0.4)',
              }}
            >
              <Activity size={20} color="#fff" />
            </div>
            <div>
              <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
                Live Calculation Engine
              </h1>
              <p style={{ margin: '2px 0 0', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Real-time technical indicators computed directly from Dhan tick feeds with yfinance failover
              </p>
            </div>
          </div>
        </div>

        {/* Live Status Indicators */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* WebSocket Status */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '999px',
              background: wsConnected ? 'rgba(16, 185, 129, 0.12)' : 'rgba(255, 255, 255, 0.05)',
              border: `1px solid ${wsConnected ? 'rgba(16, 185, 129, 0.3)' : 'var(--border-subtle)'}`,
              fontSize: '0.75rem',
              color: wsConnected ? 'var(--accent-emerald)' : 'var(--text-dim)',
              fontWeight: 600,
            }}
          >
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: wsConnected ? '#10b981' : '#64748b',
                boxShadow: wsConnected ? '0 0 8px #10b981' : 'none',
              }}
            />
            <span>{wsConnected ? 'WebSocket Live' : 'Connecting WS'}</span>
          </div>

          {/* Data Source Badge */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '999px',
              background: 'rgba(56, 189, 248, 0.1)',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              fontSize: '0.75rem',
              color: 'var(--accent-cyan)',
              fontWeight: 600,
            }}
          >
            <Database size={13} />
            <span>{snapshot?.data_source || 'DHAN'}</span>
          </div>

          {/* Engine Running Badge */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '999px',
              background: isRunning ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.15)',
              border: `1px solid ${isRunning ? 'rgba(16, 185, 129, 0.5)' : 'rgba(245, 158, 11, 0.4)'}`,
              fontSize: '0.8rem',
              color: isRunning ? 'var(--accent-emerald)' : 'var(--accent-amber)',
              fontWeight: 700,
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: isRunning ? '#10b981' : '#f59e0b',
                animation: isRunning ? 'pulse 1.5s infinite' : 'none',
              }}
            />
            <span>{isRunning ? 'ENGINE ACTIVE' : 'ENGINE IDLE'}</span>
          </div>
        </div>
      </div>

      {/* Control Toolbar */}
      <div
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '14px',
          padding: '16px 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        {/* Symbol Selector Presets */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>
            Symbol:
          </span>
          {PRESET_SYMBOLS.map((sym) => (
            <button
              key={sym}
              onClick={() => {
                setSelectedSymbol(sym);
                setCustomSymbol('');
              }}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: 'pointer',
                background: symbolToUse === sym ? 'rgba(56, 189, 248, 0.15)' : 'rgba(255, 255, 255, 0.03)',
                color: symbolToUse === sym ? 'var(--accent-cyan)' : 'var(--text-muted)',
                border: symbolToUse === sym ? '1px solid rgba(56, 189, 248, 0.4)' : '1px solid var(--border-subtle)',
                transition: 'all 0.15s ease',
              }}
            >
              {sym}
            </button>
          ))}

          {/* Custom Symbol Input */}
          <input
            type="text"
            placeholder="Custom (e.g. INFY)"
            value={customSymbol}
            onChange={(e) => setCustomSymbol(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: '8px',
              fontSize: '0.8rem',
              background: 'var(--bg-input)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-main)',
              width: '130px',
              outline: 'none',
            }}
          />
        </div>

        {/* Timeframe & Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          {/* Timeframe selector */}
          <div style={{ display: 'flex', background: 'var(--bg-input)', padding: '3px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf.id}
                onClick={() => setTimeframe(tf.id)}
                style={{
                  padding: '5px 10px',
                  borderRadius: '6px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: 'none',
                  background: timeframe === tf.id ? 'var(--accent-cyan)' : 'transparent',
                  color: timeframe === tf.id ? '#080c14' : 'var(--text-muted)',
                  transition: 'all 0.15s ease',
                }}
              >
                {tf.label}
              </button>
            ))}
          </div>

          {/* Manual Refresh */}
          <button
            onClick={loadData}
            disabled={loading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: '8px',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-main)',
            }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Recalculate</span>
          </button>

          {/* Start / Stop Toggle */}
          {isRunning ? (
            <button
              onClick={handleStopEngine}
              disabled={loading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 18px',
                borderRadius: '8px',
                fontSize: '0.8rem',
                fontWeight: 700,
                cursor: 'pointer',
                background: 'rgba(244, 63, 94, 0.15)',
                border: '1px solid rgba(244, 63, 94, 0.4)',
                color: 'var(--accent-rose)',
              }}
            >
              <Square size={14} />
              <span>Stop Engine</span>
            </button>
          ) : (
            <button
              onClick={handleStartEngine}
              disabled={loading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 20px',
                borderRadius: '8px',
                fontSize: '0.8rem',
                fontWeight: 700,
                cursor: 'pointer',
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                border: 'none',
                color: '#fff',
                boxShadow: '0 0 16px rgba(16, 185, 129, 0.35)',
              }}
            >
              <Play size={14} fill="#fff" />
              <span>Start Live Engine</span>
            </button>
          )}
        </div>
      </div>

      {/* Primary Key Stats Bar */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '16px',
        }}
      >
        {/* Spot Price (LTP) */}
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '12px',
            padding: '16px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}
        >
          <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-dim)', fontWeight: 600 }}>
            {symbolToUse} Spot Price (LTP)
          </span>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: "'Outfit', sans-serif" }}>
              {snapshot?.ltp ? snapshot.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '--'}
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>INR</span>
          </div>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
            Updated: {snapshot?.timestamp ? new Date(snapshot.timestamp).toLocaleTimeString() : '--'}
          </span>
        </div>

        {/* Session VWAP */}
        <div
          style={{
            background: 'var(--bg-card)',
            border: `1px solid ${isAboveVwap ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
            borderRadius: '12px',
            padding: '16px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}
        >
          <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-dim)', fontWeight: 600 }}>
            Session VWAP (Anchor)
          </span>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--accent-cyan)', fontFamily: "'Outfit', sans-serif" }}>
              {snapshot?.vwap ? snapshot.vwap.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '--'}
            </span>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                color: isAboveVwap ? 'var(--accent-emerald)' : 'var(--accent-rose)',
              }}
            >
              {isAboveVwap ? '▲ Price Above' : '▼ Price Below'}
            </span>
          </div>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            Spread: {isAboveVwap ? '+' : ''}{vwapDiff.toFixed(2)} pts ({snapshot?.vwap ? ((vwapDiff / snapshot.vwap) * 100).toFixed(2) : 0}%)
          </span>
        </div>

        {/* Technical Consensus */}
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '12px',
            padding: '16px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}
        >
          <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-dim)', fontWeight: 600 }}>
            Consensus Market Bias
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
            <span
              style={{
                fontSize: '1rem',
                fontWeight: 800,
                padding: '4px 10px',
                borderRadius: '6px',
                background: consensus.bg || 'rgba(255, 255, 255, 0.05)',
                color: consensus.color,
                letterSpacing: '0.04em',
              }}
            >
              {consensus.label}
            </span>
          </div>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '4px' }}>
            Derived from RSI, MACD, Supertrend & EMAs
          </span>
        </div>

        {/* Window Candles */}
        <div
          style={{
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '12px',
            padding: '16px 20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}
        >
          <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-dim)', fontWeight: 600 }}>
            Window Sampling
          </span>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: "'Outfit', sans-serif" }}>
              {snapshot?.candle_count || 0}
            </span>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>candles ({timeframe})</span>
          </div>
          <span style={{ fontSize: '0.7rem', color: 'var(--accent-purple)', fontWeight: 600 }}>
            {conditions.length} Strategy Conditions Bound
          </span>
        </div>
      </div>

      {/* Grid of 12 Technical Indicators */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)' }}>
              Real-Time Technical Indicators
            </h3>
            <p style={{ margin: '2px 0 0', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Self-contained calculations computed on live Dhan tick & candle closes
            </p>
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            Showing {snapshot?.indicators?.length || 0} active indicators
          </span>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
            gap: '16px',
          }}
        >
          {snapshot?.indicators && snapshot.indicators.length > 0 ? (
            snapshot.indicators.map((ind) => (
              <IndicatorCard key={ind.name} indicator={ind} ltp={snapshot.ltp} />
            ))
          ) : (
            <div
              style={{
                gridColumn: '1 / -1',
                padding: '48px',
                textAlign: 'center',
                color: 'var(--text-muted)',
                background: 'var(--bg-surface)',
                borderRadius: '12px',
                border: '1px solid var(--border-subtle)',
              }}
            >
              <Activity size={32} style={{ opacity: 0.4, marginBottom: '12px' }} />
              <div>Calculating live indicators for {symbolToUse}...</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '6px' }}>
                Fetching historical OHLCV data from Dhan and yfinance
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Split Section: Strategy Conditions + Live Signal Stream */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
          gap: '20px',
        }}
      >
        <StrategyConditionPanel conditions={conditions} snapshot={snapshot} />
        <LiveSignalFeed signals={signals} />
      </div>
    </div>
  );
};
