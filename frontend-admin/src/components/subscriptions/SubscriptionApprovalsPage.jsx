import React, { useState, useEffect } from 'react';
import {
  Wallet,
  CheckCircle2,
  XCircle,
  Clock,
  RefreshCw,
  Search,
  DollarSign,
  Users,
  ShieldCheck,
  Building2,
  QrCode,
  FileText,
  ArrowRight,
} from 'lucide-react';
import { paymentApi } from '../../api/paymentApi';
import { Modal } from '../common/Modal';
import { useToast } from '../../context/ToastContext';

export const SubscriptionApprovalsPage = () => {
  const { addToast } = useToast();
  const [pendingRequests, setPendingRequests] = useState([]);
  const [walletLedger, setWalletLedger] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);

  // Approval Modal State
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [isApproveModalOpen, setIsApproveModalOpen] = useState(false);
  const [isRejectModalOpen, setIsRejectModalOpen] = useState(false);
  const [adminNotes, setAdminNotes] = useState('Verified in Bank/UPI Statement. Funds received.');
  const [rejectReason, setRejectReason] = useState('UTR number not found in bank statement.');

  const loadData = async () => {
    setLoading(true);
    try {
      const [resPending, resLedger] = await Promise.all([
        paymentApi.getPendingSubscriptionRequests(),
        paymentApi.getPlanWalletLedger(),
      ]);
      setPendingRequests(resPending.data || []);
      setWalletLedger(resLedger.data);
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to load subscription approvals', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleOpenApprove = (req) => {
    setSelectedRequest(req);
    setAdminNotes(`Verified in Bank/UPI statement for ₹${Number(req.totalAmount).toLocaleString('en-IN')}.`);
    setIsApproveModalOpen(true);
  };

  const handleOpenReject = (req) => {
    setSelectedRequest(req);
    setRejectReason(`UTR ${req.utrNumber} could not be verified in the bank account.`);
    setIsRejectModalOpen(true);
  };

  const handleConfirmApprove = async () => {
    if (!selectedRequest) return;
    setActionLoading(selectedRequest.paymentId);
    try {
      await paymentApi.approveSubscription(selectedRequest.paymentId, adminNotes);
      addToast(`Plan for ${selectedRequest.userEmail} approved & activated! Revenue added to Admin Plan Wallet.`, 'success');
      setIsApproveModalOpen(false);
      loadData();
    } catch (err) {
      addToast(err.message || 'Approval failed', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleConfirmReject = async () => {
    if (!selectedRequest) return;
    setActionLoading(selectedRequest.paymentId);
    try {
      await paymentApi.rejectSubscription(selectedRequest.paymentId, rejectReason);
      addToast(`Subscription request #${selectedRequest.paymentId} rejected.`, 'warning');
      setIsRejectModalOpen(false);
      loadData();
    } catch (err) {
      addToast(err.message || 'Rejection failed', 'error');
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Plan Purchase Approvals & Admin Plan Wallet</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Manually verify client UPI/Bank UTRs, approve plan activations, and audit revenue collection.
          </p>
        </div>

        <button onClick={loadData} disabled={loading} className="btn btn-secondary">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Queue & Ledger</span>
        </button>
      </div>

      {/* Hero Plan Wallet KPI Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
        
        {/* Total Collected Revenue */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-emerald)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>ADMIN PLAN WALLET BALANCE</span>
            <Wallet size={18} color="var(--accent-emerald)" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--accent-emerald)', marginTop: '8px' }}>
            ₹{Number(walletLedger?.totalRevenue || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            ● Verified institutional subscription revenue
          </div>
        </div>

        {/* Pending Approval Revenue */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-amber)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>PENDING VERIFICATION</span>
            <Clock size={18} color="var(--accent-amber)" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--accent-amber)', marginTop: '8px' }}>
            ₹{Number(walletLedger?.pendingRevenue || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            {pendingRequests.length} Pending Client Requests in Queue
          </div>
        </div>

        {/* Active Subscribers */}
        <div className="glass-panel" style={{ padding: '20px', borderLeft: '4px solid var(--accent-cyan)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <span>ACTIVE PAID SUBSCRIBERS</span>
            <Users size={18} color="var(--accent-cyan)" />
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff', marginTop: '8px' }}>
            {walletLedger?.activeSubscribersCount || 0} <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>Traders</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', marginTop: '4px' }}>
            ● Plan active & strategy execution unlocked
          </div>
        </div>
      </div>

      {/* Section 1: Pending Requests Verification Queue */}
      <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={18} color="var(--accent-amber)" />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
              Pending Plan Purchase Requests ({pendingRequests.length})
            </h3>
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Match UTR against bank account / UPI statement
          </span>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Request ID</th>
                <th>Client User</th>
                <th>Purchased Plan</th>
                <th>Total Amount</th>
                <th>Payment Mode</th>
                <th>Submitted UTR / Ref No</th>
                <th>User Remarks</th>
                <th>Requested At</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="9" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    Loading pending requests...
                  </td>
                </tr>
              ) : pendingRequests.length === 0 ? (
                <tr>
                  <td colSpan="9" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    ✓ No pending requests in queue. All client payments are verified!
                  </td>
                </tr>
              ) : (
                pendingRequests.map((req) => (
                  <tr key={req.paymentId}>
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>
                      #{req.paymentId}
                    </td>
                    <td>
                      <strong style={{ color: '#fff' }}>{req.userName}</strong>
                      <div className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                        {req.userEmail} (User #{req.userId})
                      </div>
                    </td>
                    <td>
                      <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.15)', color: 'var(--accent-purple)' }}>
                        {req.planName}
                      </span>
                    </td>
                    <td>
                      <strong style={{ color: 'var(--accent-emerald)', fontSize: '0.95rem' }}>
                        ₹{Number(req.totalAmount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </strong>
                    </td>
                    <td>
                      <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)' }}>
                        {req.paymentMode}
                      </span>
                    </td>
                    <td>
                      <code className="font-mono" style={{ color: 'var(--accent-amber)', fontWeight: 800, fontSize: '0.9rem', background: 'rgba(245, 158, 11, 0.1)', padding: '3px 6px', borderRadius: '4px', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                        {req.utrNumber}
                      </code>
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)', maxWidth: '200px' }}>
                      {req.userRemarks || '—'}
                    </td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                      {new Date(req.requestedAt).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button
                          onClick={() => handleOpenApprove(req)}
                          disabled={actionLoading === req.paymentId}
                          className="btn btn-emerald"
                          style={{ padding: '6px 12px', fontSize: '0.75rem' }}
                        >
                          <CheckCircle2 size={14} />
                          <span>Approve</span>
                        </button>
                        <button
                          onClick={() => handleOpenReject(req)}
                          disabled={actionLoading === req.paymentId}
                          className="btn btn-danger"
                          style={{ padding: '6px 10px', fontSize: '0.75rem' }}
                        >
                          <XCircle size={14} />
                          <span>Reject</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Section 2: Admin Plan Revenue Financial Ledger */}
      <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={18} color="var(--accent-cyan)" />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
              Admin Plan Wallet Revenue Ledger
            </h3>
          </div>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Dual-entry audit trail linking client payments to Admin Plan Wallet
          </span>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Tx ID</th>
                <th>Client Source</th>
                <th>Plan Name</th>
                <th>Revenue Credited</th>
                <th>UTR Reference</th>
                <th>Verified By</th>
                <th>Approved Date</th>
                <th>Ledger Status</th>
              </tr>
            </thead>
            <tbody>
              {!walletLedger?.ledger || walletLedger.ledger.length === 0 ? (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    No approved revenue records yet.
                  </td>
                </tr>
              ) : (
                walletLedger.ledger.map((item) => (
                  <tr key={item.id}>
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)' }}>#TX-{item.id}</td>
                    <td>
                      <strong style={{ color: '#fff' }}>{item.userName}</strong>
                      <div className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                        {item.userEmail} (User #{item.userId})
                      </div>
                    </td>
                    <td>
                      <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.15)', color: 'var(--accent-purple)' }}>
                        {item.planName}
                      </span>
                    </td>
                    <td>
                      <strong style={{ color: 'var(--accent-emerald)', fontSize: '0.95rem' }}>
                        +₹{Number(item.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </strong>
                    </td>
                    <td className="font-mono" style={{ color: 'var(--accent-amber)', fontSize: '0.85rem' }}>
                      {item.utrNumber}
                    </td>
                    <td>
                      <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)' }}>
                        {item.approvedBy}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                      {new Date(item.approvedAt).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })}
                    </td>
                    <td>
                      <span className="badge badge-active">
                        ● CREDITED TO PLAN WALLET
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Approve Modal */}
      <Modal isOpen={isApproveModalOpen} onClose={() => setIsApproveModalOpen(false)} title="✓ Approve & Activate Plan Subscription">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '14px', borderRadius: '8px' }}>
            <div style={{ fontWeight: 700, color: '#fff' }}>Confirming Payment Verification:</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              • User: <strong>{selectedRequest?.userEmail}</strong><br />
              • Plan: <strong>{selectedRequest?.planName}</strong><br />
              • Amount: <strong style={{ color: 'var(--accent-emerald)' }}>₹{Number(selectedRequest?.totalAmount || 0).toLocaleString('en-IN')}</strong><br />
              • UTR Number: <strong className="font-mono" style={{ color: 'var(--accent-amber)' }}>{selectedRequest?.utrNumber}</strong>
            </div>
          </div>

          <div>
            <label>Admin Verification Notes (Optional)</label>
            <input
              type="text"
              value={adminNotes}
              onChange={(e) => setAdminNotes(e.target.value)}
              className="input-field"
              placeholder="e.g. Verified in HDFC bank statement"
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
            <button onClick={() => setIsApproveModalOpen(false)} className="btn btn-secondary">
              Cancel
            </button>
            <button onClick={handleConfirmApprove} disabled={actionLoading} className="btn btn-emerald" style={{ padding: '10px 24px' }}>
              {actionLoading ? 'Activating...' : 'Confirm & Activate Plan'}
            </button>
          </div>
        </div>
      </Modal>

      {/* Reject Modal */}
      <Modal isOpen={isRejectModalOpen} onClose={() => setIsRejectModalOpen(false)} title="✗ Reject Subscription Payment Request">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.3)', padding: '14px', borderRadius: '8px' }}>
            <div style={{ fontWeight: 700, color: '#fff' }}>Rejecting Request #{selectedRequest?.paymentId}:</div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              User will be notified to double check with their bank or provide a valid UTR number.
            </div>
          </div>

          <div>
            <label>Reason for Rejection</label>
            <input
              type="text"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              className="input-field"
              required
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
            <button onClick={() => setIsRejectModalOpen(false)} className="btn btn-secondary">
              Cancel
            </button>
            <button onClick={handleConfirmReject} disabled={actionLoading} className="btn btn-danger" style={{ padding: '10px 24px' }}>
              {actionLoading ? 'Rejecting...' : 'Confirm Rejection'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default SubscriptionApprovalsPage;
