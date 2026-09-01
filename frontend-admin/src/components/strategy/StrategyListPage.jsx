import React, { useState, useEffect } from 'react';
import { StatusBadge } from '../common/StatusBadge';
import { Play, Square, Activity, RefreshCw, Plus, Layers, ArrowUpRight, CheckCircle2, Clock, AlertTriangle, Zap, Eye } from 'lucide-react';
import { strategyApi } from '../../api/strategyApi';
import { executionApi } from '../../api/executionApi';
import { useToast } from '../../context/ToastContext';

export const StrategyListPage = ({ onNavigateToBuilder, onNavigateToOrders, onNavigateToBatches }) => {
  const { addToast } = useToast();
  const [strategies, setStrategies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);

  const loadStrategies = async () => {
    setLoading(true);
    try {
      const res = await strategyApi.getStrategies();
      setStrategies(res.data || []);
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to fetch strategies', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStrategies();
  }, []);

  const handleDeploy = async (id, mode = 'PAPER') => {
    setActionLoading(id);
    try {
      if (mode === 'PAPER') {
        await strategyApi.activatePaper(id);
        addToast(`Strategy #${id} deployed in PAPER trading mode!`, 'success');
      } else {
        await strategyApi.activateLive(id);
        addToast(`Strategy #${id} deployed to LIVE BROKER!`, 'warning');
      }
      loadStrategies();
    } catch (err) {
      addToast(err.message || 'Deployment failed', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleSimulateTrade = async (id) => {
    setActionLoading(id);
    try {
      const res = await executionApi.simulateExecution(id);
      addToast(`Simulated 5m paper order placed for Strategy #${id}! (Execution #${res.data?.executionId})`, 'success');
      loadStrategies();
    } catch (err) {
      addToast(err.message || 'Simulation failed', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleSquareOff = async (id) => {
    if (!window.confirm(`Are you sure you want to force square-off all positions for Strategy #${id}?`)) return;
    setActionLoading(id);
    try {
      await strategyApi.squareOff(id);
      addToast(`Strategy #${id} squared off successfully!`, 'success');
      loadStrategies();
    } catch (err) {
      addToast(err.message || 'Square off failed', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Strategy Fleet & Execution Hub</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Monitor active algorithmic strategies, state machine lifecycles, and copy-trading execution fleets.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={loadStrategies} disabled={loading} className="btn btn-secondary">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            <span>Refresh Fleet</span>
          </button>
          <button onClick={onNavigateToBuilder} className="btn btn-primary">
            <Plus size={16} />
            <span>+ Build New Strategy</span>
          </button>
        </div>
      </div>

      {/* Visual State Machine Lifecycle Guide Card */}
      <div className="glass-panel" style={{ padding: '20px', border: '1px solid var(--border-highlight)' }}>
        <h4 style={{ fontSize: '0.9rem', color: 'var(--accent-cyan)', textTransform: 'uppercase', fontWeight: 700, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Activity size={16} />
          <span>Institutional State Machine Lifecycle</span>
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '12px', borderRadius: '6px', borderLeft: '3px solid #94a3b8' }}>
            <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.85rem' }}>1. WAITING</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>Scheduled for market opening time (09:15 AM).</div>
          </div>
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '12px', borderRadius: '6px', borderLeft: '3px solid var(--accent-cyan)' }}>
            <div style={{ fontWeight: 700, color: 'var(--accent-cyan)', fontSize: '0.85rem' }}>2. MONITORING_ENTRY</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>Scanning 5m live candles for technical rule triggers.</div>
          </div>
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '12px', borderRadius: '6px', borderLeft: '3px solid var(--accent-emerald)' }}>
            <div style={{ fontWeight: 700, color: 'var(--accent-emerald)', fontSize: '0.85rem' }}>3. POSITION_OPEN</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>Multi-leg orders filled. Trailing stop & targets active.</div>
          </div>
          <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '12px', borderRadius: '6px', borderLeft: '3px solid var(--accent-purple)' }}>
            <div style={{ fontWeight: 700, color: 'var(--accent-purple)', fontSize: '0.85rem' }}>4. SQUARED_OFF</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>Target/Stop reached or forced exit at 15:15 PM.</div>
          </div>
        </div>
      </div>

      {/* Strategies Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '20px' }}>
        {loading ? (
          <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', gridColumn: '1 / -1', color: 'var(--text-muted)' }}>
            Loading active strategy fleet...
          </div>
        ) : strategies.length === 0 ? (
          <div className="glass-panel" style={{ padding: '40px', textAlign: 'center', gridColumn: '1 / -1', color: 'var(--text-muted)' }}>
            No strategies configured yet. Click <strong>"+ Build New Strategy"</strong> to generate one.
          </div>
        ) : (
          strategies.map((s) => (
            <div
              key={s.id}
              className="glass-panel"
              style={{
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '16px',
                position: 'relative',
                border: '1px solid var(--border-highlight)',
              }}
            >
              {/* Card Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', fontWeight: 700 }}>
                    STRATEGY #{s.id}
                  </div>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff', marginTop: '2px' }}>
                    {s.name}
                  </h3>
                </div>
                <StatusBadge status={s.status || 'MONITORING_ENTRY'} />
              </div>

              {/* Badges Bar */}
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', fontSize: '0.75rem' }}>
                <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)' }}>
                  {s.underlying || 'NIFTY 50'}
                </span>
                <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-emerald)' }}>
                  MODE: {s.mode || 'PAPER'}
                </span>
                <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.15)', color: 'var(--accent-purple)' }}>
                  {s.timeframe || '5m Candle'}
                </span>
              </div>

              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', minHeight: '36px' }}>
                {s.description || 'Institutional algorithmic trading strategy'}
              </div>

              {/* Fast Action Simulator & Links */}
              <div style={{
                borderTop: '1px solid var(--border-subtle)',
                paddingTop: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
              }}>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <button
                    onClick={() => handleSimulateTrade(s.id)}
                    disabled={actionLoading === s.id}
                    className="btn btn-emerald"
                    style={{ padding: '8px', fontSize: '0.8rem', justifyContent: 'center' }}
                  >
                    <Zap size={14} />
                    <span>⚡ 5m Paper Trade</span>
                  </button>
                  <button
                    onClick={() => handleDeploy(s.id, 'PAPER')}
                    disabled={actionLoading === s.id}
                    className="btn btn-primary"
                    style={{ padding: '8px', fontSize: '0.8rem', justifyContent: 'center' }}
                  >
                    <Play size={14} />
                    <span>Deploy Paper</span>
                  </button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  <button
                    onClick={() => onNavigateToOrders && onNavigateToOrders(s.id)}
                    className="btn btn-secondary"
                    style={{ padding: '6px', fontSize: '0.75rem', justifyContent: 'center' }}
                  >
                    <Eye size={12} />
                    <span>View Orders</span>
                  </button>
                  <button
                    onClick={() => onNavigateToBatches && onNavigateToBatches(s.id)}
                    className="btn btn-secondary"
                    style={{ padding: '6px', fontSize: '0.75rem', justifyContent: 'center' }}
                  >
                    <Layers size={12} />
                    <span>Audit Batches</span>
                  </button>
                </div>

                <button
                  onClick={() => handleSquareOff(s.id)}
                  disabled={actionLoading === s.id}
                  className="btn btn-danger"
                  style={{ padding: '6px', fontSize: '0.75rem', width: '100%', justifyContent: 'center', marginTop: '2px' }}
                >
                  <Square size={12} />
                  <span>Square Off Strategy</span>
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default StrategyListPage;
