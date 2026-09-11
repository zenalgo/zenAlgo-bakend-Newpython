import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { TradingModeProvider } from './context/TradingModeContext';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <ToastProvider>
        <TradingModeProvider>
          <App />
        </TradingModeProvider>
      </ToastProvider>
    </AuthProvider>
  </React.StrictMode>
);
