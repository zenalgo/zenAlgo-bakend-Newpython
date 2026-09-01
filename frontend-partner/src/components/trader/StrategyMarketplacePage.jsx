import React, { useState, useEffect } from 'react';
import { Cpu, Search, RefreshCw, Zap, Play, Square, Filter, Star } from 'lucide-react';
import { traderApi } from '../../api/traderApi';
import { useToast } from '../../context/ToastContext';

export const StrategyMarketplacePage = () => {
  const { addToast } = useToast();
  const [strategies, setStrategies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [actionLoading, setActionLoading] = useState(null);

  const loadStrategies = async () => {
    setLoading(true);
    try {
      const res = await traderApi.getStrategies({ search: search || undefined });
      setStrategies(res.data || []);
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to load strategy marketplace', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStrategies();
  }, [search]);

  const handleSimulate = async (id) => {
    setActionLoading(id);
    try {
      const res = await traderApi.simulateExecution(id);
      addToast(`Simulated 5m paper order placed for Strategy #${id}! (Execution #${res.data?.executionId})`, 'success');
    } catch (err) {
      addToast(err.message || 'Trade simulation failed', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Copy-Trading Fleet & Marketplace</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Subscribe and copy verified institutional algorithmic strategies directly into your broker account.
          </p>
        </div>

        <button onClick={loadStrategies} disabled={loading} className="btn btn-secondary">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Fleet</span>
        </button>
      </div>

      {/* Search Toolbar */}
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, maxWidth: '400px' }}>
          <Search size={18} color="var(--text-dim)" />
          <input
            type="text"
            placeholder="Search strategy by name or underlying..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-field"
          />
        </div>

        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          Available Strategies: <strong style={{ color: 'var(--accent-cyan)' }}>{strategies.length}</strong>
        </span>
      </div>

      {/* Strategies Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '20px' }}>
        {strategies.map((s) => (
          <div
            key={s.id}
            className="glass-panel"
            style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', fontWeight: 700 }}>
                  STRATEGY #{s.id}
                </span>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff', marginTop: '2px' }}>
                  {s.name}
                </h3>
              </div>
              <span className="badge badge-active">{s.mode || 'PAPER'}</span>
            </div>

            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', fontSize: '0.75rem' }}>
              <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)' }}>
                {s.underlying}
              </span>
              <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.15)', color: 'var(--accent-purple)' }}>
                {s.timeframe || '5m'}
              </span>
              <span className="badge" style={{ background: 'rgba(16, 185, 129, 0.15)', color: 'var(--accent-emerald)' }}>
                Auto-Hedged
              </span>
            </div>

            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', minHeight: '40px', lineHeight: '1.4' }}>
              {s.description || 'Institutional quantitative trend strategy with rule-based stop loss and multi-leg risk controls.'}
            </p>

            <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <button
                onClick={() => handleSimulate(s.id)}
                disabled={actionLoading === s.id}
                className="btn btn-emerald"
                style={{ justifyContent: 'center', padding: '10px' }}
              >
                <Zap size={16} />
                <span>⚡ 5m Paper Trade</span>
              </button>

              <button
                onClick={() => addToast(`Copying Strategy #${s.id} active! Orders will replicate automatically.`, 'success')}
                className="btn btn-primary"
                style={{ justifyContent: 'center', padding: '10px' }}
              >
                <Play size={16} />
                <span>Copy Strategy</span>
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default StrategyMarketplacePage;
