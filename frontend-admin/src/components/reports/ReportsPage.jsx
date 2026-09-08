import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart3, RefreshCw, TrendingUp, TrendingDown, Users,
  Zap, Activity, Target, Award, ChevronUp, ChevronDown
} from 'lucide-react';
import { reportsApi } from '../../api/executionApi';

const DAY_OPTIONS = [
  { label: '7 Days', value: 7 },
  { label: '30 Days', value: 30 },
  { label: '90 Days', value: 90 },
];

function SummaryCard({ icon: Icon, label, value, color, sub, trend }) {
  return (
    <div style={{
      padding: '22px 24px', borderRadius: '16px',
      background: 'linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
      border: `1px solid ${color}25`,
      position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', top: -20, right: -20, opacity: 0.05 }}>
        <Icon size={100} color={color} />
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <div style={{ padding: '8px', borderRadius: '10px', background: `${color}18` }}>
              <Icon size={18} color={color} />
            </div>
            <span style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
          </div>
          <div style={{ fontSize: '2.2rem', fontWeight: 900, color, lineHeight: 1 }}>{value}</div>
          {sub && <div style={{ fontSize: '0.75rem', color: '#475569', marginTop: '6px' }}>{sub}</div>}
        </div>
        {trend !== undefined && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '3px',
            fontSize: '0.8rem', fontWeight: 700,
            color: trend >= 0 ? '#10b981' : '#ef4444',
            background: trend >= 0 ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
            padding: '4px 8px', borderRadius: '8px',
          }}>
            {trend >= 0 ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {Math.abs(trend)}%
          </div>
        )}
      </div>
    </div>
  );
}

// Tiny bar chart rendered with pure CSS/HTML (no library)
function MiniBarChart({ data }) {
  if (!data || data.length === 0) return (
    <div style={{ padding: '40px', textAlign: 'center', color: '#475569', fontSize: '0.85rem' }}>No activity data for this period.</div>
  );

  const maxSuccess = Math.max(...data.map(d => d.successfulUsers), 1);
  const maxFailed = Math.max(...data.map(d => d.failedUsers), 1);
  const maxVal = Math.max(maxSuccess, maxFailed, 1);
  const barH = 120;

  return (
    <div style={{ overflowX: 'auto', paddingBottom: '8px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '6px', minWidth: `${data.length * 42}px`, padding: '0 4px' }}>
        {data.map((d, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '3px', flex: '0 0 36px' }}>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: `${barH}px` }}>
              <div style={{
                width: '14px', background: 'linear-gradient(180deg, #10b981, #059669)',
                height: `${Math.max(2, (d.successfulUsers / maxVal) * barH)}px`,
                borderRadius: '3px 3px 0 0',
                transition: 'height 0.5s ease',
              }} title={`Success: ${d.successfulUsers}`} />
              <div style={{
                width: '14px', background: 'linear-gradient(180deg, #ef4444, #dc2626)',
                height: `${Math.max(2, (d.failedUsers / maxVal) * barH)}px`,
                borderRadius: '3px 3px 0 0',
                transition: 'height 0.5s ease',
              }} title={`Failed: ${d.failedUsers}`} />
            </div>
            <div style={{ fontSize: '0.58rem', color: '#475569', textAlign: 'center', lineHeight: 1.2 }}>
              {new Date(d.tradingDate).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: '16px', marginTop: '12px', paddingLeft: '4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.73rem', color: '#64748b' }}>
          <div style={{ width: '12px', height: '12px', borderRadius: '3px', background: '#10b981' }} /> Success
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.73rem', color: '#64748b' }}>
          <div style={{ width: '12px', height: '12px', borderRadius: '3px', background: '#ef4444' }} /> Failed
        </div>
      </div>
    </div>
  );
}

function SuccessRateBar({ rate }) {
  const color = rate >= 80 ? '#10b981' : rate >= 50 ? '#f59e0b' : '#ef4444';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div style={{ flex: 1, height: '6px', borderRadius: '3px', background: 'rgba(255,255,255,0.08)' }}>
        <div style={{ width: `${rate}%`, height: '100%', borderRadius: '3px', background: color }} />
      </div>
      <span style={{ fontSize: '0.78rem', fontWeight: 700, color, minWidth: '38px' }}>{rate}%</span>
    </div>
  );
}

export const ReportsPage = () => {
  const [activeTab, setActiveTab] = useState('summary');
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState(null);
  const [execSummary, setExecSummary] = useState([]);
  const [daily, setDaily] = useState([]);
  const [userPerf, setUserPerf] = useState([]);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [sumRes, execRes, dailyRes, userRes] = await Promise.all([
        reportsApi.getSummary(days),
        reportsApi.getExecutionSummary(days),
        reportsApi.getDailyActivity(days),
        reportsApi.getUserPerformance(days, { page: 0, size: 50 }),
      ]);
      setSummary(sumRes.data?.data);
      setExecSummary(execRes.data?.data || []);
      setDaily(dailyRes.data?.data || []);
      setUserPerf(userRes.data?.data || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [days]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const tabs = [
    { id: 'summary', label: 'Platform Overview', icon: Activity },
    { id: 'strategies', label: 'By Strategy', icon: Zap },
    { id: 'daily', label: 'Daily Activity', icon: BarChart3 },
    { id: 'users', label: 'User Performance', icon: Users },
  ];

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '28px' }}>
        <div>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 800, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '10px', margin: 0 }}>
            <BarChart3 size={26} color="#fb923c" /> Reports & Analytics
          </h1>
          <p style={{ color: '#64748b', fontSize: '0.875rem', marginTop: '4px' }}>Platform-wide execution analytics, strategy performance, and user P&L</p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          {/* Day selector */}
          <div style={{ display: 'flex', gap: '4px', background: 'rgba(255,255,255,0.04)', borderRadius: '10px', padding: '3px', border: '1px solid rgba(255,255,255,0.08)' }}>
            {DAY_OPTIONS.map(opt => (
              <button key={opt.value} onClick={() => setDays(opt.value)}
                style={{
                  padding: '6px 14px', borderRadius: '7px', border: 'none', cursor: 'pointer', fontSize: '0.78rem', fontWeight: 700,
                  background: days === opt.value ? 'rgba(251,146,60,0.2)' : 'transparent',
                  color: days === opt.value ? '#fb923c' : '#64748b',
                  transition: 'all 0.15s',
                }}>
                {opt.label}
              </button>
            ))}
          </div>
          <button onClick={fetchAll} disabled={loading} style={{
            display: 'flex', alignItems: 'center', gap: '6px', padding: '9px 18px',
            background: 'rgba(251,146,60,0.12)', border: '1px solid rgba(251,146,60,0.3)',
            color: '#fb923c', borderRadius: '9px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600,
          }}>
            <RefreshCw size={14} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            Refresh
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '28px', background: 'rgba(255,255,255,0.04)', padding: '4px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.07)', width: 'fit-content' }}>
        {tabs.map(t => {
          const Icon = t.icon;
          return (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: '7px',
                padding: '9px 18px', borderRadius: '9px', border: 'none', cursor: 'pointer',
                background: activeTab === t.id ? 'rgba(251,146,60,0.15)' : 'transparent',
                color: activeTab === t.id ? '#fb923c' : '#64748b',
                fontSize: '0.83rem', fontWeight: activeTab === t.id ? 700 : 500,
                transition: 'all 0.15s',
                borderBottom: activeTab === t.id ? '2px solid #fb923c' : '2px solid transparent',
              }}>
              <Icon size={15} /> {t.label}
            </button>
          );
        })}
      </div>

      {/* ── Tab: Platform Summary ── */}
      {activeTab === 'summary' && (
        <div>
          {summary ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '32px' }}>
              <SummaryCard icon={Zap} label="Total Strategies" value={summary.totalStrategies} color="#38bdf8" sub="Across platform" />
              <SummaryCard icon={Activity} label="Batches Run" value={summary.totalBatchesRun} color="#a78bfa" sub={`Last ${days} days`} />
              <SummaryCard icon={Target} label="Orders Placed" value={summary.totalOrdersPlaced} color="#fb923c" sub="Across all users" />
              <SummaryCard icon={Award} label="Success Rate" value={`${summary.overallSuccessRate}%`} color={summary.overallSuccessRate >= 70 ? '#10b981' : '#f59e0b'} sub="Overall fill rate" />
              <SummaryCard icon={Users} label="Active Users" value={summary.activeUsers} color="#10b981" sub={`Traded in last ${days} days`} />
            </div>
          ) : (
            <div style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
              {loading ? <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', color: '#fb923c' }} /> : 'No summary data yet.'}
            </div>
          )}

          {/* Daily chart preview */}
          <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '14px', padding: '24px' }}>
            <h3 style={{ margin: '0 0 20px', fontSize: '1rem', fontWeight: 700, color: '#e2e8f0', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <BarChart3 size={16} color="#fb923c" /> Daily Activity Chart
            </h3>
            <MiniBarChart data={daily} />
          </div>
        </div>
      )}

      {/* ── Tab: By Strategy ── */}
      {activeTab === 'strategies' && (
        <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '14px', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(0,0,0,0.2)' }}>
                {['Strategy', 'Batches', 'Users Served', 'Successful', 'Failed', 'Success Rate', 'Last Run'].map(h => (
                  <th key={h} style={{ padding: '14px 16px', textAlign: 'left', fontSize: '0.72rem', color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
                  <RefreshCw size={22} style={{ animation: 'spin 1s linear infinite', color: '#fb923c' }} />
                </td></tr>
              ) : execSummary.length === 0 ? (
                <tr><td colSpan={7} style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>No strategy execution data for this period.</td></tr>
              ) : execSummary.map(s => (
                <tr key={s.strategyId} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', transition: 'background 0.12s' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <td style={{ padding: '14px 16px' }}>
                    <div style={{ fontWeight: 700, fontSize: '0.85rem', color: '#e2e8f0' }}>{s.strategyName}</div>
                    <div style={{ fontSize: '0.72rem', color: '#475569' }}>ID #{s.strategyId}</div>
                  </td>
                  <td style={{ padding: '14px 16px', fontSize: '0.85rem', fontWeight: 700, color: '#a78bfa' }}>{s.totalBatches}</td>
                  <td style={{ padding: '14px 16px', fontSize: '0.85rem', color: '#94a3b8' }}>{s.totalUsersServed}</td>
                  <td style={{ padding: '14px 16px', fontSize: '0.85rem', color: '#10b981', fontWeight: 700 }}>{s.totalSuccessful}</td>
                  <td style={{ padding: '14px 16px', fontSize: '0.85rem', color: '#ef4444', fontWeight: 700 }}>{s.totalFailed}</td>
                  <td style={{ padding: '14px 16px', minWidth: '140px' }}><SuccessRateBar rate={s.successRate} /></td>
                  <td style={{ padding: '14px 16px', fontSize: '0.78rem', color: '#64748b' }}>{s.lastExecutedDate || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Tab: Daily Activity ── */}
      {activeTab === 'daily' && (
        <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '14px', padding: '24px' }}>
          <h3 style={{ margin: '0 0 24px', fontSize: '1rem', fontWeight: 700, color: '#e2e8f0' }}>
            Daily Execution Activity — Last {days} Days
          </h3>
          <MiniBarChart data={daily} />
          {!loading && daily.length > 0 && (
            <div style={{ marginTop: '28px', overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                    {['Date', 'Batches', 'Total Users', 'Successful', 'Failed', 'Success Rate'].map(h => (
                      <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: '0.72rem', color: '#475569', fontWeight: 700, textTransform: 'uppercase' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...daily].reverse().map((d, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
                      onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      <td style={{ padding: '10px 14px', fontSize: '0.82rem', color: '#94a3b8', fontWeight: 600 }}>
                        {new Date(d.tradingDate).toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short' })}
                      </td>
                      <td style={{ padding: '10px 14px', fontSize: '0.82rem', color: '#a78bfa', fontWeight: 700 }}>{d.totalBatches}</td>
                      <td style={{ padding: '10px 14px', fontSize: '0.82rem', color: '#94a3b8' }}>{d.totalUsers}</td>
                      <td style={{ padding: '10px 14px', fontSize: '0.82rem', color: '#10b981', fontWeight: 700 }}>{d.successfulUsers}</td>
                      <td style={{ padding: '10px 14px', fontSize: '0.82rem', color: '#ef4444', fontWeight: 700 }}>{d.failedUsers}</td>
                      <td style={{ padding: '10px 14px', minWidth: '140px' }}><SuccessRateBar rate={d.successRate} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Tab: User Performance ── */}
      {activeTab === 'users' && (
        <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: '14px', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(0,0,0,0.2)' }}>
                {['User', 'Email', 'Total Executions', 'Successful', 'Failed', 'Success Rate', 'Realized P&L'].map(h => (
                  <th key={h} style={{ padding: '14px 16px', textAlign: 'left', fontSize: '0.72rem', color: '#475569', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>
                  <RefreshCw size={22} style={{ animation: 'spin 1s linear infinite', color: '#fb923c' }} />
                </td></tr>
              ) : userPerf.length === 0 ? (
                <tr><td colSpan={7} style={{ padding: '60px', textAlign: 'center', color: '#64748b' }}>No user performance data for this period.</td></tr>
              ) : userPerf.map(u => (
                <tr key={u.userId} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', transition: 'background 0.12s' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <td style={{ padding: '14px 16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div style={{
                        width: '32px', height: '32px', borderRadius: '50%',
                        background: `hsl(${(u.userId * 47) % 360}, 65%, 20%)`,
                        border: `2px solid hsl(${(u.userId * 47) % 360}, 65%, 40%)`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '0.72rem', fontWeight: 800, color: `hsl(${(u.userId * 47) % 360}, 65%, 75%)`, flexShrink: 0,
                      }}>
                        {(u.userName || 'U')[0].toUpperCase()}
                      </div>
                      <div style={{ fontWeight: 600, fontSize: '0.83rem', color: '#e2e8f0' }}>{u.userName}</div>
                    </div>
                  </td>
                  <td style={{ padding: '14px 16px', fontSize: '0.78rem', color: '#64748b' }}>{u.userEmail}</td>
                  <td style={{ padding: '14px 16px', fontSize: '0.85rem', fontWeight: 700, color: '#a78bfa' }}>{u.totalExecutions}</td>
                  <td style={{ padding: '14px 16px', fontSize: '0.85rem', color: '#10b981', fontWeight: 700 }}>{u.successfulExecutions}</td>
                  <td style={{ padding: '14px 16px', fontSize: '0.85rem', color: '#ef4444', fontWeight: 700 }}>{u.failedExecutions}</td>
                  <td style={{ padding: '14px 16px', minWidth: '140px' }}><SuccessRateBar rate={u.successRate} /></td>
                  <td style={{ padding: '14px 16px', fontSize: '0.85rem', fontWeight: 800, color: u.totalRealizedPnl >= 0 ? '#10b981' : '#ef4444' }}>
                    {u.totalRealizedPnl >= 0 ? '+' : ''}₹{u.totalRealizedPnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </div>
  );
};

export default ReportsPage;
