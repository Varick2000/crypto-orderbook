import React, { useState, useEffect } from 'react';
import OrderBookTable from './OrderBookTable';
import OrderDetail from './OrderDetail';
import ExchangeManager from './ExchangeManager';
import TokenManager from './TokenManager';
import Settings from './Settings';
import WebSocketService from '../services/websocket';
import '../App.css';

// URL для WebSocket-з'єднання з бекендом
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';

function App() {
  // Стан додатку
  const [wsService, setWsService] = useState(null);
  const [connected, setConnected] = useState(false);
  const [tokens, setTokens] = useState([]);
  const [exchanges, setExchanges] = useState([]);
  const [orderbooks, setOrderbooks] = useState({});
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [thresholds, setThresholds] = useState({
    percentThreshold: 5.0,  // 5%
    deltaThreshold: 0.5     // 0.5 USDT
  });
  const [searchToken, setSearchToken] = useState('');
  
  // Ініціалізація WebSocket-сервісу
  useEffect(() => {
    const service = new WebSocketService(WS_URL);
    let updateTimeout = null;

    const scheduleNextUpdate = () => {
      updateTimeout = setTimeout(() => {
        if (service && service.isConnected) {
          service.updatePrices().then(() => {
            scheduleNextUpdate();
          });
        } else {
          scheduleNextUpdate();
        }
      }, 1000);
    };
    
    // Реєстрація обробників подій
    service
      .on('onOpen', () => {
        setConnected(true);
        service.updatePrices().then(() => {
          scheduleNextUpdate();
        });
      })
      .on('onClose', () => {
        setConnected(false);
        if (updateTimeout) {
          clearTimeout(updateTimeout);
        }
      })
      .on('onInitialData', (data) => {
        setTokens(data.tokens || []);
        setExchanges(data.exchanges.map(e => e.name) || []);
        setOrderbooks(data.orderbooks || {});
      })
      .on('onOrderbookUpdate', (data) => {
        console.log('Отримано оновлення ордербуку:', data);
        setOrderbooks(prev => {
          // Створюємо глибоку копію попереднього стану
          const newOrderbooks = JSON.parse(JSON.stringify(prev));
          
          // Ініціалізуємо структуру, якщо вона не існує
          if (!newOrderbooks[data.token]) {
            newOrderbooks[data.token] = {};
          }
          
          if (!newOrderbooks[data.token][data.exchange]) {
            newOrderbooks[data.token][data.exchange] = {};
          }
          
          // Оновлюємо дані
          newOrderbooks[data.token][data.exchange] = {
            best_sell: data.best_sell,
            best_buy: data.best_buy,
            sells: data.sell,
            buys: data.buy,
            lastUpdate: Date.now()
          };
          
          return newOrderbooks;
        });
      })
      .on('onTokenAdded', (token) => {
        setTokens(prev => [...prev, token]);
      })
      .on('onTokenRemoved', (token) => {
        setTokens(prev => prev.filter(t => t !== token));
      })
      .on('onExchangeAdded', (exchange) => {
        setExchanges(prev => [...prev, exchange.name]);
      })
      .on('onExchangeRemoved', (exchange) => {
        setExchanges(prev => prev.filter(e => e !== exchange));
      })
      .on('onOrderbooksCleared', () => {
        setOrderbooks({});
      });

    // Підключення до WebSocket
    service.connect();
    setWsService(service);

    // Відключення при розмонтуванні компонента
    return () => {
      if (updateTimeout) {
        clearTimeout(updateTimeout);
      }
      if (service) {
        service.disconnect();
      }
    };
  }, []);
  
  // Обробник кліку на клітину таблиці
  const handleCellClick = (token, exchange, type) => {
    const data = orderbooks[token]?.[exchange];
    
    if (!data) return;
    
    setSelectedOrder({
      token,
      exchange,
      type,
      orders: type === 'sell' ? data.sells : data.buys
    });
  };
  
  // Обробник кліку на токен
  const handleTokenClick = (token) => {
    setSearchToken(token);
  };
  
  // Обробник додавання токена
  const handleAddToken = (token) => {
    if (wsService) {
      wsService.addToken(token);
    }
  };
  
  // Обробник видалення токена
  const handleRemoveToken = () => {
    if (!searchToken) {
      showToast('Будь ласка, виберіть токен для видалення', 'error');
      return;
    }

    if (wsService) {
      wsService.removeToken(searchToken);
      setSearchToken('');
    }
  };
  
  // Обробник додавання біржі
  const handleAddExchange = (name, url, type) => {
    if (wsService) {
      wsService.addExchange(name, url, type);
    }
  };
  
  // Обробник видалення біржі
  const handleRemoveExchange = (exchange) => {
    if (wsService) {
      wsService.removeExchange(exchange);
    }
  };
  
  // Обробник оновлення цін
  const handleUpdatePrices = (exchange = null) => {
    if (wsService) {
      wsService.updatePrices(exchange);
    }
  };
  
  // Обробник очищення ордербуків
  const handleClearOrderbooks = () => {
    if (wsService) {
      wsService.clear();
    }
  };
  
  // Обробник зміни порогів підсвічування
  const handleThresholdsChange = (newThresholds) => {
    setThresholds(newThresholds);
  };
  
  // Обробник закриття модального вікна з деталями ордеру
  const handleCloseOrderDetail = () => {
    setSelectedOrder(null);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Crypto Orderbook Dashboard</h1>
        <div className="connection-status">
          <span className={`status-indicator ${connected ? 'connected' : 'disconnected'}`}></span>
          {connected ? 'Connected' : 'Disconnected'}
        </div>
      </header>
      
      <div className="app-content">
        <div className="sidebar">
          <div className="search-section">
            <input
              type="text"
              placeholder="Пошук токена..."
              value={searchToken}
              onChange={(e) => setSearchToken(e.target.value.toUpperCase())}
              className="search-input"
            />
            <button onClick={handleRemoveToken} className="remove-button">
              Видалити токен
            </button>
          </div>
          
          <TokenManager 
            tokens={tokens} 
            onAddToken={handleAddToken}
            searchToken={searchToken}
          />
          
          <ExchangeManager 
            exchanges={exchanges} 
            onAddExchange={handleAddExchange} 
            onRemoveExchange={handleRemoveExchange} 
            onUpdatePrices={handleUpdatePrices}
          />
          
          <Settings 
            thresholds={thresholds} 
            onThresholdsChange={handleThresholdsChange} 
          />
          
          <div className="actions">
            <button onClick={() => handleUpdatePrices()} className="update-button">
              Update All Prices
            </button>
            <button onClick={handleClearOrderbooks} className="clear-button">
              Clear Orderbooks
            </button>
          </div>
        </div>
        
        <div className="main-content">
          <OrderBookTable 
            orderbooks={orderbooks}
            exchanges={exchanges}
            tokens={tokens}
            thresholds={thresholds}
            onCellClick={handleCellClick}
            onTokenClick={handleTokenClick}
          />
        </div>
      </div>
      
      {selectedOrder && (
        <OrderDetail 
          order={selectedOrder} 
          onClose={handleCloseOrderDetail} 
        />
      )}
    </div>
  );
}

export default App;