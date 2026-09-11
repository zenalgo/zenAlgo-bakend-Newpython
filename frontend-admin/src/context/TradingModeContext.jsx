import React, { createContext, useContext, useState, useEffect } from 'react';

const TradingModeContext = createContext();

export const TradingModeProvider = ({ children }) => {
  const [tradingMode, setTradingModeState] = useState(() => {
    return localStorage.getItem('zenalgo_trading_mode') || 'LIVE';
  });

  const setTradingMode = (mode) => {
    const norm = mode === 'LIVE' ? 'LIVE' : 'PAPER';
    setTradingModeState(norm);
    localStorage.setItem('zenalgo_trading_mode', norm);
    window.dispatchEvent(new CustomEvent('zenalgo_mode_changed', { detail: norm }));
  };

  const toggleTradingMode = () => {
    setTradingMode(tradingMode === 'LIVE' ? 'PAPER' : 'LIVE');
  };

  const isLive = tradingMode === 'LIVE';
  const isPaper = tradingMode === 'PAPER';

  return (
    <TradingModeContext.Provider
      value={{
        tradingMode,
        setTradingMode,
        toggleTradingMode,
        isLive,
        isPaper,
      }}
    >
      {children}
    </TradingModeContext.Provider>
  );
};

export const useTradingMode = () => {
  const context = useContext(TradingModeContext);
  if (!context) {
    throw new Error('useTradingMode must be used within a TradingModeProvider');
  }
  return context;
};
