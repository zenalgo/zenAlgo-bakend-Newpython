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
      'EMA 8 is above EMA 33 for bullish setup',
      'EMA 8 is below EMA 33 for bearish setup',
      'Price pulls back toward EMA 33',
      'Strong bullish candle confirmation for CALL',
      'Strong bearish candle confirmation for PUT',
      'CALL entry when confirmation candle high breaks',
      'PUT entry when confirmation candle low breaks',
    ],
    exitConditions: [
      'Stop loss is hit',
      'Target of 2R is hit',
      'EMA 8 crosses to the opposite side of EMA 33',
      'Forced exit at 15:15',
    ],
    youtubeUrl: '',
    keyPoints: [
      'Use 5-minute NIFTY chart',
      'EMA 8 is the fast EMA',
      'EMA 33 is the slow EMA',
      'Trade in the direction of the EMA trend',
      'Wait for a pullback',
      'Do not chase extended candles',
      'Enter only after confirmation candle breakout',
    ],
    status: 'ACTIVE_LIVE',
    config: {
      timing: {
        entryFrom: '09:30',
        entryTo: '14:30',
        entryTimeMode: 'Time Window',
        forcedExitTime: '15:15',
        exitTimeMode: 'End of Session',
        entryDays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
        exitDays: ['Wed'],
        weeklyCycleScope: 'SAME_WEEK',
        maxHoldingPeriod: 'Same Day',
      },
      entry: {
        logic: 'ALL (AND)',
        timeframeMode: 'Same as Entry Timeframe',
        marketFilters: ['Avoid first 15 minutes', 'Avoid highly volatile conditions'],
      },
      exit: {
        logic: 'ANY (OR)',
        partialExit: { enabled: true, plan: 'Book 50% at 1R and trail remaining 50% using EMA 8' },
        trailingStop: { enabled: true, rule: 'Trail after 1R using EMA 8' },
      },
      riskManagement: {
        riskRewardRatio: '1:2',
        stopLoss: { value: 'Below confirmation candle low for CALL / above confirmation candle high for PUT' },
        maxLossPerTrade: '₹2500',
        maxLossPerDay: '₹5000',
        maxLossPerWeek: '₹15000',
        maxTradesPerDay: '3',
        maxOpenPositions: '1',
        consecutiveLossLimit: '3',
        cooldownMinutes: '15',
        positionSizingMode: 'Risk Based',
        afterLossAction: 'Reduce Size',
        capitalAllocationPerTrade: '5%',
      },
      options: {
        optionType: 'Auto',
        strikeSelection: 'ATM',
        strikeOffset: '0',
        expiry: 'Current Weekly',
        legs: [{ action: 'BUY', type: 'CE', strike: 'ATM', expiry: 'Current Weekly', quantity: '1' }],
      },
      execution: {
        orderType: 'Market',
        triggerType: 'Candle Close',
        slippage: '0.10%',
        orderTimeout: '30',
        reentry: { mode: 'After New Setup', maxReentries: '1' },
      },
      target: {
        value: '2R',
        scaleOutPlan: 'Book 50% at 1R and trail remaining 50% using EMA 8',
      },
    },
  },
  RSI_MOMENTUM: {
    id: `STRAT-RSI-${Math.floor(100000 + Math.random() * 900000)}`,
    name: 'NIFTY RSI 60 Alert Candle',
    author: 'Ankur',
    description: 'Intraday NIFTY options buying strategy using RSI 60 momentum confirmation and alert-candle breakout.',
    category: 'Option Buying - Index',
    marketBias: 'NEUTRAL_BOTH',
    strategyStyle: 'Momentum',
    tradingHorizon: 'Intraday',
    instrumentType: 'Options',
    underlying: 'NIFTY 50',
    indicesArray: ['NIFTY 50'],
    entryTimeframe: '15m',
    expiryType: 'Weekly',
    coreIdea: 'When RSI crosses above 60, mark the alert candle and buy CE when its high breaks. For bearish conditions, use the opposite setup for PE.',
    riskReward: '1:2',
    stopLoss: 'Alert candle low for CE / alert candle high for PE',
    maxLossTrade: '₹2500',
    maxLossDay: '₹5000',
    target: 'Alert Candle Range',
    entryConditions: [
      'RSI crosses above 60 for bullish setup',
      'Mark the candle responsible for the RSI 60 breakout as the alert candle',
      'Wait for alert candle high to break',
      'Buy CE on break of alert candle high',
      'RSI crosses below bearish threshold for bearish setup',
      'Mark the bearish alert candle',
      'Buy PE on break of alert candle low',
    ],
    exitConditions: [
      'Stop loss is hit',
      'Alert candle range target is hit',
      'Forced exit at 15:15',
    ],
    youtubeUrl: '',
    keyPoints: [
      'Use 15-minute NIFTY chart',
      'RSI is used as the momentum trigger',
      'Bullish RSI trigger is above 60',
      'Use the alert candle created by the RSI trigger',
      'Do not enter immediately on RSI crossover',
      'Wait for alert candle breakout',
      'Use CE for bullish breakout',
      'Use PE for bearish breakout',
    ],
    status: 'ACTIVE_LIVE',
    config: {
      timing: {
        entryFrom: '09:30',
        entryTo: '14:30',
        entryTimeMode: 'Time Window',
        forcedExitTime: '15:15',
        exitTimeMode: 'End of Session',
        entryDays: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
        exitDays: ['Wed'],
        weeklyCycleScope: 'SAME_WEEK',
        maxHoldingPeriod: 'Same Day',
      },
      entry: {
        logic: 'ALL (AND)',
        timeframeMode: 'Same as Entry Timeframe',
        marketFilters: ['Avoid first 15 minutes', 'Avoid highly volatile conditions'],
      },
      exit: {
        logic: 'ANY (OR)',
        partialExit: { enabled: true, plan: 'Book partial profit at first target and trail remaining position' },
        trailingStop: { enabled: true, rule: 'Trail after first target' },
      },
      riskManagement: {
        riskRewardRatio: '1:2',
        stopLoss: { value: 'Alert candle low for CE / alert candle high for PE' },
        maxLossPerTrade: '₹2500',
        maxLossPerDay: '₹5000',
        maxLossPerWeek: '₹15000',
        maxTradesPerDay: '3',
        maxOpenPositions: '1',
        consecutiveLossLimit: '3',
        cooldownMinutes: '15',
        positionSizingMode: 'Risk Based',
        afterLossAction: 'Reduce Size',
        capitalAllocationPerTrade: '5%',
      },
      options: {
        optionType: 'Auto',
        strikeSelection: 'ATM',
        strikeOffset: '0',
        expiry: 'Current Weekly',
        legs: [{ action: 'BUY', type: 'CE', strike: 'ATM', expiry: 'Current Weekly', quantity: '1' }],
      },
      execution: {
        orderType: 'Market',
        triggerType: 'Candle Close',
        slippage: '0.10%',
        orderTimeout: '30',
        reentry: { mode: 'After New Setup', maxReentries: '1' },
      },
      target: {
        value: 'Alert Candle Range',
        scaleOutPlan: 'Partial profit followed by trailing stop',
      },
    },
  },
  RELIANCE_PIVOT: {
    id: `STRAT-REL-${Math.floor(100000 + Math.random() * 900000)}`,
    name: 'Reliance S3/R3 Pivot Reversal',
    author: 'Ankur',
    description: 'Monthly Camarilla pivot reversal strategy for Reliance using R3 and S3 with mandatory 200-point option hedging.',
    category: 'Stock Option Selling',
    marketBias: 'NEUTRAL_BOTH',
    strategyStyle: 'Mean Reversion',
    tradingHorizon: 'Monthly',
    instrumentType: 'Options',
    underlying: 'RELIANCE',
    indicesArray: ['RELIANCE'],
    entryTimeframe: '15m',
    expiryType: 'Monthly',
    coreIdea: 'Monitor Monthly Camarilla R3 and S3 levels. Sell CE after a fake breakout at R3 and sell PE after a fake breakdown at S3. Always hedge the short option approximately 200 points away.',
    riskReward: '',
    stopLoss: 'Strategy invalidation above R3 for CE setup / below S3 for PE setup',
    maxLossTrade: '',
    maxLossDay: '',
    target: '2% - 3%',
    entryConditions: [
      'Monitor Monthly Camarilla R3 and S3',
      'R3 setup: Reliance touches R3 and closes back below R3',
      'Sell CE after bearish confirmation at R3',
      'Buy CE hedge approximately 200 points away',
      'S3 setup: Reliance drops to S3 and closes back above S3',
      'Sell PE after bullish confirmation at S3',
      'Buy PE hedge approximately 200 points away',
    ],
    exitConditions: [
      'Target profit of approximately 2% to 3% is achieved',
      'Monthly expiry is approaching',
      'Defined risk limit is reached',
      'Exit short option and corresponding hedge together',
    ],
    youtubeUrl: '',
    keyPoints: [
      'Underlying is RELIANCE',
      'Pivot calculation is Camarilla',
      'Pivot periodicity is Monthly',
      'Only R3 and S3 are monitored',
      'Always hedge the short option 200 points away',
      'Primary objective is theta decay',
    ],
    status: 'ACTIVE_LIVE',
    config: {
      timing: {
        entryFrom: '09:30',
        forcedExitTime: '15:15',
        entryTimeMode: 'Signal Based',
        exitTimeMode: 'Exact Time',
        maxHoldingPeriod: 'Until Monthly Expiry',
      },
      entry: {
        logic: 'ALL (AND)',
        timeframeMode: 'Signal Based',
        marketFilters: ['Do not trade during quarterly earnings-result months'],
      },
      exit: {
        logic: 'ANY (OR)',
        partialExit: { enabled: false, plan: '' },
        trailingStop: { enabled: false, rule: '' },
      },
      riskManagement: {
        riskRewardRatio: '',
        stopLoss: { value: 'Strategy invalidation above R3 for CE setup / below S3 for PE setup' },
        maxLossPerTrade: '',
        maxLossPerDay: '',
        maxLossPerWeek: '',
        maxTradesPerDay: '1',
        maxOpenPositions: '1',
        consecutiveLossLimit: '2',
        cooldownMinutes: '0',
        positionSizingMode: 'Fixed Lots',
        afterLossAction: 'Stop Strategy',
      },
      options: {
        optionType: 'Both',
        strikeSelection: 'Custom',
        strikeOffset: '200',
        expiry: 'Current Monthly',
        legs: [
          { action: 'SELL', type: 'CE', strike: 'Selected OTM CE', expiry: 'Current Monthly', quantity: '1' },
          { action: 'BUY', type: 'CE', strike: 'Short CE strike + 200 points', expiry: 'Current Monthly', quantity: '1' },
          { action: 'SELL', type: 'PE', strike: 'Selected OTM PE', expiry: 'Current Monthly', quantity: '1' },
          { action: 'BUY', type: 'PE', strike: 'Short PE strike - 200 points', expiry: 'Current Monthly', quantity: '1' },
        ],
      },
      execution: {
        orderType: 'Limit',
        triggerType: 'Candle Close',
        slippage: '0.20%',
        orderTimeout: '30',
        reentry: { mode: 'After New Setup', maxReentries: '0' },
      },
      target: {
        value: '2% - 3%',
        scaleOutPlan: 'Exit full strategy position when target is achieved or monthly expiry approaches',
      },
    },
  },
};

export const StrategyBuilderPage = ({ onNavigate }) => {
  const { addToast } = useToast();
  const [activeTab, setActiveTab] = useState('FORM'); // 'FORM' or 'JSON'
  const [loading, setLoading] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiGenerating, setAiGenerating] = useState(false);

  // Core Form State (initialized to EMA_PULLBACK template)
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

  // AI Prompt Generator
  const handleAiGenerate = async () => {
    if (!aiPrompt.trim()) {
      addToast('Please enter a description for the AI generator', 'warning');
      return;
    }
    setAiGenerating(true);
    try {
      const res = await strategyApi.generateStrategyAI(aiPrompt);
      if (res.data) {
        const d = res.data;
        updateStrat({
          name: d.name || stratState.name,
          description: d.description || stratState.description,
          underlying: d.underlying || stratState.underlying,
          entryTimeframe: d.timeframe || stratState.entryTimeframe,
        });
        addToast('AI generated strategy schema successfully!', 'success');
      }
    } catch (err) {
      addToast(err.message || 'AI Generation synced with smart defaults', 'info');
      updateStrat({
        name: 'AI Generated Trend Strategy',
        description: aiPrompt,
      });
    } finally {
      setAiGenerating(false);
    }
  };

  // Leg Management
  const addLeg = () => {
    const curLegs = stratState.config?.options?.legs || [];
    const newLegs = [...curLegs, { action: 'BUY', type: 'CE', strike: 'ATM', expiry: 'Current Weekly', quantity: '1' }];
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
    updateStrat({ entryConditions: [...cur, 'New entry rule condition'] });
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
    updateStrat({ exitConditions: [...cur, 'New exit target condition'] });
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

  // Submit Handler
  const handleSaveStrategy = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);

    let finalPayload;
    try {
      if (activeTab === 'JSON') {
        finalPayload = JSON.parse(jsonText);
      } else {
        finalPayload = stratState;
      }
    } catch (err) {
      addToast('Invalid JSON syntax: ' + err.message, 'error');
      setLoading(false);
      return;
    }

    try {
      const res = await strategyApi.createStrategy(finalPayload);
      addToast(`Strategy "${finalPayload.name}" saved! ID: #${res.data?.id || 'NEW'}`, 'success');
      onNavigate('strategies');
    } catch (err) {
      addToast(err.message || 'Failed to create strategy', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Header & Mode Switcher */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fff' }}>Institutional Strategy Builder</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
            Full Schema v2.0.0 with dual persistence, multi-leg hedging, and risk controls.
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

      {/* 1-Click Institutional Presets Bar */}
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', background: 'rgba(56, 189, 248, 0.04)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Bookmark size={18} color="var(--accent-cyan)" />
          <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-main)' }}>1-Click Production Templates:</span>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button onClick={() => handleLoadPreset('EMA_PULLBACK')} className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.75rem' }}>
            📈 8/33 EMA Pullback (NIFTY 5m)
          </button>
          <button onClick={() => handleLoadPreset('RSI_MOMENTUM')} className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.75rem' }}>
            ⚡ RSI 60 Alert Candle (NIFTY 15m)
          </button>
          <button onClick={() => handleLoadPreset('RELIANCE_PIVOT')} className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.75rem' }}>
            🛡️ Reliance Camarilla 200pt Hedged
          </button>
        </div>
      </div>

      {/* AI Strategy Generator Bar */}
      <div className="glass-panel" style={{ padding: '18px 20px', border: '1px solid rgba(168, 85, 247, 0.4)', background: 'rgba(168, 85, 247, 0.05)' }}>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <Sparkles size={20} color="var(--accent-purple)" />
          <input
            type="text"
            placeholder="AI Strategy Prompt: e.g. '5m EMA 8/33 trend pullback strategy with 2R target and forced exit at 15:15'..."
            value={aiPrompt}
            onChange={(e) => setAiPrompt(e.target.value)}
            className="input-field"
          />
          <button
            onClick={handleAiGenerate}
            disabled={aiGenerating}
            className="btn"
            style={{ background: 'var(--accent-purple)', color: '#fff', whiteSpace: 'nowrap' }}
          >
            <Sparkles size={16} />
            <span>{aiGenerating ? 'Generating...' : 'AI Generate'}</span>
          </button>
        </div>
      </div>

      {activeTab === 'JSON' ? (
        /* Raw JSON Editor Tab */
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>JSON Payload Editor</h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Direct payload matching curl / API contract</span>
          </div>
          <textarea
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            className="input-field font-mono"
            rows="24"
            style={{ fontSize: '0.85rem', lineHeight: '1.5' }}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
            <button type="button" onClick={() => onNavigate('strategies')} className="btn btn-secondary">Cancel</button>
            <button onClick={handleSaveStrategy} disabled={loading} className="btn btn-primary" style={{ padding: '10px 24px' }}>
              <CheckCircle size={18} />
              <span>{loading ? 'Submitting...' : 'Save & Provision Strategy'}</span>
            </button>
          </div>
        </div>
      ) : (
        /* Visual Form Tab */
        <form onSubmit={handleSaveStrategy} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* 1. General & Classification */}
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>
              1. General Strategy & Market Classification
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
              <div>
                <label>Strategy ID</label>
                <input type="text" value={stratState.id || ''} onChange={(e) => updateStrat({ id: e.target.value })} className="input-field font-mono" />
              </div>
              <div>
                <label>Strategy Name</label>
                <input type="text" value={stratState.name} onChange={(e) => updateStrat({ name: e.target.value })} className="input-field" required />
              </div>
              <div>
                <label>Author</label>
                <input type="text" value={stratState.author} onChange={(e) => updateStrat({ author: e.target.value })} className="input-field" />
              </div>
              <div>
                <label>Category</label>
                <select value={stratState.category} onChange={(e) => updateStrat({ category: e.target.value })} className="input-field">
                  <option value="Option Buying - Index">Option Buying - Index</option>
                  <option value="Stock Option Selling">Stock Option Selling</option>
                  <option value="Equity Intraday">Equity Intraday</option>
                  <option value="Futures Trend">Futures Trend</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              <div>
                <label>Underlying Asset</label>
                <select value={stratState.underlying} onChange={(e) => updateStrat({ underlying: e.target.value, indicesArray: [e.target.value] })} className="input-field">
                  <option value="NIFTY 50">NIFTY 50</option>
                  <option value="BANKNIFTY">BANKNIFTY</option>
                  <option value="FINNIFTY">FINNIFTY</option>
                  <option value="RELIANCE">RELIANCE</option>
                  <option value="HDFCBANK">HDFCBANK</option>
                </select>
              </div>
              <div>
                <label>Entry Timeframe</label>
                <select value={stratState.entryTimeframe} onChange={(e) => updateStrat({ entryTimeframe: e.target.value })} className="input-field">
                  <option value="1m">1 Minute</option>
                  <option value="5m">5 Minutes</option>
                  <option value="15m">15 Minutes</option>
                  <option value="1d">Daily (1D)</option>
                </select>
              </div>
              <div>
                <label>Market Bias</label>
                <select value={stratState.marketBias} onChange={(e) => updateStrat({ marketBias: e.target.value })} className="input-field">
                  <option value="NEUTRAL_BOTH">NEUTRAL_BOTH (CE & PE)</option>
                  <option value="BULLISH">BULLISH ONLY</option>
                  <option value="BEARISH">BEARISH ONLY</option>
                </select>
              </div>
              <div>
                <label>Expiry Horizon</label>
                <select value={stratState.expiryType} onChange={(e) => updateStrat({ expiryType: e.target.value })} className="input-field">
                  <option value="Weekly">Weekly Expiry</option>
                  <option value="Monthly">Monthly Expiry</option>
                </select>
              </div>
            </div>

            <div>
              <label>Strategy Description</label>
              <textarea value={stratState.description} onChange={(e) => updateStrat({ description: e.target.value })} className="input-field" rows="2" />
            </div>

            <div>
              <label>Core Idea & Edge</label>
              <textarea value={stratState.coreIdea} onChange={(e) => updateStrat({ coreIdea: e.target.value })} className="input-field" rows="2" />
            </div>
          </div>

          {/* 2. Multi-Leg Options Construction & Hedging */}
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff' }}>
                2. Multi-Leg Options Construction & Strike Offsets
              </h3>
              <button type="button" onClick={addLeg} className="btn btn-secondary" style={{ fontSize: '0.75rem', padding: '4px 10px' }}>
                <Plus size={14} />
                <span>Add Leg</span>
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {(stratState.config?.options?.legs || []).map((leg, idx) => (
                <div key={idx} style={{
                  display: 'grid',
                  gridTemplateColumns: '110px 100px 1fr 140px 80px 40px',
                  gap: '12px',
                  alignItems: 'center',
                  background: 'var(--bg-input)',
                  padding: '12px 16px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-subtle)',
                }}>
                  <div>
                    <label style={{ fontSize: '0.7rem' }}>Action</label>
                    <select value={leg.action} onChange={(e) => updateLeg(idx, 'action', e.target.value)} className="input-field">
                      <option value="BUY">BUY</option>
                      <option value="SELL">SELL</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.7rem' }}>Option</label>
                    <select value={leg.type} onChange={(e) => updateLeg(idx, 'type', e.target.value)} className="input-field">
                      <option value="CE">CALL (CE)</option>
                      <option value="PE">PUT (PE)</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.7rem' }}>Strike / Offset Expression</label>
                    <input type="text" value={leg.strike} onChange={(e) => updateLeg(idx, 'strike', e.target.value)} className="input-field" />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.7rem' }}>Expiry Scope</label>
                    <select value={leg.expiry} onChange={(e) => updateLeg(idx, 'expiry', e.target.value)} className="input-field">
                      <option value="Current Weekly">Current Weekly</option>
                      <option value="Current Monthly">Current Monthly</option>
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: '0.7rem' }}>Quantity</label>
                    <input type="text" value={leg.quantity} onChange={(e) => updateLeg(idx, 'quantity', e.target.value)} className="input-field" />
                  </div>
                  <button
                    type="button"
                    onClick={() => removeLeg(idx)}
                    style={{ background: 'transparent', border: 'none', color: 'var(--accent-rose)', cursor: 'pointer', marginTop: '16px' }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* 3. Entry & Exit Rules */}
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>
              3. Entry Conditions & Exit Targets
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              {/* Entry Conditions List */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <label style={{ margin: 0 }}>Entry Conditions ({stratState.entryConditions?.length || 0})</label>
                  <button type="button" onClick={addEntryCondition} className="btn btn-secondary" style={{ padding: '2px 8px', fontSize: '0.7rem' }}>+ Add</button>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {(stratState.entryConditions || []).map((cond, idx) => (
                    <div key={idx} style={{ display: 'flex', gap: '6px' }}>
                      <input type="text" value={cond} onChange={(e) => updateEntryCondition(idx, e.target.value)} className="input-field" style={{ fontSize: '0.8rem' }} />
                      <button type="button" onClick={() => removeEntryCondition(idx)} style={{ background: 'transparent', border: 'none', color: 'var(--accent-rose)', cursor: 'pointer' }}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Exit Conditions List */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <label style={{ margin: 0 }}>Exit Conditions ({stratState.exitConditions?.length || 0})</label>
                  <button type="button" onClick={addExitCondition} className="btn btn-secondary" style={{ padding: '2px 8px', fontSize: '0.7rem' }}>+ Add</button>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {(stratState.exitConditions || []).map((cond, idx) => (
                    <div key={idx} style={{ display: 'flex', gap: '6px' }}>
                      <input type="text" value={cond} onChange={(e) => updateExitCondition(idx, e.target.value)} className="input-field" style={{ fontSize: '0.8rem' }} />
                      <button type="button" onClick={() => removeExitCondition(idx)} style={{ background: 'transparent', border: 'none', color: 'var(--accent-rose)', cursor: 'pointer' }}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* 4. Risk Management & Timing */}
          <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>
              4. Institutional Risk Controls & Timing Windows
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              <div>
                <label>Target Profit</label>
                <input type="text" value={stratState.target} onChange={(e) => updateStrat({ target: e.target.value })} className="input-field" />
              </div>
              <div>
                <label>Stop Loss Invalidation</label>
                <input type="text" value={stratState.stopLoss} onChange={(e) => updateStrat({ stopLoss: e.target.value })} className="input-field" />
              </div>
              <div>
                <label>Max Loss / Trade</label>
                <input type="text" value={stratState.maxLossTrade} onChange={(e) => updateStrat({ maxLossTrade: e.target.value })} className="input-field" />
              </div>
              <div>
                <label>Max Loss / Day</label>
                <input type="text" value={stratState.maxLossDay} onChange={(e) => updateStrat({ maxLossDay: e.target.value })} className="input-field" />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
              <div>
                <label>Entry Window Start</label>
                <input
                  type="text"
                  value={stratState.config?.timing?.entryFrom || '09:30'}
                  onChange={(e) => updateConfig('timing', { entryFrom: e.target.value })}
                  className="input-field"
                />
              </div>
              <div>
                <label>Entry Window End</label>
                <input
                  type="text"
                  value={stratState.config?.timing?.entryTo || '14:30'}
                  onChange={(e) => updateConfig('timing', { entryTo: e.target.value })}
                  className="input-field"
                />
              </div>
              <div>
                <label>Forced Exit Cutoff Time</label>
                <input
                  type="text"
                  value={stratState.config?.timing?.forcedExitTime || '15:15'}
                  onChange={(e) => updateConfig('timing', { forcedExitTime: e.target.value })}
                  className="input-field"
                />
              </div>
              <div>
                <label>Max Trades Per Day</label>
                <input
                  type="text"
                  value={stratState.config?.riskManagement?.maxTradesPerDay || '3'}
                  onChange={(e) => updateConfig('riskManagement', { maxTradesPerDay: e.target.value })}
                  className="input-field"
                />
              </div>
            </div>
          </div>

          {/* Form Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
            <button type="button" onClick={() => onNavigate('strategies')} className="btn btn-secondary">Cancel</button>
            <button type="submit" disabled={loading} className="btn btn-primary" style={{ padding: '10px 24px' }}>
              <CheckCircle size={18} />
              <span>{loading ? 'Submitting...' : 'Save & Provision Strategy'}</span>
            </button>
          </div>
        </form>
      )}
    </div>
  );
};

export default StrategyBuilderPage;
