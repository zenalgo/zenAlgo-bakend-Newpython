import React, { useState, useEffect } from 'react';
import { StatusBadge } from '../common/StatusBadge';
import { Zap, Play, Square, Layers, Trash2, Eye, Plus, Cpu } from 'lucide-react';
import { strategyApi } from '../../api/strategyApi';
import { useToast } from '../../context/ToastContext';

export const StrategyListPage = ({ onNavigate, onSelectStrategy }) => {
  const { addToast } = useToast();
  const [strategies, setStrategies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const loadStrategies = async () => {
    try {
      const res = await strategyApi.getStrategies();
      setStrategies(res.data || []);
    } catch (err) {
      addToast(err.message || 'Failed to fetch strategies', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStrategies();
  }, []);

  const handleActivatePaper = async (id) => {
    try {
      await strategyApi.activatePaper(id);
      addToast(`Strategy #${id} deployed into PAPER trading!`, 'success');
      loadStrategies();
    } catch (err) {
      addToast(err.message || 'Activation failed', 'error');
    }
  };

  const handleSquareOff = async (id) => {
    if (!window.confirm(`Are you sure you want to square off all positions for Strategy #${id}?`)) return;
    try {
      await strategyApi.squareOff(id);
      addToast(`Square-off executed for Strategy #${id}!`, 'success');
      loadStrategies();
    } catch (err) {
      addToast(err.message || 'Square-off failed', 'error');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm(`Are you sure you want to delete Strategy #${id}?`)) return;
    try {
      await strategyApi.deleteStrategy(id);
      addToast(`Strategy #${id} deleted`, 'info');
      loadStrategies();
    } catch (err) {
      addToast(err.message || 'Delete failed', 'error');
    }
  };

  const filtered = strategies.filter((s) =>
    (s.name || '').toLowerCase().includes(search.toLowerCase()) ||
    (s.underlying || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Strategy Fleet & Lifecycle</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Deploy, monitor state transitions, and audit multi-leg algorithmic strategies.</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={() => onNavigate('builder')} className="btn btn-primary">
            <Plus size={16} />
            <span>Visual Multi-Leg Builder</span>
          </button>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: '20px' }}>
        <input
          type="text"
          placeholder="Search by strategy name, underlying asset..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input-field"
          style={{ maxWidth: '400px', marginBottom: '16px' }}
        />

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Strategy Name</th>
                <th>Underlying</th>
                <th>Timeframe</th>
                <th>Mode</th>
                <th>State Machine</th>
                <th>Target / SL</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    No strategies matching your search.
                  </td>
                </tr>
              ) : (
                filtered.map((s) => (
                  <tr key={s.id}>
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>#{s.id}</td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{s.name}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Version #{s.currentVersionId || 1}</div>
                    </td>
                    <td><span style={{ fontWeight: 600 }}>{s.underlying || 'NIFTY'}</span></td>
                    <td className="font-mono">{s.timeframe || '5m'}</td>
                    <td><StatusBadge status={s.mode || 'PAPER'} /></td>
                    <td><StatusBadge status={s.status || 'WAITING'} /></td>
                    <td>
                      <div style={{ fontSize: '0.8rem' }}>
                        <span style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>Target: {typeof s.target === 'object' ? s.target?.value || '2R' : s.target || '2R'}</span>
                        <div style={{ color: 'var(--accent-rose)', fontSize: '0.75rem' }}>Forced Exit: 15:15</div>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button
                          onClick={() => handleActivatePaper(s.id)}
                          title="Deploy Paper Trading"
                          className="btn btn-emerald"
                          style={{ padding: '6px 10px', fontSize: '0.75rem' }}
                        >
                          <Play size={14} />
                          <span>Paper Deploy</span>
                        </button>
                        <button
                          onClick={() => {
                            if (onSelectStrategy) onSelectStrategy(s.id);
                            onNavigate('placed-orders');
                          }}
                          title="View Placed Orders"
                          className="btn btn-secondary"
                          style={{ padding: '6px 10px', fontSize: '0.75rem' }}
                        >
                          Orders
                        </button>
                        <button
                          onClick={() => {
                            if (onSelectStrategy) onSelectStrategy(s.id);
                            onNavigate('batches');
                          }}
                          title="Copy-Trading Batches"
                          className="btn btn-secondary"
                          style={{ padding: '6px 10px', fontSize: '0.75rem' }}
                        >
                          <Layers size={14} />
                        </button>
                        <button
                          onClick={() => handleSquareOff(s.id)}
                          title="Square Off All"
                          className="btn btn-danger"
                          style={{ padding: '6px 10px', fontSize: '0.75rem' }}
                        >
                          <Square size={14} />
                        </button>
                        <button
                          onClick={() => handleDelete(s.id)}
                          title="Delete Strategy"
                          style={{
                            background: 'transparent',
                            border: '1px solid var(--border-subtle)',
                            color: 'var(--text-muted)',
                            borderRadius: '6px',
                            padding: '6px 8px',
                            cursor: 'pointer',
                          }}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default StrategyListPage;
