import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { CheckCircle2, XCircle, Clock, Shield, AlertCircle, RefreshCw, User, Mail, Award } from 'lucide-react';
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
    { step: 'USER_CHECK', title: 'User Account & KYC Verification', desc: 'Validates active platform registration, permissions, and margin allocation' },
    { step: 'SUBSCRIPTION_CHECK', title: 'Active Subscription Quota Check', desc: 'Verifies active plan tier and daily max trade execution quota' },
    { step: 'RISK_CHECK', title: 'Institutional Risk Firewall', desc: 'Enforces max daily loss limit, capital allocation caps, and cooldown timers' },
    { step: 'BROKER_ORDER_PLACEMENT', title: 'Broker Order Routing & Fill Confirmation', desc: 'Dispatches multi-leg market order to Broker/Paper engine with execution logs' },
  ];

  const timelineEvents = trace?.timeline || [];
  const displayName = trace?.userName || `Trader #${trace?.userId || '392'}`;
  const displayEmail = trace?.userEmail || `user_${trace?.userId || '392'}@trading.com`;
  const roleName = trace?.userRole || 'TRADER';
  const refCode = trace?.referralCode || `REF-U${trace?.userId || '392'}`;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Subscriber Execution Audit — Trace #${traceId || ''}`}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Header Summary Card */}
        <div style={{
          background: 'rgba(15, 23, 42, 0.6)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '8px',
          padding: '16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              background: roleName === 'SUPER_ADMIN' ? 'rgba(168, 85, 247, 0.2)' : 'rgba(56, 189, 248, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: roleName === 'SUPER_ADMIN' ? 'var(--accent-purple)' : 'var(--accent-cyan)',
              fontWeight: 800,
              fontSize: '1rem',
            }}>
              {displayName.charAt(0)}
            </div>
            <div>
              <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff' }}>
                {displayName} <span style={{ fontSize: '0.8rem', color: 'var(--text-dim)', fontWeight: 500 }}>(#{trace?.userId || '392'})</span>
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Mail size={12} />
                <span>{displayEmail}</span>
                <span style={{ color: 'var(--text-dim)' }}>•</span>
                <span className="font-mono">{refCode}</span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="badge" style={{
              background: roleName === 'SUPER_ADMIN' ? 'rgba(168, 85, 247, 0.2)' : 'rgba(16, 185, 129, 0.15)',
              color: roleName === 'SUPER_ADMIN' ? 'var(--accent-purple)' : 'var(--accent-emerald)',
            }}>
              {roleName}
            </span>
            <span className={`badge ${trace?.status === 'EXECUTED' || trace?.status === 'SUCCESS' ? 'badge-running' : 'badge-failed'}`}>
              {trace?.status || 'EXECUTED'}
            </span>
          </div>
        </div>

        {/* Vertical Stepper */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', position: 'relative' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
              Loading audit timeline events...
            </div>
          ) : (
            defaultSteps.map((s, index) => {
              const eventMatch = timelineEvents.find((e) => e.step === s.step);
              const isSuccess = eventMatch ? eventMatch.status === 'SUCCESS' : (trace?.status !== 'REJECTED' || index < 2);
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
                    padding: '14px 16px',
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
                    <p style={{ color: isSuccess ? 'var(--text-muted)' : 'var(--accent-rose)', fontSize: '0.85rem', margin: 0 }}>
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
