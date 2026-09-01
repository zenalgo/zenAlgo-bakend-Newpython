import React, { useState, useEffect } from 'react';
import { FileText, RefreshCw, Filter, CheckCircle2, TrendingUp, Zap, Clock } from 'lucide-react';
import { traderApi } from '../../api/traderApi';
import { useToast } from '../../context/ToastContext';

export const TraderOrdersPage = () => {
  const { addToast } = useToast();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadOrders = async () => {
    setLoading(true);
    try {
      const res = await traderApi.getPlacedOrders();
      setOrders(res.data || []);
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to load placed orders', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOrders();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Placed Orders & Open Positions</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Real-time execution ledger, contract legs, fill prices, and live PnL.
          </p>
        </div>

        <button onClick={loadOrders} disabled={loading} className="btn btn-secondary">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Fills</span>
        </button>
      </div>

      {/* Orders Table */}
      <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Execution ID</th>
                <th>Strategy</th>
                <th>Trading Mode</th>
                <th>Filled Trade Legs</th>
                <th>Realized / Live PnL</th>
                <th>Execution Status</th>
                <th>Entry Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    Loading execution ledger...
                  </td>
                </tr>
              ) : orders.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    No placed orders recorded yet. Click "⚡ 5m Paper Trade" on any strategy in your dashboard!
                  </td>
                </tr>
              ) : (
                orders.map((o) => (
                  <tr key={o.executionId}>
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>
                      #{o.executionId}
                    </td>
                    <td>
                      <strong style={{ color: '#fff' }}>{o.strategyName}</strong>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Strategy #{o.strategyId}</div>
                    </td>
                    <td>
                      <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.15)', color: 'var(--accent-cyan)' }}>
                        {o.mode}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {(o.legs || []).map((leg, idx) => (
                          <div key={idx} style={{ fontSize: '0.8rem', display: 'flex', gap: '6px' }}>
                            <strong style={{ color: leg.side === 'BUY' ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>{leg.side}</strong>
                            <span>{leg.symbol} (Qty: {leg.quantity})</span>
                            <span className="font-mono" style={{ color: 'var(--text-dim)' }}>@ ₹{leg.price}</span>
                          </div>
                        ))}
                      </div>
                    </td>
                    <td>
                      <strong style={{ color: Number(o.pnl || 0) >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)', fontSize: '0.95rem' }}>
                        {Number(o.pnl || 0) >= 0 ? '+' : ''}₹{Number(o.pnl || 0).toFixed(2)}
                      </strong>
                    </td>
                    <td>
                      <span className={`badge ${o.status === 'FILLED' ? 'badge-active' : 'badge-pending'}`}>
                        {o.status}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
                      {new Date(o.entryTime).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default TraderOrdersPage;
