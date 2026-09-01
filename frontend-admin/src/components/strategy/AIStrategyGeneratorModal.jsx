import React, { useState, useEffect } from 'react';
import { Modal } from '../common/Modal';
import { Sparkles, Bot, Key, CheckCircle2, AlertTriangle, Play, Save, Eye, EyeOff, Zap, ShieldCheck, Layers, ArrowRight } from 'lucide-react';
import { strategyApi } from '../../api/strategyApi';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';

export const AIStrategyGeneratorModal = ({ isOpen, onClose, onStrategyCreated, onAutoFillBuilder }) => {
  const { user } = useAuth();
  const { addToast } = useToast();

  const [provider, setProvider] = useState('OPENAI'); // 'OPENAI' | 'GEMINI' | 'CLAUDE'
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Result state
  const [generatedStrategy, setGeneratedStrategy] = useState(null);
  const [indicatorAudit, setIndicatorAudit] = useState(null);

  // Load cached API key for the selected provider
  useEffect(() => {
    const saved = localStorage.getItem(`zenalgo_ai_key_${provider.toLowerCase()}`) || '';
    setApiKey(saved);
  }, [provider]);

  const handleSaveApiKey = (keyVal) => {
    setApiKey(keyVal);
    localStorage.setItem(`zenalgo_ai_key_${provider.toLowerCase()}`, keyVal);
  };

  const handleSelectPreset = (presetPrompt) => {
    setPrompt(presetPrompt);
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!apiKey.trim()) {
      addToast(`Please enter your ${provider} API Key (or type 'demo' / 'test' to simulate)`, 'warning');
      return;
    }
    if (!prompt.trim()) {
      addToast('Please enter a strategy idea or prompt', 'warning');
      return;
    }

    setLoading(true);
    setGeneratedStrategy(null);
    setIndicatorAudit(null);

    try {
      const res = await strategyApi.generateWithAI({
        provider,
        apiKey: apiKey.trim(),
        prompt: prompt.trim(),
      });

      const data = res.data;
      setGeneratedStrategy(data.strategy);
      setIndicatorAudit(data.indicatorAudit);
      addToast(`AI Strategy "${data.strategy.name}" generated & verified!`, 'success');
    } catch (err) {
      console.error(err);
      addToast(err.message || 'AI Strategy Generation failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveToFleet = async () => {
    if (!generatedStrategy) return;
    setSaving(true);
    try {
      const payload = {
        id: `STRAT_${Date.now()}`,
        name: generatedStrategy.name || 'AI Algorithmic Strategy',
        description: generatedStrategy.description || 'AI-generated quantitative strategy',
        underlying: generatedStrategy.underlying || 'NIFTY',
        timeframe: generatedStrategy.timeframe || '5m',
        mode: generatedStrategy.mode || 'PAPER',
        entrySetting: {
          entryType: 'INTRADAY',
          entryTime: '09:15',
          reEntryLimit: 3,
        },
        entryDays: ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY'],
        exitSetting: {
          exitType: 'TIME_BASED',
          exitTime: '15:15',
        },
        entryConditions: (generatedStrategy.entryRules || []).map((r) => ({
          rawText: r,
        })),
        exitConditions: (generatedStrategy.exitRules || []).map((r) => ({
          rawText: r,
        })),
        legs: (generatedStrategy.legs || []).map((l, idx) => ({
          sequence: idx + 1,
          segment: 'OPT',
          expiry: 'WEEKLY',
          lots: 1,
          instrumentType: 'OPT',
          side: l.side || 'BUY',
          positionType: l.positionType || 'CALL',
          strikeSelection: l.strikeSelection || 'ATM',
          quantity: l.quantity || 50,
          stopLossPoints: l.stopLossPoints || 30.0,
          targetPoints: l.targetPoints || 60.0,
        })),
      };

      const res = await strategyApi.createStrategy(payload);
      addToast(`Strategy "${payload.name}" successfully saved to Fleet!`, 'success');
      if (onStrategyCreated) {
        onStrategyCreated(res.data);
      }
      onClose();
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Failed to save strategy to fleet', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleFillBuilder = () => {
    if (!generatedStrategy) return;
    if (onAutoFillBuilder) {
      onAutoFillBuilder(generatedStrategy);
    }
    onClose();
  };

  const isAdmin = user?.role === 'SUPER_ADMIN' || user?.role === 'ADMIN';

  if (!isAdmin) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="AI Strategy Generator">
        <div style={{ textAlign: 'center', padding: '30px', color: 'var(--accent-rose)' }}>
          <AlertTriangle size={36} style={{ margin: '0 auto 12px auto' }} />
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Access Restricted</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            The AI Strategy Generator is exclusively available for <strong>Administrator</strong> and <strong>Super Administrator</strong> accounts.
          </p>
        </div>
      </Modal>
    );
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="🤖 Multi-Model AI Strategy Generator">
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxHeight: '80vh', overflowY: 'auto' }}>
        
        {/* Model Provider Switcher */}
        <div>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '8px', display: 'block' }}>
            1. Select AI Model Provider:
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
            <button
              type="button"
              onClick={() => setProvider('OPENAI')}
              style={{
                background: provider === 'OPENAI' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(15, 23, 42, 0.6)',
                border: `1px solid ${provider === 'OPENAI' ? 'var(--accent-emerald)' : 'var(--border-subtle)'}`,
                borderRadius: '8px',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer',
              }}
            >
              <span style={{ fontSize: '1.2rem' }}>🟢</span>
              <strong style={{ color: '#fff', fontSize: '0.9rem' }}>ChatGPT</strong>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>OpenAI (GPT-4o)</span>
            </button>

            <button
              type="button"
              onClick={() => setProvider('GEMINI')}
              style={{
                background: provider === 'GEMINI' ? 'rgba(56, 189, 248, 0.2)' : 'rgba(15, 23, 42, 0.6)',
                border: `1px solid ${provider === 'GEMINI' ? 'var(--accent-cyan)' : 'var(--border-subtle)'}`,
                borderRadius: '8px',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer',
              }}
            >
              <span style={{ fontSize: '1.2rem' }}>🔵</span>
              <strong style={{ color: '#fff', fontSize: '0.9rem' }}>Google Gemini</strong>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Gemini 1.5 Pro / Flash</span>
            </button>

            <button
              type="button"
              onClick={() => setProvider('CLAUDE')}
              style={{
                background: provider === 'CLAUDE' ? 'rgba(168, 85, 247, 0.2)' : 'rgba(15, 23, 42, 0.6)',
                border: `1px solid ${provider === 'CLAUDE' ? 'var(--accent-purple)' : 'var(--border-subtle)'}`,
                borderRadius: '8px',
                padding: '12px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer',
              }}
            >
              <span style={{ fontSize: '1.2rem' }}>🟣</span>
              <strong style={{ color: '#fff', fontSize: '0.9rem' }}>Anthropic Claude</strong>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Claude 3.5 Sonnet</span>
            </button>
          </div>
        </div>

        {/* API Key Input */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
            <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', margin: 0 }}>
              2. {provider} API Key:
            </label>
            <span style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
              🔒 Stored locally in your browser
            </span>
          </div>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <input
              type={showApiKey ? 'text' : 'password'}
              placeholder={`Enter your ${provider} API Key (or type 'test' / 'demo' to simulate)...`}
              value={apiKey}
              onChange={(e) => handleSaveApiKey(e.target.value)}
              className="input-field font-mono"
              style={{ paddingRight: '40px' }}
            />
            <button
              type="button"
              onClick={() => setShowApiKey(!showApiKey)}
              style={{
                position: 'absolute',
                right: '10px',
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
              }}
            >
              {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>

        {/* Prompt Input & Quick Presets */}
        <div>
          <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
            3. Plain-English Strategy Idea / Indicator Logic:
          </label>
          <textarea
            rows={3}
            placeholder="e.g. Generate a 5m NIFTY momentum breakout strategy that enters when Close crosses above 20 EMA and RSI > 55, buying ATM Calls with 30-point stop loss and 60-point target."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="input-field"
            style={{ resize: 'vertical' }}
          />

          {/* Quick Presets */}
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', alignSelf: 'center' }}>Quick Presets:</span>
            <button
              type="button"
              onClick={() => handleSelectPreset('Create a 5m NIFTY trend-following breakout strategy using 20 EMA crossover and RSI(14) > 55 filter with ATM Call buy, 30-pt stop loss and 60-pt target.')}
              className="btn btn-secondary"
              style={{ padding: '3px 8px', fontSize: '0.75rem' }}
            >
              ⚡ 5m EMA + RSI Scalper
            </button>
            <button
              type="button"
              onClick={() => handleSelectPreset('Create a 15m BANKNIFTY Supertrend(10,3) options buyer with ATR(14) volatility filter, 50-pt stop loss and 120-pt target.')}
              className="btn btn-secondary"
              style={{ padding: '3px 8px', fontSize: '0.75rem' }}
            >
              📊 15m Supertrend Breakout
            </button>
            <button
              type="button"
              onClick={() => handleSelectPreset('Create a 5m FINNIFTY golden breakout strategy with candle closure above 20 EMA and MACD bullish crossover, 25-pt stop and 50-pt target.')}
              className="btn btn-secondary"
              style={{ padding: '3px 8px', fontSize: '0.75rem' }}
            >
              🚀 5m MACD + Golden Breakout
            </button>
          </div>
        </div>

        {/* Generate Button */}
        <div>
          <button
            type="button"
            onClick={handleGenerate}
            disabled={loading}
            className="btn btn-primary"
            style={{ width: '100%', padding: '12px', fontSize: '0.95rem', justifyContent: 'center' }}
          >
            <Sparkles size={18} className={loading ? 'animate-spin' : ''} />
            <span>{loading ? `Synthesizing with ${provider}...` : `Generate Strategy with ${provider}`}</span>
          </button>
        </div>

        {/* Pre-Save Indicator & Calculation Audit Verification Card */}
        {indicatorAudit && generatedStrategy && (
          <div style={{
            background: 'rgba(15, 23, 42, 0.8)',
            border: '1px solid var(--accent-emerald)',
            borderRadius: '8px',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <ShieldCheck size={20} color="var(--accent-emerald)" />
                <h4 style={{ fontSize: '1rem', fontWeight: 800, color: '#fff', margin: 0 }}>
                  Pre-Save Mathematical & Indicator Audit: PASSED
                </h4>
              </div>
              <span className="badge badge-running">VERIFIED CALCULATIONS</span>
            </div>

            {/* Verification Checklist */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.85rem' }}>
              {indicatorAudit.checksPassed.map((c, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-emerald)' }}>
                  <CheckCircle2 size={15} />
                  <span>{c}</span>
                </div>
              ))}
            </div>

            {/* Generated Strategy Preview */}
            <div style={{
              background: 'rgba(0, 0, 0, 0.4)',
              borderRadius: '6px',
              padding: '12px',
              border: '1px solid var(--border-subtle)',
              fontSize: '0.85rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}>
              <div><strong style={{ color: '#fff' }}>Strategy Name:</strong> <span style={{ color: 'var(--accent-cyan)' }}>{generatedStrategy.name}</span></div>
              <div><strong style={{ color: '#fff' }}>Asset & Timeframe:</strong> {generatedStrategy.underlying} ({generatedStrategy.timeframe})</div>
              <div><strong style={{ color: '#fff' }}>Entry Expression:</strong> <code style={{ color: 'var(--accent-emerald)' }}>{generatedStrategy.entryRules?.[0]}</code></div>
              <div><strong style={{ color: '#fff' }}>Exit Expression:</strong> <code style={{ color: 'var(--accent-rose)' }}>{generatedStrategy.exitRules?.[0]}</code></div>
              <div>
                <strong style={{ color: '#fff' }}>Execution Leg:</strong>{' '}
                {generatedStrategy.legs?.[0]?.side} {generatedStrategy.legs?.[0]?.strikeSelection} {generatedStrategy.legs?.[0]?.positionType} (Qty: {generatedStrategy.legs?.[0]?.quantity}, SL: {generatedStrategy.legs?.[0]?.stopLossPoints} pts, Target: {generatedStrategy.legs?.[0]?.targetPoints} pts)
              </div>
            </div>

            {/* Action Buttons */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '6px' }}>
              <button
                type="button"
                onClick={handleFillBuilder}
                className="btn btn-secondary"
                style={{ justifyContent: 'center' }}
              >
                <span>Edit in Builder Form</span>
              </button>

              <button
                type="button"
                onClick={handleSaveToFleet}
                disabled={saving}
                className="btn btn-emerald"
                style={{ justifyContent: 'center' }}
              >
                <Save size={16} />
                <span>{saving ? 'Saving to Fleet...' : '⚡ Auto-Fill & Save Strategy'}</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};

export default AIStrategyGeneratorModal;
