import React from 'react';
import { Target, CheckCircle2, Clock, AlertCircle } from 'lucide-react';

export const StrategyConditionPanel = ({ conditions = [], snapshot }) => {
  // Helper to test if a condition is currently met
  const checkConditionStatus = (cond) => {
    if (!snapshot) return { isMet: false, currVal: null };

    const ruleJson = cond.rule_json || {};
    let indName = ruleJson.indicator;
    let op = ruleJson.operator || '>=';
    let targetVal = ruleJson.value;

    if (!indName && cond.raw_text) {
      const raw = cond.raw_text.toUpperCase();
      for (const cand of ['VWAP', 'RSI', 'MACD', 'SUPERTREND', 'STOCHASTIC', 'ADX', 'CCI', 'MFI', 'EMA', 'BB']) {
        if (raw.includes(cand)) {
          indName = cand;
          break;
        }
      }
    }

    if (!indName) return { isMet: false, currVal: null };

    // Extract current value from snapshot
    let currVal = null;
    if (['LTP', 'PRICE'].includes(indName.toUpperCase())) {
      currVal = snapshot.ltp;
    } else if (indName.toUpperCase() === 'VWAP') {
      currVal = snapshot.vwap;
    } else if (snapshot.indicators) {
      const found = snapshot.indicators.find(
        (i) => i.name.toUpperCase() === indName.toUpperCase()
      );
      if (found) currVal = found.value;
    }

    if (currVal === null || currVal === undefined || targetVal === null || targetVal === undefined) {
      return { isMet: false, currVal };
    }

    const numTarget = parseFloat(targetVal);
    let isMet = false;
    if (['>', 'GREATER_THAN', 'PRICE_ABOVE', 'ABOVE'].includes(op)) isMet = currVal > numTarget;
    else if (['<', 'LESS_THAN', 'PRICE_BELOW', 'BELOW'].includes(op)) isMet = currVal < numTarget;
    else if (['>=', 'GREATER_THAN_EQUAL', 'AT_LEAST'].includes(op)) isMet = currVal >= numTarget;
    else if (['<=', 'LESS_THAN_EQUAL', 'AT_MOST'].includes(op)) isMet = currVal <= numTarget;
    else if (['==', '=', 'EQUALS'].includes(op)) isMet = Math.abs(currVal - numTarget) < 0.01;

    return { isMet, currVal, indName, op, targetVal };
  };

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
          <Target size={18} color="var(--accent-purple)" />
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)' }}>
            Strategy Entry/Exit Rules
          </h3>
        </div>

        <span
          style={{
            fontSize: '0.7rem',
            padding: '2px 8px',
            borderRadius: '999px',
            background: 'rgba(168, 85, 247, 0.15)',
            border: '1px solid rgba(168, 85, 247, 0.3)',
            color: 'var(--accent-purple)',
            fontWeight: 600,
          }}
        >
          {conditions.length} Monitored
        </span>
      </div>

      {/* Conditions List */}
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
        {conditions.length === 0 ? (
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
            <AlertCircle size={24} style={{ opacity: 0.3 }} />
            <span>No active strategy conditions tied to this symbol</span>
            <span style={{ fontSize: '0.75rem' }}>Create rules in Strategy Builder with indicators like VWAP or RSI</span>
          </div>
        ) : (
          conditions.map((cond, idx) => {
            const { isMet, currVal } = checkConditionStatus(cond);
            const isEntry = cond.rule_type === 'ENTRY';

            return (
              <div
                key={cond.condition_id || idx}
                style={{
                  padding: '12px 14px',
                  borderRadius: '10px',
                  background: isMet ? 'rgba(16, 185, 129, 0.1)' : 'rgba(15, 23, 42, 0.6)',
                  border: `1px solid ${isMet ? 'rgba(16, 185, 129, 0.4)' : 'var(--border-subtle)'}`,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  transition: 'all 0.2s ease',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span
                      style={{
                        fontSize: '0.65rem',
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: '4px',
                        background: isEntry ? 'rgba(56, 189, 248, 0.15)' : 'rgba(244, 63, 94, 0.15)',
                        color: isEntry ? 'var(--accent-cyan)' : 'var(--accent-rose)',
                      }}
                    >
                      {cond.rule_type || 'RULE'}
                    </span>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-main)' }}>
                      {cond.strategy_name}
                    </span>
                  </div>

                  {/* Status Badge */}
                  <div
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '0.7rem',
                      fontWeight: 700,
                      color: isMet ? 'var(--accent-emerald)' : 'var(--text-dim)',
                    }}
                  >
                    {isMet ? <CheckCircle2 size={13} color="var(--accent-emerald)" /> : <Clock size={13} />}
                    <span>{isMet ? 'CONDITION MET' : 'MONITORING'}</span>
                  </div>
                </div>

                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  Rule: <span style={{ color: 'var(--text-main)', fontWeight: 500 }}>{cond.raw_text || JSON.stringify(cond.rule_json)}</span>
                </div>

                {currVal !== null && (
                  <div style={{ fontSize: '0.75rem', color: isMet ? 'var(--accent-emerald)' : 'var(--text-dim)', display: 'flex', justifyContent: 'space-between', marginTop: '2px' }}>
                    <span>Current Value: <strong style={{ color: 'var(--text-main)' }}>{currVal}</strong></span>
                    {isMet && <span style={{ fontWeight: 700 }}>⚡ Triggers Strategy Execution</span>}
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
