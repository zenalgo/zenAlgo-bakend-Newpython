import React, { useState, useEffect } from 'react';
import { CreditCard, ArrowDownRight, CheckCircle2, Clock, Plus, Building2, RefreshCw, AlertCircle } from 'lucide-react';
import { partnerApi } from '../../api/partnerApi';
import { Modal } from '../common/Modal';
import { useToast } from '../../context/ToastContext';

export const PayoutsPage = () => {
  const { addToast } = useToast();
  const [payouts, setPayouts] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [requesting, setRequesting] = useState(false);

  // Form State
  const [amount, setAmount] = useState('');
  const [accountName, setAccountName] = useState('Vikram Mehta');
  const [accountNumber, setAccountNumber] = useState('501004892182');
  const [ifsc, setIfsc] = useState('HDFC0001234');
  const [upi, setUpi] = useState('vikram.mehta@okhdfcbank');

  const loadData = async () => {
    setLoading(true);
    try {
      const [resPayouts, resStats] = await Promise.all([
        partnerApi.getPayouts(),
        partnerApi.getDashboardStats(),
      ]);
      setPayouts(resPayouts.data || []);
      setStats(resStats.data);
      if (resStats.data?.availablePayoutBalance) {
        setAmount(String(resStats.data.availablePayoutBalance));
      }
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to load payouts data', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRequestPayout = async (e) => {
    e.preventDefault();
    const numAmount = Number(amount);
    if (!numAmount || numAmount <= 0) {
      addToast('Please enter a valid payout amount', 'warning');
      return;
    }
    if (numAmount > Number(stats?.availablePayoutBalance || 24500)) {
      addToast('Payout amount exceeds available commission balance', 'warning');
      return;
    }

    setRequesting(true);
    try {
      const res = await partnerApi.requestPayout({
        amount: numAmount,
        accountHolderName: accountName,
        bankAccountNumber: accountNumber,
        ifscCode: ifsc,
        upiId: upi,
      });
      addToast(`Payout request for ₹${numAmount.toLocaleString('en-IN')} submitted successfully! (ID: ${res.data?.payoutId})`, 'success');
      setIsModalOpen(false);
      loadData();
    } catch (err) {
      addToast(err.message || 'Failed to submit payout request', 'error');
    } finally {
      setRequesting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Payouts & Bank Settlements</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Withdraw earned commissions directly to your linked bank account or UPI handle.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="btn btn-amber"
          style={{ padding: '10px 20px', fontSize: '0.9rem' }}
        >
          <CreditCard size={18} />
          <span>Request Instant Payout</span>
        </button>
      </div>

      {/* Hero Payout Balances Card */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
        <div className="glass-panel" style={{ padding: '24px', borderLeft: '4px solid var(--accent-amber)' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>AVAILABLE COMMISSION BALANCE</div>
          <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--accent-amber)', marginTop: '6px' }}>
            ₹{Number(stats?.availablePayoutBalance || 24500).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--accent-emerald)', marginTop: '8px' }}>
            ● Minimum withdrawal threshold: ₹1,000.00 (No TDS / Zero Gateway Deductions)
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '24px', borderLeft: '4px solid var(--accent-emerald)' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>DEFAULT SETTLEMENT ACCOUNT</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '8px' }}>
            <Building2 size={24} color="var(--accent-cyan)" />
            <div>
              <div style={{ fontWeight: 700, color: '#fff', fontSize: '0.95rem' }}>HDFC Bank Ltd (•••• 2182)</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>IFSC: HDFC0001234 • Vikram Mehta</div>
            </div>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '8px' }}>
            NEFT / IMPS settlements process within 4 to 24 hours
          </div>
        </div>
      </div>

      {/* Payout History Table */}
      <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
            Settlement & Withdrawal History
          </h3>
          <button onClick={loadData} disabled={loading} className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.75rem' }}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Payout ID</th>
                <th>Requested Amount</th>
                <th>Destination Account</th>
                <th>UTR / Reference Number</th>
                <th>Request Date</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    Loading settlement history...
                  </td>
                </tr>
              ) : payouts.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    No payout requests found yet.
                  </td>
                </tr>
              ) : (
                payouts.map((p) => (
                  <tr key={p.payoutId}>
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>{p.payoutId}</td>
                    <td>
                      <strong style={{ color: 'var(--accent-emerald)', fontSize: '1rem' }}>
                        ₹{Number(p.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </strong>
                    </td>
                    <td>{p.bankAccount}</td>
                    <td className="font-mono" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {p.utrNumber || 'PENDING_BANK_CLEARING'}
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                      {new Date(p.requestedAt).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
                    </td>
                    <td>
                      <span className={`badge ${p.status === 'COMPLETED' ? 'badge-active' : 'badge-pending'}`}>
                        {p.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Request Payout Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="🏦 Request Commission Bank Withdrawal">
        <form onSubmit={handleRequestPayout} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label>Withdrawal Amount (₹)</label>
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="input-field font-mono"
              placeholder="e.g. 24500"
              required
            />
            <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '4px' }}>
              Max Available: ₹{Number(stats?.availablePayoutBalance || 24500).toLocaleString('en-IN')}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Account Holder Name</label>
              <input
                type="text"
                value={accountName}
                onChange={(e) => setAccountName(e.target.value)}
                className="input-field"
                required
              />
            </div>

            <div>
              <label>Bank Account Number</label>
              <input
                type="text"
                value={accountNumber}
                onChange={(e) => setAccountNumber(e.target.value)}
                className="input-field font-mono"
                required
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label>Bank IFSC Code</label>
              <input
                type="text"
                value={ifsc}
                onChange={(e) => setIfsc(e.target.value)}
                className="input-field font-mono"
                required
              />
            </div>

            <div>
              <label>UPI ID (Optional)</label>
              <input
                type="text"
                value={upi}
                onChange={(e) => setUpi(e.target.value)}
                className="input-field font-mono"
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
            <button type="button" onClick={() => setIsModalOpen(false)} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={requesting} className="btn btn-amber" style={{ padding: '10px 24px' }}>
              {requesting ? 'Submitting...' : 'Confirm Withdrawal'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default PayoutsPage;
