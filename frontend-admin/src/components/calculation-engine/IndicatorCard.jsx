import React from 'react';
import { TrendingUp, TrendingDown, Minus, Activity, ArrowUpRight, ArrowDownRight } from 'lucide-react';

export const IndicatorCard = ({ indicator, ltp }) => {
  if (!indicator) return null;

  const {
    name,
    display_name,
    value,
    secondary = {},
    signal = 'NEUTRAL',
    signal_color = 'amber',
    description = '',
    history = [],
  } = indicator;

  // Signal formatting
  const isBuy = signal === 'BUY' || signal_color === 'green';
  const isSell = signal === 'SELL' || signal_color === 'red';
  const isNeutral = !isBuy && !isSell;

  const badgeBg = isBuy
    ? 'rgba(16, 185, 129, 0.15)'
    : isSell
    ? 'rgba(244, 63, 94, 0.15)'
    : 'rgba(245, 158, 11, 0.15)';

  const badgeBorder = isBuy
    ? 'rgba(16, 185, 129, 0.4)'
    : isSell
    ? 'rgba(244, 63, 94, 0.4)'
    : 'rgba(245, 158, 11, 0.4)';

  const badgeColor = isBuy
    ? 'var(--accent-emerald)'
    : isSell
    ? 'var(--accent-rose)'
    : 'var(--accent-amber)';

  const SignalIcon = isBuy ? ArrowUpRight : isSell ? ArrowDownRight : Minus;

  // Sparkline path generator
  const renderSparkline = () => {
    if (!history || history.length < 2) return null;
    const min = Math.min(...history);
    const max = Math.max(...history);
    const range = max - min || 1;
    const w = 120;
    const h = 28;

    const points = history.map((val, idx) => {
      const x = (idx / (history.length - 1)) * w;
      const y = h - ((val - min) / range) * (h - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    const strokeColor = isBuy ? '#10b981' : isSell ? '#f43f5e' : '#38bdf8';

    return (
      <svg width={w} height={h} style={{ overflow: 'visible' }}>
        <polyline
          fill="none"
          stroke={strokeColor}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
      </svg>
    );
  };

  // Check if indicator is percentage bounded (0 - 100)
  const isBounded = ['RSI', 'STOCHASTIC', 'MFI', 'CCI'].includes(name?.toUpperCase());
  const percentVal = isBounded && typeof value === 'number' ? Math.max(0, Math.min(100, value)) : null;

  return (
    <div
      style={{
        background: 'linear-gradient(135deg, rgba(20, 31, 54, 0.75) 0%, rgba(15, 23, 42, 0.85) 100%)',
        backdropFilter: 'blur(12px)',
        border: `1px solid ${isBuy ? 'rgba(16, 185, 129, 0.3)' : isSell ? 'rgba(244, 63, 94, 0.3)' : 'var(--border-subtle)'}`,
        borderRadius: '14px',
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        boxShadow: isBuy
          ? '0 4px 20px rgba(16, 185, 129, 0.08)'
          : isSell
          ? '0 4px 20px rgba(244, 63, 94, 0.08)'
          : '0 4px 16px rgba(0, 0, 0, 0.2)',
        transition: 'all 0.2s ease-in-out',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Top accent glow line */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '2px',
          background: isBuy
            ? 'linear-gradient(90deg, transparent, #10b981, transparent)'
            : isSell
            ? 'linear-gradient(90deg, transparent, #f43f5e, transparent)'
            : 'linear-gradient(90deg, transparent, #38bdf8, transparent)',
        }}
      />

      {/* Header: Name + Signal Badge */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-dim)', fontWeight: 600 }}>
            INDICATOR
          </span>
          <h4 style={{ margin: '2px 0 0', fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.01em' }}>
            {display_name || name}
          </h4>
        </div>

        {/* Signal Badge */}
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            padding: '4px 10px',
            borderRadius: '999px',
            background: badgeBg,
            border: `1px solid ${badgeBorder}`,
            color: badgeColor,
            fontSize: '0.75rem',
            fontWeight: 700,
            letterSpacing: '0.04em',
          }}
        >
          <SignalIcon size={13} />
          <span>{signal}</span>
        </div>
      </div>

      {/* Main Metric Value & Sparkline */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: '2px' }}>
        <div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)', fontFamily: "'Outfit', 'Inter', sans-serif" }}>
            {value !== null && value !== undefined ? (typeof value === 'number' ? value.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : value) : '--'}
          </div>
          {name === 'VWAP' && ltp && value && (
            <div style={{ fontSize: '0.75rem', color: ltp >= value ? 'var(--accent-emerald)' : 'var(--accent-rose)', fontWeight: 600, marginTop: '2px' }}>
              LTP vs VWAP: {ltp >= value ? '+' : ''}{(ltp - value).toFixed(2)} ({(((ltp - value) / value) * 100).toFixed(2)}%)
            </div>
          )}
        </div>

        {/* Mini Sparkline */}
        {renderSparkline()}
      </div>

      {/* Progress Bar for Bounded Indicators */}
      {percentVal !== null && (
        <div style={{ marginTop: '2px' }}>
          <div style={{ height: '5px', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '3px', overflow: 'hidden' }}>
            <div
              style={{
                width: `${percentVal}%`,
                height: '100%',
                background: isBuy ? 'var(--accent-emerald)' : isSell ? 'var(--accent-rose)' : 'var(--accent-cyan)',
                borderRadius: '3px',
                transition: 'width 0.4s ease',
              }}
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--text-dim)', marginTop: '4px' }}>
            <span>0</span>
            <span>50</span>
            <span>100</span>
          </div>
        </div>
      )}

      {/* Secondary Values Grid (MACD, Supertrend, Bollinger, etc.) */}
      {secondary && Object.keys(secondary).length > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `repeat(${Math.min(Object.keys(secondary).length, 3)}, 1fr)`,
            gap: '8px',
            padding: '8px 10px',
            background: 'rgba(11, 19, 37, 0.6)',
            borderRadius: '8px',
            border: '1px solid rgba(255, 255, 255, 0.04)',
            fontSize: '0.75rem',
          }}
        >
          {Object.entries(secondary).map(([key, val]) => (
            <div key={key} style={{ display: 'flex', flexDirection: 'column' }}>
              <span style={{ color: 'var(--text-dim)', fontSize: '0.65rem', textTransform: 'uppercase' }}>
                {key.replace('_', ' ')}
              </span>
              <span style={{ color: 'var(--text-main)', fontWeight: 600, marginTop: '1px' }}>
                {typeof val === 'number' ? val.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : String(val)}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Description / Interpretation */}
      {description && (
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.4, borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: '8px' }}>
          {description}
        </div>
      )}
    </div>
  );
};
