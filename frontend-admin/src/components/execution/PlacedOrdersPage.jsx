import React, { useState, useEffect } from 'react';
import { StatusBadge } from '../common/StatusBadge';
import { Package, RefreshCw, Square, CheckCircle, TrendingUp, AlertCircle } from 'lucide-react';
import { executionApi } from '../../api/executionApi';
import { strategyApi } from '../../api/strategyApi';
import { useToast } from '../../context/ToastContext';

export const PlacedOrdersPage = ({ selectedStrategyId }) => {
  const { addToast } = useToast();
  const [strategies, setStrategies] = useState([]);
  const [currentStrategyId, setCurrentStrategyId] = useState(selectedStrategyId || '');
  const [placedOrders, setPlacedOrders] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    strategyApi.getStrategies().then((res) => {
      const list = res.data || [];
      setStrategies(list);
      if (!currentStrategyId && list.length > 0) {
        setCurrentStrategyId(list[0].id);
      }
    });
  }, []);

  const loadOrders = async () => {
    if (!currentStrategyId) return;
    setLoading(true);
    try {
      const res = await executionApi.getPlacedOrders(currentStrategyId);
      setPlacedOrders(res.data || []);
    } catch (err) {
      console.error(err);
      addToast('Failed to load placed orders', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (currentStrategyId) {
      loadOrders();
    }
  }, [currentStrategyId]);

  const handleSquareOff = async () => {
    if (!currentStrategyId) return;
    if (!window.confirm('Are you sure you want to trigger market square-off for this strategy?')) return;
    try {
      await strategyApi.squareOff(currentStrategyId);
      addToast('Square-off orders dispatched!', 'success');
      loadOrders();
    } catch (err) {
      addToast(err.message || 'Square-off failed', 'error');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Placed Orders & Open Paper Positions</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Real-time execution ledger, contract legs, fill prices, and live PnL.</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={loadOrders} disabled={loading} className="btn btn-secondary">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            <span>Refresh Fills</span>
          </button>
          <button onClick={handleSquareOff} className="btn btn-danger">
            <Square size={16} />
            <span>Square Off Positions</span>
          </button>
        </div>
      </div>

      {/* Strategy Selector Toolbar */}
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', gap: '16px' }}>
        <label style={{ margin: 0, whiteSpace: 'nowrap' }}>Active Strategy:</label>
        <select
          value={currentStrategyId}
          onChange={(e) => setCurrentStrategyId(e.target.value)}
          className="input-field"
          style={{ maxWidth: '400px' }}
        >
          {strategies.map((s) => (
            <option key={s.id} value={s.id}>
              #{s.id} — {s.name} ({s.underlying || 'NIFTY'}) [{s.mode || 'PAPER'}]
            </option>
          ))}
        </select>
      </div>

      {/* Orders Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Execution ID</th>
                <th>Strategy & User</th>
                <th>Mode</th>
                <th>Status</th>
                <th>Filled Trade Legs</th>
                <th>Realized / Live PnL</th>
                <th>Entry Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {placedOrders.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    No placed orders recorded for this strategy yet.
                    <div style={{ marginTop: '8px', fontSize: '0.8rem' }}>
                      Click <strong>"Simulate 5m Candle & Execution"</strong> on top to execute an instant paper trade!
                    </div>
                  </td>
                </tr>
              ) : (
                placedOrders.map((order) => (
                  <tr key={order.executionId}>
                    <td className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 700 }}>
                      #{order.executionId}
                    </td>
                    <td>
                      <div style={{ fontWeight: 600 }}>Strategy #{order.strategyId}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Subscriber User: #{order.userId}</div>
                    </td>
                    <td><StatusBadge status={order.mode || 'PAPER'} /></td>
                    <td><StatusBadge status={order.status || 'RUNNING'} /></td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {(order.legs || []).map((l, idx) => (
                          <div key={idx} style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span className="font-mono" style={{ color: 'var(--accent-emerald)', fontWeight: 600 }}>
                              {l.tradingSymbol || 'NIFTY 25050 CE'}
                            </span>
                            <span style={{ color: 'var(--text-muted)' }}>
                              • Fill: ₹{l.price || '100.00'} (Qty: {l.filledQuantity}/{l.quantity})
                            </span>
                          </div>
                        ))}
                      </div>
                    </td>
                    <td>
                      <div style={{ fontWeight: 700, color: order.unrealizedPnl >= 0 ? 'var(--accent-emerald)' : 'var(--accent-rose)' }}>
                        {order.unrealizedPnl >= 0 ? `+₹${order.unrealizedPnl.toFixed(2)}` : `₹${order.unrealizedPnl.toFixed(2)}`}
                      </div>
                    </td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {new Date(order.entryTime).toLocaleTimeString()}
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

export default PlacedOrdersPage;
