import React, { useState, useEffect } from 'react';
import {
  Package,
  Check,
  Sparkles,
  Shield,
  ArrowUpRight,
  QrCode,
  Building2,
  Clock,
  CheckCircle2,
  AlertCircle,
  Copy,
  RefreshCw,
  Wallet,
} from 'lucide-react';
import { traderApi } from '../../api/traderApi';
import { Modal } from '../common/Modal';
import { useToast } from '../../context/ToastContext';

export const MySubscriptionPage = () => {
  const { addToast } = useToast();
  const [plans, setPlans] = useState([]);
  const [paymentMethods, setPaymentMethods] = useState([]);
  const [currentSub, setCurrentSub] = useState(null);
  const [loading, setLoading] = useState(true);

  // Purchase Modal State
  const [isPayModalOpen, setIsPayModalOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [selectedMethodType, setSelectedMethodType] = useState('UPI'); // 'UPI' | 'BANK_ACCOUNT'
  const [utrNumber, setUtrNumber] = useState('');
  const [userRemarks, setUserRemarks] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [resPlans, resMethods, resSub] = await Promise.allSettled([
        traderApi.getPlans(),
        traderApi.getActivePaymentMethods(),
        traderApi.getMySubscription(),
      ]);

      if (resPlans.status === 'fulfilled' && resPlans.value?.data) {
        setPlans(resPlans.value.data);
      }
      if (resMethods.status === 'fulfilled' && resMethods.value?.data) {
        setPaymentMethods(resMethods.value.data);
      }
      if (resSub.status === 'fulfilled' && resSub.value?.data) {
        setCurrentSub(resSub.value.data);
      }
    } catch (err) {
      console.error(err);
      addToast('Failed to load subscription data', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleOpenPay = (plan) => {
    setSelectedPlan(plan);
    setUtrNumber('');
    setUserRemarks('');
    setIsPayModalOpen(true);
  };

  const handleCopyText = (text, label) => {
    navigator.clipboard.writeText(text);
    addToast(`Copied ${label} to clipboard!`, 'info');
  };

  const handleSubmitPayment = async (e) => {
    e.preventDefault();
    if (!utrNumber || utrNumber.trim().length < 6) {
      addToast('Please enter a valid 6-20 digit UTR / Reference number', 'warning');
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        planId: selectedPlan.id,
        paymentMode: selectedMethodType === 'UPI' ? 'UPI' : 'BANK_TRANSFER',
        utrNumber: utrNumber.trim(),
        userRemarks: userRemarks || `Paid ₹${selectedPlan.monthly_price || selectedPlan.monthlyPrice} via ${selectedMethodType}`,
      };

      const res = await traderApi.requestPlanActivation(payload);
      addToast('Payment UTR submitted! Pending Admin verification for instant activation.', 'success');
      setIsPayModalOpen(false);
      loadData();
    } catch (err) {
      addToast(err.message || 'Failed to submit payment request', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const activeBank = paymentMethods.find((m) => m.methodType === 'BANK_ACCOUNT');
  const activeUpi = paymentMethods.find((m) => m.methodType === 'UPI');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Algorithmic Subscription Plans</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Choose your automated execution fleet tier. Pay zero payment fees via direct UPI or Bank IMPS/NEFT.
          </p>
        </div>

        <button onClick={loadData} disabled={loading} className="btn btn-secondary">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Status</span>
        </button>
      </div>

      {/* Current Active / Pending Status Banner */}
      {currentSub ? (
        <div
          className="glass-panel"
          style={{
            padding: '20px 24px',
            borderLeft: `5px solid ${currentSub.status === 'ACTIVE' ? 'var(--accent-emerald)' : 'var(--accent-amber)'}`,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: currentSub.status === 'ACTIVE' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                color: currentSub.status === 'ACTIVE' ? 'var(--accent-emerald)' : 'var(--accent-amber)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {currentSub.status === 'ACTIVE' ? <CheckCircle2 size={26} /> : <Clock size={26} />}
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff', margin: 0 }}>
                  {currentSub.planName || 'Plan Subscription'}
                </h3>
                <span className={`badge ${currentSub.status === 'ACTIVE' ? 'badge-running' : 'badge-pending'}`}>
                  {currentSub.status === 'ACTIVE' ? '● ACTIVE & EXECUTION UNLOCKED' : '⏳ PENDING UTR VERIFICATION'}
                </span>
              </div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '4px' }}>
                {currentSub.status === 'ACTIVE' ? (
                  <>
                    Valid Until:{' '}
                    <strong style={{ color: '#fff' }}>
                      {currentSub.endDate ? new Date(currentSub.endDate).toLocaleDateString('en-IN') : 'Ongoing'}
                    </strong>{' '}
                    • 5m Candle Automated Order Routing Active
                  </>
                ) : (
                  <>
                    Submitted UTR: <strong className="font-mono" style={{ color: 'var(--accent-amber)' }}>{currentSub.utrNumber || 'Verified in Progress'}</strong> • Admin is verifying the transaction.
                  </>
                )}
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div
          className="glass-panel"
          style={{
            padding: '16px 20px',
            borderLeft: '4px solid var(--accent-amber)',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <AlertCircle size={20} color="var(--accent-amber)" />
          <span style={{ fontSize: '0.9rem', color: 'var(--text-main)' }}>
            <strong>No active plan:</strong> Strategy execution is currently locked. Select a tier below and submit your payment UTR for instant activation.
          </span>
        </div>
      )}

      {/* Plans Tier Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
        {plans.map((p) => {
          const price = p.monthly_price || p.monthlyPrice || 0;
          const isCurrentActive = currentSub?.status === 'ACTIVE' && currentSub?.planId === p.id;
          const isPending = currentSub?.status === 'PENDING_APPROVAL' && currentSub?.planId === p.id;

          return (
            <div
              key={p.id}
              className="glass-panel"
              style={{
                padding: '30px 24px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                border: isCurrentActive
                  ? '2px solid var(--accent-emerald)'
                  : isPending
                  ? '2px solid var(--accent-amber)'
                  : '1px solid var(--border-subtle)',
                position: 'relative',
              }}
            >
              {p.code === 'PRO_SCALPER' || p.code === 'PRO' ? (
                <span
                  style={{
                    position: 'absolute',
                    top: '-12px',
                    right: '24px',
                    background: 'var(--accent-cyan)',
                    color: '#000',
                    fontSize: '0.7rem',
                    fontWeight: 800,
                    padding: '3px 10px',
                    borderRadius: '4px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                  }}
                >
                  Most Popular
                </span>
              ) : null}

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff', margin: 0 }}>{p.name}</h3>
                  <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                    #{p.code}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '14px' }}>
                  <span style={{ fontSize: '2.2rem', fontWeight: 800, color: '#fff' }}>
                    ₹{Number(price).toLocaleString('en-IN')}
                  </span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>/ month</span>
                </div>

                <p style={{ color: 'var(--text-dim)', fontSize: '0.85rem', marginTop: '8px' }}>
                  {p.description || 'Full algorithmic trading execution suite with multi-broker routing.'}
                </p>

                <div style={{ borderTop: '1px solid var(--border-subtle)', marginTop: '20px', paddingTop: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: 'var(--text-main)' }}>
                    <Check size={16} color="var(--accent-emerald)" />
                    <span>Up to {p.max_concurrent_strategies || 5} Concurrent Live Strategies</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: 'var(--text-main)' }}>
                    <Check size={16} color="var(--accent-emerald)" />
                    <span>5m Candle High-Frequency Trigger Engine</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: 'var(--text-main)' }}>
                    <Check size={16} color="var(--accent-emerald)" />
                    <span>Dhan Broker Live & Paper Trading</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.85rem', color: 'var(--text-main)' }}>
                    <Check size={16} color="var(--accent-emerald)" />
                    <span>Real-time Order Fills & Audit Tracing</span>
                  </div>
                </div>
              </div>

              <div style={{ marginTop: '28px' }}>
                {isCurrentActive ? (
                  <button disabled className="btn btn-secondary" style={{ width: '100%', justifyContent: 'center', opacity: 0.8 }}>
                    <CheckCircle2 size={16} color="var(--accent-emerald)" />
                    <span>Current Active Plan</span>
                  </button>
                ) : isPending ? (
                  <button disabled className="btn btn-secondary" style={{ width: '100%', justifyContent: 'center', border: '1px solid var(--accent-amber)' }}>
                    <Clock size={16} color="var(--accent-amber)" />
                    <span>Verification Pending</span>
                  </button>
                ) : (
                  <button
                    onClick={() => handleOpenPay(p)}
                    className="btn btn-primary"
                    style={{ width: '100%', justifyContent: 'center', padding: '12px' }}
                  >
                    <QrCode size={16} />
                    <span>Subscribe via UPI / Bank</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Payment & UTR Submission Modal */}
      <Modal isOpen={isPayModalOpen} onClose={() => setIsPayModalOpen(false)} title="💳 Pay via UPI or Bank IMPS / NEFT">
        <form onSubmit={handleSubmitPayment} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          {/* Selected Plan Summary Banner */}
          <div style={{ background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.3)', padding: '14px 18px', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>SELECTED TIER</div>
              <div style={{ fontWeight: 800, fontSize: '1.1rem', color: '#fff' }}>{selectedPlan?.name}</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>PAYABLE AMOUNT</div>
              <div style={{ fontWeight: 800, fontSize: '1.25rem', color: 'var(--accent-emerald)' }}>
                ₹{Number(selectedPlan?.monthly_price || selectedPlan?.monthlyPrice || 0).toLocaleString('en-IN')}
              </div>
            </div>
          </div>

          {/* Payment Method Selector Tabs */}
          <div>
            <label style={{ marginBottom: '8px', display: 'block' }}>Choose Payment Option:</label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setSelectedMethodType('UPI')}
                className={`btn ${selectedMethodType === 'UPI' ? 'btn-emerald' : 'btn-secondary'}`}
                style={{ justifyContent: 'center', padding: '10px' }}
              >
                <QrCode size={16} />
                <span>Instant UPI / QR</span>
              </button>

              <button
                type="button"
                onClick={() => setSelectedMethodType('BANK_ACCOUNT')}
                className={`btn ${selectedMethodType === 'BANK_ACCOUNT' ? 'btn-primary' : 'btn-secondary'}`}
                style={{ justifyContent: 'center', padding: '10px' }}
              >
                <Building2 size={16} />
                <span>Bank IMPS / NEFT</span>
              </button>
            </div>
          </div>

          {/* Payment Details Card */}
          <div style={{ background: 'rgba(0, 0, 0, 0.5)', border: '1px solid var(--border-subtle)', borderRadius: '8px', padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {selectedMethodType === 'UPI' ? (
              <>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Scan with GPay, PhonePe, Paytm or BHIM UPI:
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(16, 185, 129, 0.1)', padding: '10px 14px', borderRadius: '6px', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>UPI VPA ID</div>
                    <strong className="font-mono" style={{ color: 'var(--accent-emerald)', fontSize: '1.05rem' }}>
                      {activeUpi?.upiId || 'zenalgo.tech@okhdfcbank'}
                    </strong>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleCopyText(activeUpi?.upiId || 'zenalgo.tech@okhdfcbank', 'UPI ID')}
                    className="btn btn-secondary"
                    style={{ padding: '6px 10px', fontSize: '0.75rem' }}
                  >
                    <Copy size={12} />
                    <span>Copy</span>
                  </button>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                  Recipient Name: <strong>{activeUpi?.accountHolderName || 'ZenAlgo Technologies Pvt Ltd'}</strong>
                </div>
              </>
            ) : (
              <>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Transfer via NetBanking / IMPS to Current Account:
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.85rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Bank:</span>
                    <strong style={{ color: '#fff' }}>{activeBank?.bankName || 'HDFC Bank Ltd'}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Account No:</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <strong className="font-mono" style={{ color: 'var(--accent-cyan)' }}>
                        {activeBank?.accountNumber || '50200084920194'}
                      </strong>
                      <button
                        type="button"
                        onClick={() => handleCopyText(activeBank?.accountNumber || '50200084920194', 'Account No')}
                        style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}
                      >
                        <Copy size={12} />
                      </button>
                    </div>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>IFSC Code:</span>
                    <strong className="font-mono" style={{ color: 'var(--accent-amber)' }}>
                      {activeBank?.ifscCode || 'HDFC0001234'}
                    </strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Holder:</span>
                    <strong style={{ color: '#fff', fontSize: '0.8rem' }}>
                      {activeBank?.accountHolderName || 'ZENALGO TECHNOLOGIES PRIVATE LIMITED'}
                    </strong>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* UTR Input */}
          <div>
            <label>
              <strong>12-Digit Transaction Reference (UTR) Number *</strong>
            </label>
            <input
              type="text"
              value={utrNumber}
              onChange={(e) => setUtrNumber(e.target.value.trim())}
              className="input-field font-mono"
              placeholder="e.g. 423910294819 or UTR-2026-9921"
              required
              style={{ fontSize: '1rem', letterSpacing: '0.05em' }}
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px', display: 'block' }}>
              Found in your UPI app payment receipt or bank debit SMS.
            </span>
          </div>

          <div>
            <label>Payment Remarks / Sender App (Optional)</label>
            <input
              type="text"
              value={userRemarks}
              onChange={(e) => setUserRemarks(e.target.value)}
              className="input-field"
              placeholder="e.g. Sent via Google Pay / Aditya Axis Bank"
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button type="button" onClick={() => setIsPayModalOpen(false)} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="btn btn-emerald" style={{ padding: '10px 24px' }}>
              {submitting ? 'Submitting UTR...' : 'Submit Payment for Approval'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default MySubscriptionPage;
