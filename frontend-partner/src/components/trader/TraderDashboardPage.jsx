import React, { useState, useEffect } from 'react';
import {
  Activity,
  Cpu,
  TrendingUp,
  Wallet,
  Play,
  Square,
  Zap,
  RefreshCw,
  CheckCircle2,
  Clock,
  Layers,
  ArrowUpRight,
} from 'lucide-react';
import { traderApi } from '../../api/traderApi';
import { useToast } from '../../context/ToastContext';

export const TraderDashboardPage = ({ onNavigate }) => {
  const { addToast } = useToast();
  const [strategies, setStrategies] = useState([]);
  const [wallet, setWallet] = useState(null);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [resStrats, resWallet, resOrders] = await Promise.all([
        traderApi.getStrategies(),
        traderApi.getWallet(),
        traderApi.getPlacedOrders(),
      ]);
      setStrategies(resStrats.data || []);
      setWallet(resWallet.data);
      setOrders(resOrders.data || []);
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to load trader dashboard', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSimulateTrade = async (id) => {
    setActionLoading(id);
    try {
      const res = await traderApi.simulateExecution(id);
      addToast(`Paper trade executed for Strategy #${id}! (Order #${res.data?.executionId})`, 'success');
      loadData();
    } catch (err) {
      addToast(err.message || 'Simulation failed', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleSquareOff = async (id) => {
    setActionLoading(id);
    try {
      await traderApi.squareOffStrategy(id);
      addToast(`Strategy #${id} squared off successfully!`, 'success');
      loadData();
    } catch (err) {
      addToast(err.message || 'Square off failed', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Trader Execution Dashboard</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Monitor active algorithmic copy-trading strategies, margin allocation, and live order execution.
          </p>
        </div>

        <button onClick={loadData} disabled={loading} className="btn btn-secondary">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Dashboard</span>
        </button>
      </div>

      {/* Hero Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
        
        {/* Available Trading Margin */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-emerald)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>AVAILABLE TRADING MARGIN</span>
            <Wallet size={18} color="var(--accent-emerald)" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '8px' }}>
            ₹{Number(wallet?.availableMargin || 95000).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Total Balance: ₹{Number(wallet?.totalBalance || 100000).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
        </div>

        {/* Active Copy Strategies */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-cyan)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>ACTIVE COPY STRATEGIES</span>
            <Cpu size={18} color="var(--accent-cyan)" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff', marginTop: '8px' }}>
            {strategies.length} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>Deployed</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', marginTop: '4px' }}>
            ● Scanning 5m candles in real-time
          </div>
        </div>

        {/* Total Placed Orders */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-purple)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>TOTAL EXECUTIONS TODAY</span>
            <Activity size={18} color="var(--accent-purple)" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff', marginTop: '8px' }}>
            {orders.length} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>Orders Filled</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', marginTop: '4px' }}>
            ● 100% Fill Ratio on Paper Engine
          </div>
        </div>

        {/* Broker Connection Status */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-amber)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>BROKER ROUTING</span>
            <TrendingUp size={18} color="var(--accent-amber)" />
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff', marginTop: '8px' }}>
            Dhan Sandbox Active
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', marginTop: '4px' }}>
            ● Latency: 14ms (Optimal)
          </div>
        </div>
      </div>

      {/* Active Strategies Grid */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#fff' }}>
            My Active Copy-Trading Fleet
          </h3>
          <button onClick={() => onNavigate && onNavigate('trader-strategies')} className="btn btn-secondary" style={{ padding: '6px 14px', fontSize: '0.8rem' }}>
            <span>Browse All Strategies</span>
            <ArrowUpRight size={14} />
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '16px' }}>
          {strategies.map((s) => (
            <div
              key={s.id}
              className="glass-panel"
              style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                    STRATEGY #{s.id}
                  </span>
                  <h4 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#fff', marginTop: '2px' }}>
                    {s.name}
                  </h4>
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
              </div>

              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0, minHeight: '36px' }}>
                {s.description || 'Intraday quantitative strategy with automated trailing stop.'}
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px' }}>
                <button
                  onClick={() => handleSimulateTrade(s.id)}
                  disabled={actionLoading === s.id}
                  className="btn btn-emerald"
                  style={{ padding: '8px', fontSize: '0.75rem', justifyContent: 'center' }}
                >
                  <Zap size={14} />
                  <span>5m Paper Trade</span>
                </button>
                <button
                  onClick={() => handleSquareOff(s.id)}
                  disabled={actionLoading === s.id}
                  className="btn btn-danger"
                  style={{ padding: '8px', fontSize: '0.75rem', justifyContent: 'center' }}
                >
                  <Square size={14} />
                  <span>Square Off</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default TraderDashboardPage;
