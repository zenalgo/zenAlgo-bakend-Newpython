import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { brokerApi } from '../api/brokerApi';
import { useAuth } from './AuthContext';

const BrokerContext = createContext();

export const BrokerProvider = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [brokerSession, setBrokerSession] = useState(null);
  const [checkingBroker, setCheckingBroker] = useState(true);

  const checkBrokerSession = useCallback(async () => {
    if (!isAuthenticated) {
      setBrokerSession(null);
      setCheckingBroker(false);
      return null;
    }

    try {
      const res = await brokerApi.getActiveSession();
      if (res?.data?.connected) {
        setBrokerSession(res.data);
        return res.data;
      } else {
        setBrokerSession(null);
        return null;
      }
    } catch (err) {
      console.warn('Could not verify active broker session:', err);
      setBrokerSession(null);
      return null;
    } finally {
      setCheckingBroker(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      setCheckingBroker(true);
      checkBrokerSession();
    } else {
      setBrokerSession(null);
      setCheckingBroker(false);
    }
  }, [isAuthenticated, checkBrokerSession]);

  const isBrokerConnected = Boolean(brokerSession && brokerSession.connected);

  return (
    <BrokerContext.Provider
      value={{
        brokerSession,
        isBrokerConnected,
        checkingBroker,
        checkBrokerSession,
      }}
    >
      {children}
    </BrokerContext.Provider>
  );
};

export const useBroker = () => useContext(BrokerContext);

export default BrokerContext;
