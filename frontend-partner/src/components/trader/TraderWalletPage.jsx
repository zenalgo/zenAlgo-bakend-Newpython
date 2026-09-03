import React, { useState, useEffect } from 'react';
import { Wallet, Plus, ArrowUpRight, ArrowDownLeft, RefreshCw, DollarSign, Shield } from 'lucide-react';
import { traderApi } from '../../api/traderApi';
import { brokerApi } from '../../api/brokerApi';
import { Modal } from '../common/Modal';
import { useToast } from '../../context/ToastContext';

export const TraderWalletPage = () => {
  const { addToast } = useToast();
  const [wallet, setWallet] = useState(null);
  const [dhanFunds, setDhanFunds] = useState(null);
  const [brokerSession, setBrokerSession] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [depositAmount, setDepositAmount] = useState('25000');
  const [depositing, setDepositing] = useState(false);

  const loadWallet = async () => {
    setLoading(true);
    try {
      const [resWallet, resTx, resBroker] = await Promise.all([
        traderApi.getWallet().catch(() => ({ data: null })),
        traderApi.getWalletTransactions().catch(() => ({ data: [] })),
        brokerApi.getActiveSession().catch(() => ({ data: { connected: false } })),
      ]);
      setWallet(resWallet.data || null);
      setTransactions(resTx.data || []);
      const activeBroker = resBroker?.data || null;
      setBrokerSession(activeBroker);

      if (activeBroker?.connected) {
        try {
          const fundsRes = await brokerApi.getDhanFunds();
          if (fundsRes?.data) {
            setDhanFunds(fundsRes.data);
          }
        } catch (brokerErr) {
          console.warn('Could not load Dhan funds for wallet page', brokerErr);
        }
      } else {
        setDhanFunds(null);
      }
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
            Manage available trading capital, broker margin limits, and deposits.
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
          {dhanFunds ? (
            <>
              <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '6px' }}>
                ₹{Number(dhanFunds.availableBalance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', marginTop: '6px' }}>
                ● Live Dhan Margin Balance (Utilized: ₹{Number(dhanFunds.utilizedAmount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })})
              </div>
            </>
          ) : wallet && wallet.availableMargin != null ? (
            <>
              <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '6px' }}>
                ₹{Number(wallet.availableMargin).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                Locked in Active Positions: ₹{Number(wallet.lockedMargin || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--text-dim)', marginTop: '6px' }}>
                N/A
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '6px' }}>
                No active margin data found
              </div>
            </>
          )}
        </div>

        <div className="glass-panel" style={{ padding: '24px', borderLeft: '4px solid var(--accent-cyan)' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>START OF DAY (SOD) / TOTAL LIMIT</div>
          {dhanFunds ? (
            <>
              <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#fff', marginTop: '6px' }}>
                ₹{Number(dhanFunds.sodLimit || dhanFunds.availableBalance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', marginTop: '6px' }}>
                ● Withdrawable: ₹{Number(dhanFunds.withdrawableBalance || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
            </>
          ) : wallet && wallet.totalBalance != null ? (
            <>
              <div style={{ fontSize: '2.2rem', fontWeight: 800, color: '#fff', marginTop: '6px' }}>
                ₹{Number(wallet.totalBalance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', marginTop: '6px' }}>
                ● Platform Margin Pool
              </div>
            </>
          ) : (
            <>
              <div style={{ fontSize: '2.2rem', fontWeight: 800, color: 'var(--text-dim)', marginTop: '6px' }}>
                N/A
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '6px' }}>
                Connect broker to fetch limit
              </div>
            </>
          )}
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
              {loading ? (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    Loading transactions...
                  </td>
                </tr>
              ) : transactions.length === 0 ? (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    No recorded wallet transactions found.
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => (
                  <tr key={tx.id}>
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)' }}>
                      #{tx.referenceId || tx.id}
                    </td>
                    <td>
                      <span className={`badge ${tx.type === 'DEPOSIT' ? 'badge-active' : 'badge-inactive'}`}>
                        {tx.type}
                      </span>
                    </td>
                    <td style={{ fontWeight: 700, color: tx.type === 'DEPOSIT' ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                      {tx.type === 'DEPOSIT' ? '+' : '-'}₹{Number(tx.amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td style={{ color: 'var(--text-muted)' }}>
                      {tx.remarks || 'Standard transfer'}
                    </td>
                    <td className="font-mono" style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                      {tx.createdAt ? new Date(tx.createdAt).toLocaleString('en-IN') : 'N/A'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Deposit Modal */}
      {isModalOpen && (
        <Modal title="Deposit Trading Margin" onClose={() => setIsModalOpen(false)}>
          <form onSubmit={handleDeposit} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div>
              <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '8px', display: 'block' }}>
                Select Instant Amount (₹)
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginBottom: '12px' }}>
                {['10000', '25000', '50000', '100000'].map((val) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setDepositAmount(val)}
                    className={`btn ${depositAmount === val ? 'btn-primary' : 'btn-secondary'}`}
                    style={{ padding: '8px 0', justifyContent: 'center' }}
                  >
                    ₹{Number(val).toLocaleString('en-IN')}
                  </button>
                ))}
              </div>

              <input
                type="number"
                value={depositAmount}
                onChange={(e) => setDepositAmount(e.target.value)}
                placeholder="Enter custom deposit amount"
                className="input-field font-mono"
                min="1000"
                step="1000"
                required
                style={{ width: '100%' }}
              />
            </div>

            <div style={{ background: 'rgba(56, 189, 248, 0.08)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(56, 189, 248, 0.2)', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Deposit funds directly into your instant margin allocation ledger. Instant activation.
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', paddingTop: '10px' }}>
              <button type="button" onClick={() => setIsModalOpen(false)} className="btn btn-secondary">
                Cancel
              </button>
              <button type="submit" disabled={depositing} className="btn btn-emerald">
                {depositing ? 'Processing...' : `Confirm Deposit of ₹${Number(depositAmount || 0).toLocaleString('en-IN')}`}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};

export default TraderWalletPage;
