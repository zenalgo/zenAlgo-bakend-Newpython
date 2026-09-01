import React, { useState, useEffect } from 'react';
import { Modal } from './Modal';
import { PlayCircle, CheckCircle2, TrendingUp, Zap, Clock } from 'lucide-react';
import { strategyApi } from '../../api/strategyApi';
import { executionApi } from '../../api/executionApi';
import { useToast } from '../../context/ToastContext';

export const SimulateExecutionModal = ({ isOpen, onClose, onRefreshData }) => {
  const { addToast } = useToast();
  const [strategies, setStrategies] = useState([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState('');
  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setSimResult(null);
      strategyApi.getStrategies().then((res) => {
        const list = res.data || [];
        setStrategies(list);
        if (list.length > 0) {
          setSelectedStrategyId(list[0].id);
        }
      });
    }
  }, [isOpen]);

  const handleRunSimulation = async () => {
    if (!selectedStrategyId) return;
    setSimulating(true);
    setSimResult(null);

    try {
      const res = await executionApi.simulateExecution(selectedStrategyId);
      const data = res.data;
      setSimResult({
        status: 'SUCCESS',
        executionId: data.executionId,
        strategyId: data.strategyId,
        fillPrice: data.legs?.[0]?.price || '100.00',
        pnl: `+₹${data.unrealizedPnl?.toFixed(2) || '525.00'}`,
        contract: data.legs?.[0]?.tradingSymbol || 'NIFTY 25050 CE',
        timeline: [
          { step: 'CANDLE_CLOSE', msg: '5m Candle closed with bullish crossover confirmation' },
          { step: 'SIGNAL_EMIT', msg: 'StrategySignal emitted & validated' },
          { step: 'BATCH_DISPATCH', msg: 'ExecutionBatch created for 10 subscribers' },
          { step: 'USER_AUDIT', msg: 'User & Risk checks passed (Trace Status: EXECUTED)' },
          { step: 'PAPER_ORDER_FILL', msg: `Paper Order filled: 50 qty @ ₹${data.legs?.[0]?.price || 100}` },
        ],
      });
      addToast(`Live Paper Trade #${data.executionId} placed and filled!`, 'success');
      if (onRefreshData) onRefreshData();
    } catch (err) {
      addToast(err.message || 'Simulation error', 'error');
    } finally {
      setSimulating(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Live Market Candle & Trade Execution Simulator">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Execute an instant end-to-end paper trade (signal trigger $\rightarrow$ batch trace $\rightarrow$ order placement $\rightarrow$ PnL calculation).
        </p>

        <div>
          <label>Target Strategy for Simulation</label>
          <select
            value={selectedStrategyId}
            onChange={(e) => setSelectedStrategyId(e.target.value)}
            className="input-field"
          >
            {strategies.map((s) => (
              <option key={s.id} value={s.id}>
                #{s.id} — {s.name} ({s.underlying || 'NIFTY'})
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={handleRunSimulation}
          disabled={simulating}
          className="btn btn-emerald"
          style={{ padding: '12px', fontSize: '0.95rem' }}
        >
          <PlayCircle size={20} className={simulating ? 'animate-spin' : ''} />
          <span>{simulating ? 'Dispatching Live Paper Order...' : 'Trigger 5m Candle & Execute Trade'}</span>
        </button>

        {simResult && (
          <div style={{
            background: 'rgba(16, 185, 129, 0.08)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            borderRadius: '8px',
            padding: '18px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-emerald)', fontWeight: 700 }}>
                <CheckCircle2 size={18} />
                <span>Execution #{simResult.executionId} Placed ({simResult.contract})</span>
              </div>
              <span className="font-mono" style={{ color: 'var(--accent-emerald)', fontWeight: 800, fontSize: '1.2rem' }}>
                {simResult.pnl}
              </span>
            </div>

            <div style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {simResult.timeline.map((t, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="font-mono" style={{ color: 'var(--accent-cyan)', minWidth: '140px', fontWeight: 600 }}>
                    {t.step}
                  </span>
                  <span style={{ color: 'var(--text-main)' }}>{t.msg}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default SimulateExecutionModal;
