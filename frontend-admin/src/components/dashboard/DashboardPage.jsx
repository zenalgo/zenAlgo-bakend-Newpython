import React, { useState, useEffect } from 'react';
import { StatCard } from '../common/StatCard';
import { StatusBadge } from '../common/StatusBadge';
import { Zap, Activity, TrendingUp, Users, Play, ShieldAlert } from 'lucide-react';
import { strategyApi } from '../../api/strategyApi';
import { executionApi } from '../../api/executionApi';
import { useToast } from '../../context/ToastContext';

export const DashboardPage = ({ onNavigate }) => {
  const { addToast } = useToast();
  const [strategies, setStrategies] = useState([]);
  const [placedOrders, setPlacedOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchDashboardData = async () => {
    try {
      const res = await strategyApi.getStrategies();
      const list = res.data || [];
      setStrategies(list);

      if (list.length > 0) {
        const ordersRes = await executionApi.getPlacedOrders(list[0].id).catch(() => ({ data: [] }));
        setPlacedOrders(ordersRes.data || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const handleQuickDeploy = async (id) => {
    try {
      await strategyApi.activatePaper(id);
      addToast(`Strategy #${id} deployed into PAPER Trading!`, 'success');
      fetchDashboardData();
    } catch (err) {
      addToast(err.message || 'Activation failed', 'error');
    }
  };

  const activeCount = strategies.filter((s) => s.status === 'ACTIVE_LIVE' || s.status === 'ACTIVE' || s.mode === 'PAPER').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Platform Command Center</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Real-time algorithmic trading metrics, strategy states, and execution ledger.</p>
      </div>

      {/* Metric Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
        <StatCard title="Active Strategies" value={activeCount} subtitle="Deployed in Paper/Live" icon={Zap} color="cyan" />
        <StatCard title="Total Strategies" value={strategies.length} subtitle="Provisioned on Platform" icon={Activity} color="purple" />
        <StatCard title="Simulated Paper PnL" value="₹+12,450.00" subtitle="Win Rate: 72.4%" icon={TrendingUp} color="emerald" trend={14.2} />
        <StatCard title="Total Subscribers" value="142" subtitle="Active Copy-Traders" icon={Users} color="amber" />
      </div>

      {/* Strategies Overview Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>Active Strategy Fleet</h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Continuous tick-by-tick monitoring & signal generation</span>
          </div>
          <button onClick={() => onNavigate('builder')} className="btn btn-primary" style={{ fontSize: '0.8rem' }}>
            + Create / AI Generate Strategy
          </button>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Strategy ID</th>
                <th>Strategy Name</th>
                <th>Underlying & TF</th>
                <th>Mode</th>
                <th>Engine State</th>
                <th>Target / Risk</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {strategies.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    No strategies created yet. Click "Create / AI Generate Strategy" to start!
                  </td>
                </tr>
              ) : (
                strategies.slice(0, 5).map((s) => (
                  <tr key={s.id}>
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>#{s.id}</td>
                    <td style={{ fontWeight: 600 }}>{s.name}</td>
                    <td>{s.underlying || 'NIFTY'} <span style={{ color: 'var(--text-dim)' }}>({s.timeframe || '5m'})</span></td>
                    <td><StatusBadge status={s.mode || 'PAPER'} /></td>
                    <td><StatusBadge status={s.status || 'WAITING'} /></td>
                    <td>
                      <span className="font-mono" style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>
                        {typeof s.target === 'object' ? s.target?.value || '2R' : s.target || '2R'}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          onClick={() => handleQuickDeploy(s.id)}
                          className="btn btn-emerald"
                          style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                        >
                          <Play size={12} />
                          <span>Deploy</span>
                        </button>
                        <button
                          onClick={() => onNavigate('placed-orders')}
                          className="btn btn-secondary"
                          style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                        >
                          Orders
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

export default DashboardPage;
