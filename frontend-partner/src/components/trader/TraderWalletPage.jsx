import React, { useState, useEffect } from 'react';
import { Wallet, Plus, ArrowUpRight, ArrowDownLeft, RefreshCw, DollarSign, Shield } from 'lucide-react';
import { traderApi } from '../../api/traderApi';
import { Modal } from '../common/Modal';
import { useToast } from '../../context/ToastContext';

export const TraderWalletPage = () => {
  const { addToast } = useToast();
  const [wallet, setWallet] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [depositAmount, setDepositAmount] = useState('25000');
  const [depositing, setDepositing] = useState(false);

  const loadWallet = async () => {
    setLoading(true);
    try {
      const [resWallet, resTx] = await Promise.all([
        traderApi.getWallet(),
        traderApi.getWalletTransactions(),
      ]);
      setWallet(resWallet.data);
      setTransactions(resTx.data || []);
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to load wallet data', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWallet();
  }, []);

  const handleDeposit = async (e) => {
    e.preventDefault();
    const num = Number(depositAmount);
    if (!num || num <= 0) return;

    setDepositing(true);
    try {
      await traderApi.depositMargin(num);
      addToast(`₹${num.toLocaleString('en-IN')} added to trading margin successfully!`, 'success');
      setIsModalOpen(false);
      loadWallet();
    } catch (err) {
      addToast(err.message || 'Deposit failed', 'error');
    } finally {
      setDepositing(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Trading Wallet & Margin</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Manage available trading capital, margin allocations, and deposits.
          </p>
        </div>

        <button onClick={() => setIsModalOpen(true)} className="btn btn-emerald" style={{ padding: '10px 20px' }}>
          <Plus size={16} />
          <span>Add Margin / Deposit</span>
        </button>
      </div>

      {/* Hero Margin Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        <div className="glass-panel" style={{ padding: '24px', borderLeft: '4px solid var(--accent-emerald)' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>AVAILABLE TRADING MARGIN</div>
          <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '6px' }}>
            ₹{Number(wallet?.availableMargin || 95000).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '6px' }}>
            Locked in Active Positions: ₹{Number(wallet?.lockedMargin || 5000).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '24px', borderLeft: '4px solid var(--accent-cyan)' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>TOTAL WALLET BALANCE</div>
          <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#fff', marginTop: '6px' }}>
            ₹{Number(wallet?.totalBalance || 100000).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', marginTop: '6px' }}>
            ● 100% Margin Backed Instant Execution
          </div>
        </div>
      </div>

      {/* Transaction History Table */}
      <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', margin: 0 }}>Transaction History Ledger</h3>
          <button onClick={loadWallet} disabled={loading} className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.75rem' }}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Reference ID</th>
                <th>Type</th>
                <th>Amount (₹)</th>
                <th>Remarks</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {transactions.length === 0 ? (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    No transactions recorded. Click "Add Margin / Deposit" to test!
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => (
                  <tr key={tx.id}>
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)' }}>{tx.referenceId}</td>
                    <td>
                      <span className={`badge ${tx.type === 'DEPOSIT' ? 'badge-active' : 'badge-pending'}`}>
                        {tx.type}
                      </span>
                    </td>
                    <td>
                      <strong style={{ color: tx.type === 'DEPOSIT' ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                        {tx.type === 'DEPOSIT' ? '+' : '-'}₹{Number(tx.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </strong>
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{tx.remarks}</td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                      {new Date(tx.createdAt).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Deposit Modal */}
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="💳 Add Margin / Deposit Funds">
        <form onSubmit={handleDeposit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label>Deposit Amount (₹)</label>
            <input
              type="number"
              value={depositAmount}
              onChange={(e) => setDepositAmount(e.target.value)}
              className="input-field font-mono"
              placeholder="e.g. 50000"
              required
            />
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            {['10000', '25000', '50000', '100000'].map((val) => (
              <button
                key={val}
                type="button"
                onClick={() => setDepositAmount(val)}
                className="btn btn-secondary"
                style={{ flex: 1, padding: '6px', fontSize: '0.75rem' }}
              >
                +₹{Number(val).toLocaleString('en-IN')}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
            <button type="button" onClick={() => setIsModalOpen(false)} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={depositing} className="btn btn-emerald" style={{ padding: '10px 24px' }}>
              {depositing ? 'Processing...' : 'Confirm Deposit'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default TraderWalletPage;
