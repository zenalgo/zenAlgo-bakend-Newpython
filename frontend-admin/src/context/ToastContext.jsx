import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Info, X } from 'lucide-react';

const ToastContext = createContext(null);

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
  }, []);

  const removeToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  return (
    <ToastContext.Provider value={{ addToast }}>
      {children}
      <div style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        maxWidth: '420px',
      }}>
        {toasts.map((toast) => (
          <div
            key={toast.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              padding: '12px 16px',
              borderRadius: '8px',
              background: toast.type === 'success' ? 'rgba(16, 185, 129, 0.95)' :
                          toast.type === 'error' ? 'rgba(244, 63, 94, 0.95)' :
                          toast.type === 'warning' ? 'rgba(245, 158, 11, 0.95)' :
                          'rgba(30, 41, 59, 0.95)',
              color: '#ffffff',
              boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.5)',
              backdropFilter: 'blur(8px)',
              fontSize: '0.875rem',
              fontWeight: 500,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {toast.type === 'success' && <CheckCircle2 size={18} />}
              {toast.type === 'error' && <XCircle size={18} />}
              {toast.type === 'warning' && <AlertTriangle size={18} />}
              {toast.type === 'info' && <Info size={18} />}
              <span>{toast.message}</span>
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              style={{ background: 'transparent', border: 'none', color: '#fff', cursor: 'pointer' }}
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used within a ToastProvider');
  return context;
};
