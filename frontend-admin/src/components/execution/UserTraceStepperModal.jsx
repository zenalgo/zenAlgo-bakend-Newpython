import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { StatusBadge } from '../common/StatusBadge';
import { CheckCircle2, XCircle, Clock, AlertCircle } from 'lucide-react';
import { executionApi } from '../../api/executionApi';

export const UserTraceStepperModal = ({ isOpen, onClose, traceId }) => {
  const [trace, setTrace] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isOpen && traceId) {
      setLoading(true);
      executionApi.getTraceDetails(traceId)
        .then((res) => setTrace(res.data))
        .catch((err) => console.error(err))
        .finally(() => setLoading(false));
    }
  }, [isOpen, traceId]);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Subscriber Execution Trace Audit #${traceId || ''}`}>
      {loading ? (
        <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
          Loading trace timeline...
        </div>
      ) : !trace ? (
        <div style={{ textAlign: 'center', padding: '30px', color: 'var(--accent-rose)' }}>
          Trace record not found.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Header Summary */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            gap: '12px',
            background: 'var(--bg-input)',
            padding: '16px',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle)',
          }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>SUBSCRIBER USER ID</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>#{trace.userId}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>EXECUTION STATUS</div>
              <div style={{ marginTop: '4px' }}><StatusBadge status={trace.status} /></div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>CURRENT STEP</div>
              <div className="font-mono" style={{ fontSize: '0.9rem', fontWeight: 600, marginTop: '4px' }}>{trace.currentStep || 'COMPLETED'}</div>
            </div>
          </div>

          {trace.failureReason && (
            <div style={{
              background: 'rgba(244, 63, 94, 0.15)',
              border: '1px solid rgba(244, 63, 94, 0.3)',
              padding: '12px 16px',
              borderRadius: '8px',
              color: '#fb7185',
              fontSize: '0.875rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}>
              <AlertCircle size={18} />
              <span><strong>Failure Reason:</strong> {trace.failureReason} ({trace.failureCode})</span>
            </div>
          )}

          {/* Stepper Timeline */}
          <div>
            <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '14px' }}>
              Step-by-Step Live Audit Stepper
            </h4>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0', position: 'relative', paddingLeft: '24px' }}>
              {/* Vertical line */}
              <div style={{
                position: 'absolute',
                top: '12px',
                bottom: '12px',
                left: '7px',
                width: '2px',
                background: 'var(--border-highlight)',
              }}></div>

              {(trace.timeline || []).length === 0 ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No individual step logs recorded for this trace.</div>
              ) : (
                trace.timeline.map((event, idx) => {
                  const isSuccess = event.status === 'SUCCESS';
                  return (
                    <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', marginBottom: '18px', position: 'relative' }}>
                      <div style={{
                        position: 'absolute',
                        left: '-24px',
                        background: isSuccess ? 'var(--accent-emerald)' : 'var(--accent-rose)',
                        color: '#000',
                        borderRadius: '50%',
                        width: '16px',
                        height: '16px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        marginTop: '3px',
                      }}>
                        {isSuccess ? <CheckCircle2 size={12} color="#000" /> : <XCircle size={12} color="#fff" />}
                      </div>

                      <div style={{ flex: 1, background: 'rgba(255, 255, 255, 0.02)', padding: '10px 14px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span className="font-mono" style={{ fontWeight: 700, fontSize: '0.85rem', color: isSuccess ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                            {event.step}
                          </span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Clock size={12} />
                            {new Date(event.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        {event.message && (
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                            {event.message}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
};

export default UserTraceStepperModal;
