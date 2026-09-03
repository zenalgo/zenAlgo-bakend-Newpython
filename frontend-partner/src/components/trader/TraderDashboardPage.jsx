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
import { brokerApi } from '../../api/brokerApi';
import { useToast } from '../../context/ToastContext';

export const TraderDashboardPage = ({ onNavigate }) => {
  const { addToast } = useToast();
  const [strategies, setStrategies] = useState([]);
  const [wallet, setWallet] = useState(null);
  const [orders, setOrders] = useState([]);
  const [dhanFunds, setDhanFunds] = useState(null);
  const [dhanOrders, setDhanOrders] = useState([]);
  const [brokerSession, setBrokerSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);

  const loadData = async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    try {
      const [resStrats, resWallet, resOrders, resBroker] = await Promise.all([
        traderApi.getStrategies().catch(() => ({ data: [] })),
        traderApi.getWallet().catch(() => ({ data: null })),
        traderApi.getPlacedOrders().catch(() => ({ data: [] })),
        brokerApi.getActiveSession().catch(() => ({ data: { connected: false } })),
      ]);

      setStrategies(resStrats.data || []);
      setWallet(resWallet.data || null);
      setOrders(resOrders.data || []);
      const activeBroker = resBroker?.data || null;
      setBrokerSession(activeBroker);

      // If connected to Dhan, fetch live Dhan funds & orders
      if (activeBroker?.connected) {
        try {
          const [fundsRes, ordersRes] = await Promise.allSettled([
            brokerApi.getDhanFunds(),
            brokerApi.getDhanOrders(),
          ]);
          if (fundsRes.status === 'fulfilled' && fundsRes.value?.data) {
            setDhanFunds(fundsRes.value.data);
          }
          if (ordersRes.status === 'fulfilled' && Array.isArray(ordersRes.value?.data)) {
            setDhanOrders(ordersRes.value.data);
          }
        } catch (brokerErr) {
          console.warn('Could not load live Dhan data on dashboard', brokerErr);
        }
      } else {
        setDhanFunds(null);
        setDhanOrders([]);
      }
    } catch (err) {
      if (!isSilent) {
        console.error(err);
        addToast(err.message || 'Failed to load trader dashboard', 'error');
      }
    } finally {
      if (!isSilent) setLoading(false);
    }
  };

  useEffect(() => {
    loadData(false);
    const interval = setInterval(() => {
      loadData(true);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleSimulateTrade = async (id) => {
    setActionLoading(id);
    try {
      const res = await traderApi.simulateExecution(id);
      addToast(`Paper trade executed for Strategy #${id}! Realized PnL: ₹${res.data?.realizedPnl ?? 0}`, 'success');
      loadData();
    } catch (err) {
      const msg = err.response?.data?.message || err.message || 'Simulation failed';
      if (msg.includes('subscription') || msg.includes('SUBSCRIPTION_REQUIRED') || err.response?.status === 403) {
        addToast('Active subscription plan required to execute trades. Please submit payment UTR.', 'warning');
        if (onNavigate) {
          setTimeout(() => onNavigate('trader-subscription'), 1200);
        }
      } else {
        addToast(msg, 'error');
      }
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
            Monitor algorithmic copy-trading strategies, real margin allocation, and live order execution.
          </p>
        </div>

        <button onClick={() => loadData(false)} disabled={loading} className="btn btn-secondary">
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

          {dhanFunds ? (
            <>
              <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '8px' }}>
                ₹{Number(dhanFunds.availableBalance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', marginTop: '4px' }}>
                ● Live Dhan Margin (SOD: ₹{Number(dhanFunds.sodLimit || dhanFunds.availableBalance).toLocaleString('en-IN', { minimumFractionDigits: 2 })})
              </div>
            </>
          ) : wallet && wallet.availableMargin != null ? (
            <>
              <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '8px' }}>
                ₹{Number(wallet.availableMargin).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                Wallet Balance: ₹{Number(wallet.totalBalance || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-dim)', marginTop: '8px' }}>
                N/A
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px' }}>
                No active margin data
              </div>
            </>
          )}
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
          <div style={{ fontSize: '0.75rem', color: strategies.length > 0 ? 'var(--accent-cyan)' : 'var(--text-dim)', marginTop: '4px' }}>
            {strategies.length > 0 ? '● Scanning candle signals' : 'No strategies active (N/A)'}
          </div>
        </div>

        {/* Total Placed Orders */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-purple)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>TOTAL EXECUTIONS TODAY</span>
            <Activity size={18} color="var(--accent-purple)" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: '#fff', marginTop: '8px' }}>
            {brokerSession?.connected ? dhanOrders.length : orders.length}{' '}
            <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>Orders Filled</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: brokerSession?.connected ? 'var(--accent-emerald)' : 'var(--text-dim)', marginTop: '4px' }}>
            {brokerSession?.connected ? '● Live Dhan HQ Execution' : '● Broker Not Connected'}
          </div>
        </div>

        {/* Broker Connection Status */}
        <div
          className="glass-panel"
          onClick={() => onNavigate && onNavigate('trader-broker')}
          style={{
            padding: '20px',
            borderLeft: `4px solid ${brokerSession?.connected ? 'var(--accent-emerald)' : 'var(--accent-amber)'}`,
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>BROKER GATEWAY</span>
            <TrendingUp size={18} color={brokerSession?.connected ? 'var(--accent-emerald)' : 'var(--accent-amber)'} />
          </div>
          <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff', marginTop: '8px' }}>
            {brokerSession?.connected ? `${brokerSession.brokerCode} Active` : 'Disconnected'}
          </div>
          <div style={{ fontSize: '0.75rem', color: brokerSession?.connected ? 'var(--accent-emerald)' : 'var(--accent-amber)', marginTop: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{brokerSession?.connected ? `Client: ${brokerSession.accountClientId}` : 'Click to bind broker'}</span>
            <span style={{ textDecoration: 'underline' }}>Configure &rarr;</span>
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

        {strategies.length === 0 ? (
          <div className="glass-panel" style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-dim)' }}>
            No algorithmic strategies deployed yet. Click "Browse All Strategies" to select and deploy.
          </div>
        ) : (
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
                  <span className="badge badge-active">{s.mode || 'LIVE'}</span>
                </div>

                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', fontSize: '0.75rem' }}>
                  <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)' }}>
                    {s.underlying || 'N/A'}
                  </span>
                  <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.15)', color: 'var(--accent-purple)' }}>
                    {s.timeframe || '5m'}
                  </span>
                </div>

                {/* Real-Time Execution Status Box */}
                <div style={{
                  background: s.latestExecution?.status === 'RUNNING' 
                    ? 'rgba(16, 185, 129, 0.08)' 
                    : (s.latestExecution?.status === 'SQUARED_OFF' ? 'rgba(148, 163, 184, 0.06)' : 'rgba(15, 23, 42, 0.5)'),
                  border: s.latestExecution?.status === 'RUNNING' 
                    ? '1px solid rgba(16, 185, 129, 0.3)' 
                    : '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '12px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  fontSize: '0.8rem'
                }}>
                  {/* Stage 1: Entry Condition */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {s.latestExecution?.entryMatched ? (
                        <CheckCircle2 size={15} color="var(--accent-emerald)" />
                      ) : (
                        <Clock size={15} color="var(--accent-cyan)" />
                      )}
                      <span style={{ fontWeight: 700, color: s.latestExecution?.entryMatched ? 'var(--accent-emerald)' : 'var(--accent-cyan)' }}>
                        {s.latestExecution?.entryMatched ? '1. ENTRY MATCHED' : '1. SCANNING MARKET'}
                      </span>
                    </div>
                    {s.latestExecution?.entryTime && (
                      <span className="font-mono" style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {s.latestExecution.entryTime}
                      </span>
                    )}
                  </div>
                  {s.latestExecution?.primaryEntryRule && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-main)', paddingLeft: '21px' }}>
                      Rule: <code style={{ color: 'var(--accent-cyan)' }}>{s.latestExecution.primaryEntryRule}</code>
                    </div>
                  )}

                  {/* Stage 2: Trade Position */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-subtle)', paddingTop: '6px', marginTop: '2px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Activity size={15} color={s.latestExecution?.status === 'RUNNING' ? 'var(--accent-emerald)' : 'var(--text-muted)'} />
                      <span style={{ fontWeight: 700, color: '#fff' }}>2. TRADE POSITION:</span>
                    </div>
                    {s.latestExecution?.status === 'RUNNING' ? (
                      <span style={{
                        background: 'rgba(16, 185, 129, 0.2)',
                        color: 'var(--accent-emerald)',
                        fontWeight: 800,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '0.75rem'
                      }}>
                        🟢 IN PROFIT ({s.latestExecution.currentPnl != null ? `${Number(s.latestExecution.currentPnl) >= 0 ? '+' : ''}₹${Number(s.latestExecution.currentPnl).toFixed(2)}` : 'Live'})
                      </span>
                    ) : s.latestExecution?.status === 'SQUARED_OFF' ? (
                      <span style={{
                        background: 'rgba(148, 163, 184, 0.2)',
                        color: '#94a3b8',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '0.75rem'
                      }}>
                        🛑 SQUARED OFF ({s.latestExecution.realizedPnl != null ? `${Number(s.latestExecution.realizedPnl) >= 0 ? '+' : ''}₹${Number(s.latestExecution.realizedPnl).toFixed(2)}` : 'Closed'})
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>No Active Trade</span>
                    )}
                  </div>
                  {s.latestExecution?.activeLeg && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', paddingLeft: '21px' }}>
                      Contract: {s.latestExecution.activeLeg}
                    </div>
                  )}

                  {/* Stage 3: Exit Condition */}
                  <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '6px', marginTop: '2px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Clock size={15} color={s.latestExecution?.exitMatched ? 'var(--accent-purple)' : 'var(--accent-amber)'} />
                      <span style={{ fontWeight: 700, color: s.latestExecution?.exitMatched ? 'var(--accent-purple)' : 'var(--accent-amber)' }}>
                        {s.latestExecution?.exitMatched ? '3. EXIT TRIGGERED' : '3. MONITORING EXITS'}
                      </span>
                    </div>
                    {s.latestExecution?.primaryExitRule && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', paddingLeft: '21px' }}>
                        Exit Watcher: {s.latestExecution.primaryExitRule}
                      </div>
                    )}
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px' }}>
                  <button
                    onClick={() => handleSimulateTrade(s.id)}
                    disabled={actionLoading === s.id}
                    className="btn btn-emerald"
                    style={{ padding: '8px', fontSize: '0.75rem', justifyContent: 'center' }}
                  >
                    <Zap size={14} />
                    <span>Run Signal</span>
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
        )}
      </div>
    </div>
  );
};

export default TraderDashboardPage;
