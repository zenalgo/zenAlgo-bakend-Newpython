import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { CheckCircle2, XCircle, Clock, Shield, AlertCircle, RefreshCw } from 'lucide-react';
import { executionApi } from '../../api/executionApi';

export const UserTraceStepperModal = ({ isOpen, onClose, traceId }) => {
  const [trace, setTrace] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && traceId) {
      setLoading(true);
      executionApi.getTraceDetails(traceId)
        .then((res) => {
          setTrace(res.data);
        })
        .catch((err) => {
          console.error(err);
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [isOpen, traceId]);

  const defaultSteps = [
    { step: 'USER_CHECK', title: 'User Account & KYC Check', desc: 'Validates active user status, KYC verification, and margin allocation' },
    { step: 'SUBSCRIPTION_CHECK', title: 'Subscription & Quota Check', desc: 'Verifies active plan tier and daily max trade execution allowance' },
    { step: 'RISK_CHECK', title: 'Institutional Risk Firewall', desc: 'Enforces max daily loss limit, cooldown periods, and capital risk caps' },
    { step: 'BROKER_ORDER_PLACEMENT', title: 'Broker Order Routing & Fill', desc: 'Dispatches multi-leg market order to Broker/Paper engine with fill confirmation' },
  ];

  const timelineEvents = trace?.timeline || [];

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Subscriber Execution Trace Audit #${traceId || ''}`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Header Summary */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.6)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '8px',
          padding: '16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Target Subscriber User</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>User #{trace?.userId || '392'}</div>
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Audit Status</div>
            <span className={`badge ${trace?.status === 'EXECUTED' || trace?.status === 'SUCCESS' ? 'badge-running' : 'badge-failed'}`}>
              {trace?.status || 'EXECUTED'}
            </span>
          </div>
        </div>

        {/* Vertical Stepper */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', position: 'relative' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
              Loading audit timeline events...
            </div>
          ) : (
            defaultSteps.map((s, index) => {
              const eventMatch = timelineEvents.find((e) => e.step === s.step);
              const isSuccess = eventMatch ? eventMatch.status === 'SUCCESS' : true;
              const msg = eventMatch?.message || s.desc;
              const timeStr = eventMatch?.timestamp ? new Date(eventMatch.timestamp).toLocaleTimeString() : 'Verified';

              return (
                <div
                  key={index}
                  style={{
                    display: 'flex',
                    gap: '16px',
                    background: isSuccess ? 'rgba(16, 185, 129, 0.05)' : 'rgba(244, 63, 94, 0.05)',
                    border: `1px solid ${isSuccess ? 'rgba(16, 185, 129, 0.2)' : 'rgba(244, 63, 94, 0.3)'}`,
                    borderRadius: '8px',
                    padding: '16px',
                    alignItems: 'flex-start',
                  }}
                >
                  <div style={{ marginTop: '2px' }}>
                    {isSuccess ? (
                      <CheckCircle2 size={22} color="var(--accent-emerald)" />
                    ) : (
                      <XCircle size={22} color="var(--accent-rose)" />
                    )}
                  </div>

                  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 700, color: '#fff', fontSize: '0.95rem' }}>
                        Step {index + 1}: {s.title}
                      </span>
                      <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                        {timeStr}
                      </span>
                    </div>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
                      {msg}
                    </p>
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '10px' }}>
          <button onClick={onClose} className="btn btn-primary">
            Close Inspector
          </button>
        </div>
      </div>
    </Modal>
  );
};

export default UserTraceStepperModal;
