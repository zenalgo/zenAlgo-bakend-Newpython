import React, { useState } from 'react';
import {
  Sparkles,
  Plus,
  Trash2,
  CheckCircle,
  Code,
  Sliders,
  Clock,
  Shield,
  Layers,
  FileJson,
  Zap,
  Bookmark,
} from 'lucide-react';
import { strategyApi } from '../../api/strategyApi';
import { useToast } from '../../context/ToastContext';
import { AIStrategyGeneratorModal } from './AIStrategyGeneratorModal';

// Institutional Reference Preset Payloads
const PRESETS = {
  EMA_PULLBACK: {
    id: `STRAT-EMA-${Math.floor(100000 + Math.random() * 900000)}`,
    name: '8/33 EMA Pullback',
    author: 'Ankur',
    description: 'Intraday trend-following strategy using 8 EMA and 33 EMA.',
    category: 'Option Buying - Index',
    marketBias: 'NEUTRAL_BOTH',
    strategyStyle: 'Trend Following',
    tradingHorizon: 'Intraday',
    instrumentType: 'Options',
    underlying: 'NIFTY 50',
    indicesArray: ['NIFTY 50'],
    entryTimeframe: '5m',
    expiryType: 'Weekly',
    coreIdea: 'Trade in the direction of the EMA trend after price pulls back toward the 33 EMA and gives confirmation.',
    riskReward: '1:2',
    stopLoss: 'Below confirmation candle low for CALL / above confirmation candle high for PUT',
    maxLossTrade: '₹2500',
    maxLossDay: '₹5000',
    target: '2R',
    entryConditions: [
      'CLOSE > EMA(8, CLOSE) AND EMA(8, CLOSE) > EMA(33, CLOSE)',
      'Price pulls back toward EMA(33, CLOSE)',
      'Strong bullish candle confirmation for CALL',
    ],
    exitConditions: [
      'CLOSE < EMA(8, CLOSE) OR RSI(14, CLOSE) < 40',
      'Target of 2R is achieved',
      '15:15 intraday square off',
    ],
    youtubeUrl: '',
    keyPoints: [
      'EMA 8 and 33 are the primary trend indicators',
      'Always wait for pullback to 33 EMA',
      'Do not enter without confirmation candle',
    ],
    status: 'ACTIVE_LIVE',
    config: {
      timing: {
        entryFrom: '09:15',
        forcedExitTime: '15:15',
        entryTimeMode: 'Signal Based',
        exitTimeMode: 'Exact Time',
        maxHoldingPeriod: 'Intraday',
      },
      entry: {
        logic: 'ALL (AND)',
        timeframeMode: 'Signal Based',
        marketFilters: ['No trade before 09:20 AM'],
      },
      exit: {
        logic: 'ANY (OR)',
        partialExit: { enabled: false, plan: '' },
        trailingStop: { enabled: true, rule: 'Trail SL to cost after 1R' },
      },
      riskManagement: {
        riskRewardRatio: '1:2',
        stopLoss: { value: '30 points' },
        maxLossPerTrade: '₹2500',
        maxLossPerDay: '₹5000',
        maxLossPerWeek: '₹15000',
        maxTradesPerDay: '3',
        maxOpenPositions: '1',
        consecutiveLossLimit: '2',
        cooldownMinutes: '15',
        positionSizingMode: 'Fixed Capital',
        afterLossAction: 'Pause 30 mins',
      },
      options: {
        legs: [
          { action: 'BUY', type: 'CE', strike: 'ATM', expiry: 'Current Weekly', quantity: '50' },
        ],
      },
      target: {
        value: '60 points',
        scaleOutPlan: 'Book 50% at 1:1, trail balance',
      },
    },
  },
};

export const StrategyBuilderPage = ({ onNavigate }) => {
  const { addToast } = useToast();
  const [activeTab, setActiveTab] = useState('FORM'); // 'FORM' or 'JSON'
  const [loading, setLoading] = useState(false);
  const [isAIModalOpen, setIsAIModalOpen] = useState(false);

  // Core Form State
  const [stratState, setStratState] = useState(PRESETS.EMA_PULLBACK);
  const [jsonText, setJsonText] = useState(JSON.stringify(PRESETS.EMA_PULLBACK, null, 2));

  // Sync Form to JSON
  const updateStrat = (updates) => {
    const updated = { ...stratState, ...updates };
    setStratState(updated);
    setJsonText(JSON.stringify(updated, null, 2));
  };

  const updateConfig = (section, updates) => {
    const updated = {
      ...stratState,
      config: {
        ...stratState.config,
        [section]: {
          ...(stratState.config?.[section] || {}),
          ...updates,
        },
      },
    };
    setStratState(updated);
    setJsonText(JSON.stringify(updated, null, 2));
  };

  // Load Preset
  const handleLoadPreset = (key) => {
    const p = PRESETS[key];
    if (p) {
      setStratState(p);
      setJsonText(JSON.stringify(p, null, 2));
      addToast(`Loaded "${p.name}" preset template!`, 'info');
    }
  };

  // Auto-Fill from AI Generator
  const handleAutoFillFromAI = (aiStrat) => {
    const updated = {
      ...stratState,
      name: aiStrat.name || stratState.name,
      description: aiStrat.description || stratState.description,
      underlying: aiStrat.underlying || 'NIFTY 50',
      entryTimeframe: aiStrat.timeframe || '5m',
      entryConditions: (aiStrat.entryRules || []).length > 0 ? aiStrat.entryRules : stratState.entryConditions,
      exitConditions: (aiStrat.exitRules || []).length > 0 ? aiStrat.exitRules : stratState.exitConditions,
    };

    if (aiStrat.legs && aiStrat.legs.length > 0) {
      const mappedLegs = aiStrat.legs.map((l) => ({
        action: l.side || 'BUY',
        type: (l.positionType || '').toUpperCase() === 'CALL' ? 'CE' : 'PE',
        strike: l.strikeSelection || 'ATM',
        expiry: 'Current Weekly',
        quantity: String(l.quantity || 50),
      }));
      updated.config = {
        ...updated.config,
        options: { legs: mappedLegs },
      };
    }

    setStratState(updated);
    setJsonText(JSON.stringify(updated, null, 2));
    addToast(`AI Strategy "${aiStrat.name}" auto-filled into form!`, 'success');
  };

  // Leg Management
  const addLeg = () => {
    const curLegs = stratState.config?.options?.legs || [];
    const newLegs = [...curLegs, { action: 'BUY', type: 'CE', strike: 'ATM', expiry: 'Current Weekly', quantity: '50' }];
    updateConfig('options', { legs: newLegs });
  };

  const removeLeg = (idx) => {
    const curLegs = stratState.config?.options?.legs || [];
    const newLegs = curLegs.filter((_, i) => i !== idx);
    updateConfig('options', { legs: newLegs });
  };

  const updateLeg = (idx, field, val) => {
    const curLegs = [...(stratState.config?.options?.legs || [])];
    curLegs[idx][field] = val;
    updateConfig('options', { legs: curLegs });
  };

  // Condition Management
  const addEntryCondition = () => {
    const cur = stratState.entryConditions || [];
    updateStrat({ entryConditions: [...cur, 'CLOSE > EMA(20, CLOSE) AND RSI(14, CLOSE) > 55'] });
  };

  const removeEntryCondition = (idx) => {
    const cur = stratState.entryConditions || [];
    updateStrat({ entryConditions: cur.filter((_, i) => i !== idx) });
  };

  const updateEntryCondition = (idx, val) => {
    const cur = [...(stratState.entryConditions || [])];
    cur[idx] = val;
    updateStrat({ entryConditions: cur });
  };

  const addExitCondition = () => {
    const cur = stratState.exitConditions || [];
    updateStrat({ exitConditions: [...cur, 'CLOSE < EMA(20, CLOSE) OR RSI(14, CLOSE) < 40'] });
  };

  const removeExitCondition = (idx) => {
    const cur = stratState.exitConditions || [];
    updateStrat({ exitConditions: cur.filter((_, i) => i !== idx) });
  };

  const updateExitCondition = (idx, val) => {
    const cur = [...(stratState.exitConditions || [])];
    cur[idx] = val;
    updateStrat({ exitConditions: cur });
  };

  // Save Strategy to Backend
  const handleSaveStrategy = async () => {
    setLoading(true);
    let finalPayload;
    if (activeTab === 'JSON') {
      try {
        finalPayload = JSON.parse(jsonText);
      } catch (err) {
        addToast('Invalid JSON structure. Please check syntax.', 'error');
        setLoading(false);
        return;
      }
    } else {
      finalPayload = {
        id: stratState.id || `STRAT_${Date.now()}`,
        name: stratState.name,
        description: stratState.description,
        underlying: stratState.underlying || 'NIFTY 50',
        timeframe: stratState.entryTimeframe || '5m',
        mode: 'PAPER',
        entrySetting: {
          entryType: 'INTRADAY',
          reEntryLimit: parseInt(stratState.config?.riskManagement?.maxTradesPerDay || 3),
        },
        entryDays: ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY'],
        exitSetting: {
          exitType: 'TIME_BASED',
          exitTime: '15:15:00',
        },
        entryConditions: (stratState.entryConditions || []).map((r) => ({ rawText: r })),
        exitConditions: (stratState.exitConditions || []).map((r) => ({ rawText: r })),
        legs: (stratState.config?.options?.legs || []).map((l) => ({
          instrumentType: 'OPT',
          side: l.action || 'BUY',
          positionType: l.type === 'CE' ? 'CALL' : 'PUT',
          strikeSelection: l.strike || 'ATM',
          quantity: parseInt(l.quantity || 50),
          stopLossPoints: 30.0,
          targetPoints: 60.0,
        })),
      };
    }

    try {
      const res = await strategyApi.createStrategy(finalPayload);
      addToast(`Strategy "${finalPayload.name}" saved! ID: #${res.data?.id || 'NEW'}`, 'success');
      if (onNavigate) onNavigate('strategies');
    } catch (err) {
      addToast(err.message || 'Failed to create strategy', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Header & Mode Switcher */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Institutional Strategy Builder</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Full Schema v2.0.0 with dual persistence, multi-leg hedging, and multi-model AI synthesis.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', background: 'var(--bg-card)', padding: '4px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
          <button
            onClick={() => setActiveTab('FORM')}
            className={`btn ${activeTab === 'FORM' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '6px 14px', fontSize: '0.8rem' }}
          >
            <Sliders size={14} />
            <span>Visual Builder</span>
          </button>
          <button
            onClick={() => setActiveTab('JSON')}
            className={`btn ${activeTab === 'JSON' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '6px 14px', fontSize: '0.8rem' }}
          >
            <Code size={14} />
            <span>Raw JSON Schema</span>
          </button>
        </div>
      </div>

      {/* AI Strategy Generator Callout Banner */}
      <div className="glass-panel" style={{
        padding: '16px 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
        border: '1px solid var(--border-highlight)',
        background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(6, 182, 212, 0.08) 100%)',
        flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '38px',
            height: '38px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
          }}>
            <Sparkles size={20} />
          </div>
          <div>
            <div style={{ fontWeight: 800, color: '#fff', fontSize: '0.95rem' }}>
              Multi-Model AI Strategy Generator
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Synthesize institutional strategies with <strong>ChatGPT (GPT-4o)</strong>, <strong>Google Gemini</strong>, or <strong>Anthropic Claude</strong>.
            </div>
          </div>
        </div>

        <button
          onClick={() => setIsAIModalOpen(true)}
          className="btn btn-emerald"
          style={{
            background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
            color: '#fff',
            fontWeight: 700,
            border: 'none',
            boxShadow: '0 0 15px rgba(6, 182, 212, 0.4)',
          }}
        >
          <Sparkles size={16} />
          <span>Launch AI Generator</span>
        </button>
      </div>

      {activeTab === 'JSON' ? (
        /* Raw JSON Editor Tab */
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>JSON Payload Editor</h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Direct payload matching API contract</span>
          </div>
          <textarea
            rows={22}
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            className="input-field font-mono"
            style={{ fontSize: '0.85rem', lineHeight: '1.4' }}
          />
        </div>
      ) : (
        /* Visual Form Builder Tab */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Strategy Identity Card */}
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
              1. Strategy Identity & Core Edge
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
              <div>
                <label>Strategy Name</label>
                <input
                  type="text"
                  value={stratState.name}
                  onChange={(e) => updateStrat({ name: e.target.value })}
                  className="input-field"
                  placeholder="e.g. 8/33 EMA Pullback Scalper"
                />
              </div>

              <div>
                <label>Underlying Instrument</label>
                <select
                  value={stratState.underlying}
                  onChange={(e) => updateStrat({ underlying: e.target.value })}
                  className="input-field"
                >
                  <option value="NIFTY 50">NIFTY 50</option>
                  <option value="BANKNIFTY">BANKNIFTY</option>
                  <option value="FINNIFTY">FINNIFTY</option>
                  <option value="SENSEX">SENSEX</option>
                </select>
              </div>

              <div>
                <label>Candle Timeframe</label>
                <select
                  value={stratState.entryTimeframe}
                  onChange={(e) => updateStrat({ entryTimeframe: e.target.value })}
                  className="input-field"
                >
                  <option value="1m">1m Candle</option>
                  <option value="3m">3m Candle</option>
                  <option value="5m">5m Candle</option>
                  <option value="15m">15m Candle</option>
                </select>
              </div>
            </div>

            <div>
              <label>Strategy Description & Edge</label>
              <input
                type="text"
                value={stratState.description}
                onChange={(e) => updateStrat({ description: e.target.value })}
                className="input-field"
                placeholder="Brief description of the trading edge..."
              />
            </div>
          </div>

          {/* Entry Rules Card */}
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
                2. Entry Conditions & Mathematical Indicator Expressions
              </h3>
              <button onClick={addEntryCondition} className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.8rem' }}>
                <Plus size={14} />
                <span>Add Rule</span>
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {(stratState.entryConditions || []).map((cond, idx) => (
                <div key={idx} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <span className="font-mono" style={{ color: 'var(--accent-cyan)', fontSize: '0.8rem', width: '20px' }}>
                    #{idx + 1}
                  </span>
                  <input
                    type="text"
                    value={cond}
                    onChange={(e) => updateEntryCondition(idx, e.target.value)}
                    className="input-field font-mono"
                    style={{ flex: 1 }}
                  />
                  <button onClick={() => removeEntryCondition(idx)} className="btn btn-danger" style={{ padding: '8px' }}>
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Exit Rules Card */}
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
                3. Exit Targets & Stop Loss Rules
              </h3>
              <button onClick={addExitCondition} className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.8rem' }}>
                <Plus size={14} />
                <span>Add Rule</span>
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {(stratState.exitConditions || []).map((cond, idx) => (
                <div key={idx} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <span className="font-mono" style={{ color: 'var(--accent-rose)', fontSize: '0.8rem', width: '20px' }}>
                    #{idx + 1}
                  </span>
                  <input
                    type="text"
                    value={cond}
                    onChange={(e) => updateExitCondition(idx, e.target.value)}
                    className="input-field font-mono"
                    style={{ flex: 1 }}
                  />
                  <button onClick={() => removeExitCondition(idx)} className="btn btn-danger" style={{ padding: '8px' }}>
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Multi-Leg Contract Setup Card */}
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
                4. Multi-Leg Trade Contracts & Strike Selection
              </h3>
              <button onClick={addLeg} className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: '0.8rem' }}>
                <Plus size={14} />
                <span>Add Leg</span>
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {(stratState.config?.options?.legs || []).map((leg, idx) => (
                <div key={idx} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr auto', gap: '10px', alignItems: 'center' }}>
                  <div>
                    <label style={{ fontSize: '0.75rem' }}>Action</label>
                    <select value={leg.action} onChange={(e) => updateLeg(idx, 'action', e.target.value)} className="input-field">
                      <option value="BUY">BUY</option>
                      <option value="SELL">SELL</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem' }}>Option Type</label>
                    <select value={leg.type} onChange={(e) => updateLeg(idx, 'type', e.target.value)} className="input-field">
                      <option value="CE">CE (Call)</option>
                      <option value="PE">PE (Put)</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem' }}>Strike</label>
                    <select value={leg.strike} onChange={(e) => updateLeg(idx, 'strike', e.target.value)} className="input-field">
                      <option value="ATM">ATM (At-The-Money)</option>
                      <option value="ITM1">ITM1</option>
                      <option value="OTM1">OTM1</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem' }}>Expiry</label>
                    <input type="text" value={leg.expiry} onChange={(e) => updateLeg(idx, 'expiry', e.target.value)} className="input-field" />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.75rem' }}>Quantity</label>
                    <input type="number" value={leg.quantity} onChange={(e) => updateLeg(idx, 'quantity', e.target.value)} className="input-field" />
                  </div>
                  <button onClick={() => removeLeg(idx)} className="btn btn-danger" style={{ padding: '8px', alignSelf: 'flex-end' }}>
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Save & Submit Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '12px' }}>
        <button onClick={() => onNavigate && onNavigate('strategies')} className="btn btn-secondary">
          Cancel
        </button>
        <button onClick={handleSaveStrategy} disabled={loading} className="btn btn-primary" style={{ padding: '10px 24px' }}>
          <CheckCircle size={16} />
          <span>{loading ? 'Validating & Saving...' : 'Save Strategy Fleet'}</span>
        </button>
      </div>

      {/* AI Strategy Generator Modal */}
      <AIStrategyGeneratorModal
        isOpen={isAIModalOpen}
        onClose={() => setIsAIModalOpen(false)}
        onStrategyCreated={() => onNavigate && onNavigate('strategies')}
        onAutoFillBuilder={handleAutoFillFromAI}
      />
    </div>
  );
};

export default StrategyBuilderPage;
