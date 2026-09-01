import React, { useState, useEffect } from 'react';
import { StatusBadge } from '../common/StatusBadge';
import { Layers, RefreshCw, Users, CheckCircle2, XCircle, Search, Eye } from 'lucide-react';
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

  useEffect(() => {
    if (selectedBatchId) {
      executionApi.getBatchTraces(selectedBatchId).then((res) => {
        setTraces(res.data || []);
      });
    }
  }, [selectedBatchId]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Copy-Trading Batch Auditing</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Inspect subscriber execution batches, fill ratios, and step-by-step audit timelines.</p>
      </div>

      {/* Selector */}
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', gap: '16px' }}>
        <label style={{ margin: 0, whiteSpace: 'nowrap' }}>Strategy:</label>
        <select
          value={currentStrategyId}
          onChange={(e) => setCurrentStrategyId(e.target.value)}
          className="input-field"
          style={{ maxWidth: '400px' }}
        >
          {strategies.map((s) => (
            <option key={s.id} value={s.id}>
              #{s.id} — {s.name}
            </option>
          ))}
        </select>
        <button onClick={loadBatches} className="btn btn-secondary" style={{ marginLeft: 'auto' }}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Batches</span>
        </button>
      </div>

      {/* Batches Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', marginBottom: '14px' }}>
          Execution Signal Batches
        </h3>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Batch ID</th>
                <th>Signal ID</th>
                <th>Date</th>
                <th>Total Users</th>
                <th>Eligible</th>
                <th>Successful</th>
                <th>Failed</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {batches.length === 0 ? (
                <tr>
                  <td colSpan="9" style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    No execution batches recorded yet.
                  </td>
                </tr>
              ) : (
                batches.map((b) => (
                  <tr key={b.batchId} style={{ background: selectedBatchId === b.batchId ? 'rgba(56, 189, 248, 0.08)' : 'transparent' }}>
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>#{b.batchId}</td>
                    <td className="font-mono">#{b.signalId}</td>
                    <td>{b.tradingDate}</td>
                    <td style={{ fontWeight: 700 }}>{b.totalUsers}</td>
                    <td style={{ color: 'var(--accent-cyan)' }}>{b.eligibleUsers}</td>
                    <td style={{ color: 'var(--accent-emerald)', fontWeight: 700 }}>{b.successfulUsers}</td>
                    <td style={{ color: b.failedUsers > 0 ? 'var(--accent-rose)' : 'var(--text-muted)' }}>{b.failedUsers}</td>
                    <td><StatusBadge status={b.status} /></td>
                    <td>
                      <button
                        onClick={() => setSelectedBatchId(b.batchId)}
                        className="btn btn-secondary"
                        style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                      >
                        <Eye size={12} />
                        <span>Inspect Users</span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Traces in Selected Batch */}
      {selectedBatchId && (
        <div className="glass-panel" style={{ padding: '24px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', marginBottom: '14px' }}>
            Subscriber Traces in Batch #{selectedBatchId}
          </h3>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Subscriber User</th>
                  <th>Current Step</th>
                  <th>Execution Status</th>
                  <th>Failure Reason / Code</th>
                  <th>Audit Stepper</th>
                </tr>
              </thead>
              <tbody>
                {traces.length === 0 ? (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center', padding: '20px', color: 'var(--text-muted)' }}>
                      No subscriber trace records found in this batch.
                    </td>
                  </tr>
                ) : (
                  traces.map((t, idx) => (
                    <tr key={idx}>
                      <td style={{ fontWeight: 600 }}>User #{t.userId}</td>
                      <td className="font-mono">{t.currentStep || 'COMPLETED'}</td>
                      <td><StatusBadge status={t.status} /></td>
                      <td style={{ color: t.failureReason ? 'var(--accent-rose)' : 'var(--text-muted)', fontSize: '0.8rem' }}>
                        {t.failureReason || '—'}
                      </td>
                      <td>
                        <button
                          onClick={() => setActiveTraceId(t.id || 1)}
                          className="btn btn-primary"
                          style={{ padding: '4px 10px', fontSize: '0.75rem' }}
                        >
                          Step Timeline
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Stepper Modal */}
      <UserTraceStepperModal
        isOpen={!!activeTraceId}
        onClose={() => setActiveTraceId(null)}
        traceId={activeTraceId}
      />
    </div>
  );
};

export default BatchAuditingPage;
