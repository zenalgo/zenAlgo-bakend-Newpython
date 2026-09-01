import React, { createContext, useContext, useState } from 'react';
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react';

const ToastContext = createContext();

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);

  const addToast = (message, type = 'info', duration = 4000) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);

    setTimeout(() => {
      removeToast(id);
    }, duration);
  };

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const getIcon = (type) => {
    switch (type) {
      case 'success':
        return <CheckCircle2 size={18} color="var(--accent-emerald)" />;
      case 'error':
        return <AlertCircle size={18} color="var(--accent-rose)" />;
      case 'warning':
        return <AlertTriangle size={18} color="var(--accent-amber)" />;
      default:
        return <Info size={18} color="var(--accent-cyan)" />;
    }
  };

  const getBorderColor = (type) => {
    switch (type) {
      case 'success': return 'var(--accent-emerald)';
      case 'error': return 'var(--accent-rose)';
      case 'warning': return 'var(--accent-amber)';
      default: return 'var(--accent-cyan)';
    }
  };

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div
        style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          maxWidth: '380px',
        }}
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className="glass-panel"
            style={{
              padding: '12px 16px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              borderLeft: `4px solid ${getBorderColor(toast.type)}`,
              boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)',
              animation: 'slideIn 0.2s ease-out forwards',
            }}
          >
            {getIcon(toast.type)}
            <div style={{ flex: 1, fontSize: '0.85rem', color: '#fff', fontWeight: 500 }}>
              {toast.message}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => useContext(ToastContext);
