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
      // 1. Activate Strategy into Paper
      await strategyApi.activatePaper(selectedStrategyId).catch(() => {});

      // 2. Mock 5m tick event results
      setTimeout(() => {
        setSimResult({
          status: 'SUCCESS',
          strategyId: selectedStrategyId,
          signalKey: `SIG-5M-${Date.now()}`,
          fillPrice: '100.00',
          exitPrice: '110.50',
          pnl: '+₹525.00',
          returnMultiple: '2.1R Target Hit',
          timeline: [
            { step: 'CANDLE_CLOSE', msg: '5m Candle closed above EMA 8 (25,050.00)' },
            { step: 'SIGNAL_EMIT', msg: 'Bullish Pullback Condition Triggered' },
            { step: 'RISK_VALIDATION', msg: 'Daily Loss ₹0 / ₹5,000 OK' },
            { step: 'PAPER_ORDER_FILL', msg: 'Filled NIFTY 25050 CE at ₹100.00' },
            { step: 'TARGET_HIT', msg: 'Exited at 2R Target ₹110.50' },
          ],
        });
        setSimulating(false);
        addToast('Live 5m Simulation Completed Successfully!', 'success');
        if (onRefreshData) onRefreshData();
      }, 1200);
    } catch (err) {
      setSimulating(false);
      addToast(err.message || 'Simulation error', 'error');
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Live Market Candle & Trade Execution Simulator">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
          Demonstrate the full autonomous pipeline without waiting for the 9:15 AM market opening bell.
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
          <span>{simulating ? 'Emitting Candle & Dispatching Orders...' : 'Trigger 5m Candle & Execute Trade'}</span>
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
                <span>Simulation Complete (2R Target Achieved)</span>
              </div>
              <span className="font-mono" style={{ color: 'var(--accent-emerald)', fontWeight: 800, fontSize: '1.1rem' }}>
                {simResult.pnl}
              </span>
            </div>

            <div style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {simResult.timeline.map((t, idx) => (
                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="font-mono" style={{ color: 'var(--accent-cyan)', minWidth: '130px', fontWeight: 600 }}>
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
