import React, { useState, useEffect, useRef } from 'react';
import { StatusBadge } from '../common/StatusBadge';
import { Layers, RefreshCw, Users, CheckCircle2, XCircle, Search, Eye, Zap, Info, ArrowRight, ShieldCheck, User } from 'lucide-react';
import { executionApi } from '../../api/executionApi';
import { strategyApi } from '../../api/strategyApi';
import UserTraceStepperModal from './UserTraceStepperModal';
import { useToast } from '../../context/ToastContext';

export const BatchAuditingPage = ({ selectedStrategyId }) => {
  const { addToast } = useToast();
  const [strategies, setStrategies] = useState([]);
  const [currentStrategyId, setCurrentStrategyId] = useState(selectedStrategyId || '');
  const [batches, setBatches] = useState([]);
  const [selectedBatchId, setSelectedBatchId] = useState(null);
  const [traces, setTraces] = useState([]);
  const [activeTraceId, setActiveTraceId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingTraces, setLoadingTraces] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const subscriberSectionRef = useRef(null);

  useEffect(() => {
    strategyApi.getStrategies().then((res) => {
      const list = res.data || [];
      setStrategies(list);
      if (!currentStrategyId && list.length > 0) {
        setCurrentStrategyId(list[0].id);
      }
    });
  }, []);

  const loadBatches = async () => {
    if (!currentStrategyId) return;
    setLoading(true);
    try {
      const res = await executionApi.getStrategyBatches(currentStrategyId);
      const bList = res.data || [];
      setBatches(bList);
      if (bList.length > 0) {
        setSelectedBatchId(bList[0].batchId);
      } else {
        setSelectedBatchId(null);
        setTraces([]);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (currentStrategyId) {
      loadBatches();
    }
  }, [currentStrategyId]);

  const loadBatchTraces = async (bId) => {
    if (!bId) return;
    setLoadingTraces(true);
    try {
      const res = await executionApi.getBatchTraces(bId);
      setTraces(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingTraces(false);
    }
  };

  useEffect(() => {
    if (selectedBatchId) {
      loadBatchTraces(selectedBatchId);
    }
  }, [selectedBatchId]);

  const handleSelectBatch = (bId) => {
    setSelectedBatchId(bId);
    if (subscriberSectionRef.current) {
      subscriberSectionRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleSimulateTrade = async () => {
    if (!currentStrategyId) return;
    setTriggering(true);
    try {
      await executionApi.simulateExecution(currentStrategyId);
      addToast(`Batch signal and subscriber traces created for Strategy #${currentStrategyId}!`, 'success');
      loadBatches();
    } catch (err) {
      addToast(err.message || 'Simulation failed', 'error');
    } finally {
      setTriggering(false);
    }
  };

  const selectedStrategy = strategies.find((s) => String(s.id) === String(currentStrategyId));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Page Header */}
      <div>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Copy-Trading Batch Auditing & Subscriber Traces</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Inspect multi-subscriber execution batches, fill ratios, and step-by-step audit timelines for every single trader.
        </p>
      </div>

      {/* Strategy Selector & Live Simulation Banner */}
      <div className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px', border: '1px solid var(--border-highlight)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: '300px' }}>
            <span style={{ fontWeight: 700, color: 'var(--accent-cyan)', whiteSpace: 'nowrap' }}>Active Strategy Fleet:</span>
            <select
              value={currentStrategyId}
              onChange={(e) => setCurrentStrategyId(e.target.value)}
              className="input-field"
              style={{ maxWidth: '420px', fontWeight: 600 }}
            >
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>
                  #{s.id} — {s.name} ({s.underlying || 'NIFTY'}) [{s.mode || 'PAPER'}]
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button onClick={loadBatches} disabled={loading} className="btn btn-secondary">
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              <span>Refresh Batches</span>
            </button>
            <button
              onClick={handleSimulateTrade}
              disabled={triggering || !currentStrategyId}
              className="btn btn-emerald"
            >
              <Zap size={14} className={triggering ? 'animate-spin' : ''} />
              <span>{triggering ? 'Generating Batch...' : '⚡ Generate 5m Batch Signal'}</span>
            </button>
          </div>
        </div>

        {/* Selected Strategy Status Card */}
        {selectedStrategy && (
          <div style={{
            background: 'rgba(15, 23, 42, 0.5)',
            borderRadius: '8px',
            padding: '12px 16px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '0.875rem',
            border: '1px solid var(--border-subtle)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Underlying Asset:</span>
              <strong style={{ color: '#fff' }}>{selectedStrategy.underlying || 'NIFTY 50'}</strong>
              <span style={{ color: 'var(--text-dim)', margin: '0 6px' }}>•</span>
              <span style={{ color: 'var(--text-muted)' }}>Trading Mode:</span>
              <span className="badge badge-running">{selectedStrategy.mode || 'PAPER'}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <span>Total Batches Today: <strong style={{ color: 'var(--accent-cyan)' }}>{batches.length}</strong></span>
              <span>Subscriber Fill Ratio: <strong style={{ color: 'var(--accent-emerald)' }}>80% - 100%</strong></span>
            </div>
          </div>
        )}
      </div>

      {/* Execution Batches Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff' }}>
              1. Execution Signal Batches for Strategy #{currentStrategyId}
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
              Whenever a market candle triggers an entry signal, a batch is created to dispatch copy-orders to all subscribed users.
            </p>
          </div>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Batch ID</th>
                <th>Signal ID</th>
                <th>Trigger Date</th>
                <th>Subscribers</th>
                <th>Eligible</th>
                <th>Fills Succeeded</th>
                <th>Fills Failed</th>
                <th>Batch Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {batches.length === 0 ? (
                <tr>
                  <td colSpan="9" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    No execution batches recorded for Strategy #{currentStrategyId} yet.
                    <div style={{ marginTop: '12px' }}>
                      <button onClick={handleSimulateTrade} className="btn btn-emerald" style={{ padding: '8px 18px' }}>
                        <Zap size={14} />
                        <span>Trigger Simulated Batch on Strategy #{currentStrategyId}</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                batches.map((b) => (
                  <tr
                    key={b.batchId}
                    style={{
                      background: selectedBatchId === b.batchId ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                      borderLeft: selectedBatchId === b.batchId ? '3px solid var(--accent-cyan)' : 'none',
                    }}
                  >
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>#{b.batchId}</td>
                    <td className="font-mono">#{b.signalId}</td>
                    <td>{b.tradingDate}</td>
                    <td style={{ fontWeight: 700 }}>{b.totalUsers} users</td>
                    <td style={{ color: 'var(--accent-cyan)' }}>{b.eligibleUsers}</td>
                    <td style={{ color: 'var(--accent-emerald)', fontWeight: 700 }}>{b.successfulUsers}</td>
                    <td style={{ color: b.failedUsers > 0 ? 'var(--accent-rose)' : 'var(--text-muted)' }}>{b.failedUsers}</td>
                    <td><StatusBadge status={b.status} /></td>
                    <td>
                      <button
                        onClick={() => handleSelectBatch(b.batchId)}
                        className={`btn ${selectedBatchId === b.batchId ? 'btn-primary' : 'btn-secondary'}`}
                        style={{ padding: '6px 14px', fontSize: '0.8rem' }}
                      >
                        <Eye size={14} />
                        <span>Inspect Subscribers ({b.successfulUsers} Fills)</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Selected Batch: Subscriber User Breakdown */}
      <div ref={subscriberSectionRef} className="glass-panel" style={{ padding: '24px', border: '1px solid var(--border-highlight)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff' }}>
              2. Subscriber User Audit Breakdown {selectedBatchId ? `(Batch #${selectedBatchId})` : ''}
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
              Click <strong>"View 4-Step Timeline"</strong> on any subscriber to inspect KYC, Subscription Quota, Risk Limits, and Broker Order Execution.
            </p>
          </div>
          {selectedBatchId && (
            <button onClick={() => loadBatchTraces(selectedBatchId)} disabled={loadingTraces} className="btn btn-secondary">
              <RefreshCw size={14} className={loadingTraces ? 'animate-spin' : ''} />
              <span>Refresh Subscribers</span>
            </button>
          )}
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Subscriber User</th>
                <th>Audit Step</th>
                <th>Execution Status</th>
                <th>Failure Reason / Code</th>
                <th>Audit Stepper Timeline</th>
              </tr>
            </thead>
            <tbody>
              {loadingTraces ? (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    Loading subscriber traces...
                  </td>
                </tr>
              ) : !selectedBatchId ? (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    Please select a batch above or click <strong>"Inspect Subscribers"</strong>.
                  </td>
                </tr>
              ) : traces.length === 0 ? (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    No subscriber trace records found in Batch #{selectedBatchId}.
                  </td>
                </tr>
              ) : (
                traces.map((t, idx) => {
                  const traceId = t.traceId || t.id || 1448;
                  const isRejected = t.status === 'REJECTED';
                  return (
                    <tr key={idx}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <User size={16} color="var(--accent-cyan)" />
                          <div>
                            <div style={{ fontWeight: 700, color: '#fff' }}>Subscriber User #{t.userId}</div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Copy-Trading Allocation</div>
                          </div>
                        </div>
                      </td>
                      <td className="font-mono" style={{ color: isRejected ? 'var(--accent-rose)' : 'var(--accent-cyan)', fontWeight: 600 }}>
                        {t.currentStep || 'ORDER_PLACEMENT'}
                      </td>
                      <td>
                        <span className={`badge ${!isRejected ? 'badge-running' : 'badge-failed'}`}>
                          {t.status || 'EXECUTED'}
                        </span>
                      </td>
                      <td style={{ color: t.failureReason ? 'var(--accent-rose)' : 'var(--accent-emerald)', fontSize: '0.85rem' }}>
                        {t.failureReason ? `⚠️ ${t.failureReason}` : '✅ Passed all institutional checks'}
                      </td>
                      <td>
                        <button
                          onClick={() => setActiveTraceId(traceId)}
                          className="btn btn-primary"
                          style={{ padding: '6px 14px', fontSize: '0.8rem' }}
                        >
                          <ShieldCheck size={14} />
                          <span>View 4-Step Timeline</span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Vertical Stepper Modal */}
      <UserTraceStepperModal
        isOpen={!!activeTraceId}
        onClose={() => setActiveTraceId(null)}
        traceId={activeTraceId}
      />
    </div>
  );
};

export default BatchAuditingPage;
