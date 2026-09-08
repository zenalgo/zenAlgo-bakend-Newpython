import React from 'react';
import { Radio, Zap, ArrowUpRight, ArrowDownRight, Clock } from 'lucide-react';

export const LiveSignalFeed = ({ signals = [] }) => {
  return (
    <div
      style={{
        background: 'linear-gradient(135deg, rgba(20, 31, 54, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%)',
        backdropFilter: 'blur(12px)',
        border: '1px solid var(--border-subtle)',
        borderRadius: '14px',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: '340px',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Radio size={18} color="var(--accent-cyan)" />
            <span
              style={{
                position: 'absolute',
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: 'var(--accent-cyan)',
                animation: 'pulse 1.5s infinite',
              }}
            />
          </div>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>
            Live Signal Feed
          </h3>
        </div>

        <span
          style={{
            fontSize: '0.7rem',
            padding: '2px 8px',
            borderRadius: '999px',
            background: 'rgba(56, 189, 248, 0.1)',
            border: '1px solid rgba(56, 189, 248, 0.3)',
            color: 'var(--accent-cyan)',
            fontWeight: 600,
          }}
        >
          {signals.length} Signals Fired
        </span>
      </div>

      {/* Signals List */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          overflowY: 'auto',
          maxHeight: '400px',
          paddingRight: '4px',
        }}
      >
        {signals.length === 0 ? (
          <div
            style={{
              padding: '36px 16px',
              textAlign: 'center',
              color: 'var(--text-dim)',
              fontSize: '0.85rem',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <Zap size={24} style={{ opacity: 0.3 }} />
            <span>Listening for real-time strategy condition matches...</span>
            <span style={{ fontSize: '0.75rem' }}>Signals will appear immediately when conditions trigger</span>
          </div>
        ) : (
          signals.map((sig, idx) => {
            const isEntry = sig.signal === 'ENTRY' || sig.signal === 'BUY';
            const timeStr = sig.timestamp
              ? new Date(sig.timestamp).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
              : '--:--:--';

            return (
              <div
                key={sig.event_id || idx}
                style={{
                  padding: '12px 14px',
                  borderRadius: '10px',
                  background: isEntry ? 'rgba(16, 185, 129, 0.08)' : 'rgba(244, 63, 94, 0.08)',
                  border: `1px solid ${isEntry ? 'rgba(16, 185, 129, 0.25)' : 'rgba(244, 63, 94, 0.25)'}`,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  transition: 'transform 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {/* Signal Pill */}
                    <span
                      style={{
                        fontSize: '0.7rem',
                        fontWeight: 800,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background: isEntry ? 'rgba(16, 185, 129, 0.2)' : 'rgba(244, 63, 94, 0.2)',
                        color: isEntry ? 'var(--accent-emerald)' : 'var(--accent-rose)',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '2px',
                      }}
                    >
                      {isEntry ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                      {sig.signal}
                    </span>

                    <span style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--text-main)' }}>
                      {sig.symbol}
                    </span>

                    <span
                      style={{
                        fontSize: '0.65rem',
                        padding: '1px 6px',
                        borderRadius: '4px',
                        background: 'rgba(255, 255, 255, 0.06)',
                        color: 'var(--text-dim)',
                      }}
                    >
                      {sig.trigger_type || 'TICK'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-dim)', fontSize: '0.7rem' }}>
                    <Clock size={11} />
                    <span>{timeStr}</span>
                  </div>
                </div>

                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>{sig.condition_text}</span>
                  {sig.indicator_value !== undefined && (
                    <span style={{ marginLeft: '6px', color: 'var(--accent-cyan)' }}>
                      (Value: {sig.indicator_value})
                    </span>
                  )}
                </div>

                {sig.strategy_name && (
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '2px' }}>
                    Strategy: <span style={{ color: 'var(--accent-purple)', fontWeight: 600 }}>{sig.strategy_name}</span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
