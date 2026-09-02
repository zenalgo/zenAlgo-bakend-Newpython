import React, { useState, useEffect } from 'react';
import { Building2, QrCode, Plus, RefreshCw, CheckCircle2, XCircle, Trash2, Edit2, Shield, ArrowRight } from 'lucide-react';
import { paymentApi } from '../../api/paymentApi';
import { Modal } from '../common/Modal';
import { useToast } from '../../context/ToastContext';

export const PaymentSettingsPage = () => {
  const { addToast } = useToast();
  const [methods, setMethods] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);

  // Form State
  const [methodType, setMethodType] = useState('BANK_ACCOUNT'); // 'BANK_ACCOUNT' | 'UPI'
  const [title, setTitle] = useState('');
  const [bankName, setBankName] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [ifscCode, setIfscCode] = useState('');
  const [accountHolderName, setAccountHolderName] = useState('ZENALGO TECHNOLOGIES PRIVATE LIMITED');
  const [upiId, setUpiId] = useState('');
  const [displayOrder, setDisplayOrder] = useState(1);
  const [submitting, setSubmitting] = useState(false);

  const loadMethods = async () => {
    setLoading(true);
    try {
      const res = await paymentApi.getPaymentMethods();
      setMethods(res.data || []);
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to load payment methods', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMethods();
  }, []);

  const handleOpenAdd = (type = 'BANK_ACCOUNT') => {
    setEditingId(null);
    setMethodType(type);
    if (type === 'BANK_ACCOUNT') {
      setTitle('Institutional Current Account (HDFC Bank)');
      setBankName('HDFC Bank Ltd');
      setAccountNumber('');
      setIfscCode('HDFC0001234');
      setAccountHolderName('ZENALGO TECHNOLOGIES PRIVATE LIMITED');
      setUpiId('');
    } else {
      setTitle('ZenAlgo Instant QR & UPI Gateway');
      setBankName('');
      setAccountNumber('');
      setIfscCode('');
      setAccountHolderName('ZenAlgo Technologies Pvt Ltd');
      setUpiId('zenalgo.tech@okhdfcbank');
    }
    setIsModalOpen(true);
  };

  const handleToggleStatus = async (id, currentStatus) => {
    try {
      await paymentApi.togglePaymentMethodStatus(id, !currentStatus);
      addToast(`Payment account marked as ${!currentStatus ? 'ACTIVE' : 'INACTIVE'}!`, 'success');
      loadMethods();
    } catch (err) {
      addToast(err.message || 'Failed to toggle status', 'error');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this payment method?')) return;
    try {
      await paymentApi.deletePaymentMethod(id);
      addToast('Payment method removed successfully', 'success');
      loadMethods();
    } catch (err) {
      addToast(err.message || 'Failed to delete payment method', 'error');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const payload = {
        methodType,
        title,
        bankName: methodType === 'BANK_ACCOUNT' ? bankName : null,
        accountNumber: methodType === 'BANK_ACCOUNT' ? accountNumber : null,
        ifscCode: methodType === 'BANK_ACCOUNT' ? ifscCode : null,
        accountHolderName,
        upiId: methodType === 'UPI' ? upiId : null,
        isActive: true,
        displayOrder: Number(displayOrder),
      };

      if (editingId) {
        await paymentApi.updatePaymentMethod(editingId, payload);
        addToast('Payment method updated successfully!', 'success');
      } else {
        await paymentApi.createPaymentMethod(payload);
        addToast('New payment account registered successfully!', 'success');
      }
      setIsModalOpen(false);
      loadMethods();
    } catch (err) {
      addToast(err.message || 'Submission failed', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Bank & UPI Payment Settings</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Configure institutional bank accounts and UPI IDs displayed to clients for zero-fee plan payments.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={loadMethods} disabled={loading} className="btn btn-secondary">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>

          <button onClick={() => handleOpenAdd('BANK_ACCOUNT')} className="btn btn-primary">
            <Building2 size={16} />
            <span>+ Add Bank Account</span>
          </button>

          <button onClick={() => handleOpenAdd('UPI')} className="btn btn-emerald">
            <QrCode size={16} />
            <span>+ Add UPI ID</span>
          </button>
        </div>
      </div>

      {/* Methods Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '20px' }}>
        {methods.map((m) => {
          const isBank = m.methodType === 'BANK_ACCOUNT';
          return (
            <div
              key={m.id}
              className="glass-panel"
              style={{
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '16px',
                borderLeft: `4px solid ${m.isActive ? (isBank ? 'var(--accent-cyan)' : 'var(--accent-emerald)') : 'var(--text-dim)'}`,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div
                    style={{
                      width: '42px',
                      height: '42px',
                      borderRadius: '8px',
                      background: isBank ? 'rgba(56, 189, 248, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                      color: isBank ? 'var(--accent-cyan)' : 'var(--accent-emerald)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {isBank ? <Building2 size={22} /> : <QrCode size={22} />}
                  </div>
                  <div>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#fff', margin: 0 }}>{m.title}</h3>
                    <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                      #{m.id} • {m.methodType}
                    </span>
                  </div>
                </div>

                <span className={`badge ${m.isActive ? 'badge-running' : 'badge-failed'}`}>
                  {m.isActive ? 'ACTIVE IN PORTAL' : 'INACTIVE'}
                </span>
              </div>

              {/* Details Box */}
              <div style={{ background: 'rgba(0, 0, 0, 0.4)', padding: '14px 16px', borderRadius: '8px', border: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.85rem' }}>
                {isBank ? (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Bank Name:</span>
                      <strong style={{ color: '#fff' }}>{m.bankName}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Account Number:</span>
                      <strong className="font-mono" style={{ color: 'var(--accent-cyan)' }}>{m.accountNumber}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>IFSC Code:</span>
                      <strong className="font-mono" style={{ color: 'var(--accent-amber)' }}>{m.ifscCode}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Account Holder:</span>
                      <strong style={{ color: '#fff', fontSize: '0.8rem' }}>{m.accountHolderName}</strong>
                    </div>
                  </>
                ) : (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>UPI VPA ID:</span>
                      <strong className="font-mono" style={{ color: 'var(--accent-emerald)' }}>{m.upiId}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Display Name:</span>
                      <strong style={{ color: '#fff' }}>{m.accountHolderName}</strong>
                    </div>
                  </>
                )}
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: '14px' }}>
                <button
                  onClick={() => handleToggleStatus(m.id, m.isActive)}
                  className={`btn ${m.isActive ? 'btn-secondary' : 'btn-emerald'}`}
                  style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                >
                  {m.isActive ? 'Disable' : 'Enable in Portal'}
                </button>

                <button
                  onClick={() => handleDelete(m.id)}
                  className="btn btn-danger"
                  style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                >
                  <Trash2 size={14} />
                  <span>Delete</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Add / Edit Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title={editingId ? 'Edit Payment Method' : `Register New ${methodType === 'BANK_ACCOUNT' ? 'Bank Account' : 'UPI Gateway'}`}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label>Display Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="input-field"
              placeholder="e.g. Primary HDFC Current Account"
              required
            />
          </div>

          <div>
            <label>Account Holder / Business Name</label>
            <input
              type="text"
              value={accountHolderName}
              onChange={(e) => setAccountHolderName(e.target.value)}
              className="input-field"
              required
            />
          </div>

          {methodType === 'BANK_ACCOUNT' ? (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label>Bank Name</label>
                  <input
                    type="text"
                    value={bankName}
                    onChange={(e) => setBankName(e.target.value)}
                    className="input-field"
                    placeholder="e.g. HDFC Bank Ltd"
                    required
                  />
                </div>

                <div>
                  <label>Bank IFSC Code</label>
                  <input
                    type="text"
                    value={ifscCode}
                    onChange={(e) => setIfscCode(e.target.value.toUpperCase())}
                    className="input-field font-mono"
                    placeholder="e.g. HDFC0001234"
                    required
                  />
                </div>
              </div>

              <div>
                <label>Account Number</label>
                <input
                  type="text"
                  value={accountNumber}
                  onChange={(e) => setAccountNumber(e.target.value)}
                  className="input-field font-mono"
                  placeholder="e.g. 50200084920194"
                  required
                />
              </div>
            </>
          ) : (
            <div>
              <label>UPI VPA ID</label>
              <input
                type="text"
                value={upiId}
                onChange={(e) => setUpiId(e.target.value)}
                className="input-field font-mono"
                placeholder="e.g. zenalgo.tech@okhdfcbank"
                required
              />
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button type="button" onClick={() => setIsModalOpen(false)} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="btn btn-primary" style={{ padding: '10px 24px' }}>
              {submitting ? 'Saving...' : 'Save Account'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default PaymentSettingsPage;
