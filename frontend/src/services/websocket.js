/**
 * Сервіс для роботи з WebSocket-підключенням до бекенду
 */
class WebSocketService {
    constructor(url) {
      this.url = url;
      this.socket = null;
      this.isConnected = false;
      this.reconnectTimeout = null;
      this.reconnectAttempts = 0;
      this.maxReconnectAttempts = 10;
      this.reconnectDelay = 2000; // 2 секунди
      
      // Колбеки для різних подій
      this.callbacks = {
        onOpen: [],
        onClose: [],
        onError: [],
        onOrderbookUpdate: [],
        onTokenAdded: [],
        onTokenRemoved: [],
        onExchangeAdded: [],
        onExchangeRemoved: [],
        onOrderbooksCleared: [],
        onFullTableUpdate: [],
        onInitialData: [],
        onError: []
      };
    }
  
    /**
     * Підключення до WebSocket
     */
    connect() {
      if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
        console.log('WebSocket already connected or connecting');
        return;
      }
      
      this.socket = new WebSocket(this.url);
      
      this.socket.onopen = () => {
        console.log('WebSocket connected');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.triggerCallbacks('onOpen');
      };
      
      this.socket.onclose = (event) => {
        console.log(`WebSocket closed: ${event.code} - ${event.reason}`);
        this.isConnected = false;
        this.triggerCallbacks('onClose', event);
        
        // Спроба переконектитись
        this.scheduleReconnect();
      };
      
      this.socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.triggerCallbacks('onError', error);
      };
      
      this.socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };
    }
  
    /**
     * Планування спроби переконектитись
     */
    scheduleReconnect() {
      if (this.reconnectTimeout) {
        clearTimeout(this.reconnectTimeout);
      }
      
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1);
        
        console.log(`Reconnecting in ${delay / 1000} seconds (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        
        this.reconnectTimeout = setTimeout(() => {
          this.connect();
        }, delay);
      } else {
        console.error('Max reconnect attempts reached, giving up');
      }
    }
  
    /**
     * Відключення від WebSocket
     */
    disconnect() {
      if (this.socket) {
        this.socket.close();
        this.socket = null;
        this.isConnected = false;
        
        if (this.reconnectTimeout) {
          clearTimeout(this.reconnectTimeout);
          this.reconnectTimeout = null;
        }
      }
    }
  
    /**
     * Відправка повідомлення на сервер
     */
    send(message) {
      if (!this.isConnected) {
        console.warn('Cannot send message, WebSocket not connected');
        return false;
      }
      
      try {
        this.socket.send(JSON.stringify(message));
        return true;
      } catch (error) {
        console.error('Error sending WebSocket message:', error);
        return false;
      }
    }
  
    /**
     * Обробка вхідних повідомлень
     */
    handleMessage(message) {
      const type = message.type;
      
      switch (type) {
        case 'orderbook_update':
          this.triggerCallbacks('onOrderbookUpdate', {
            exchange: message.exchange,
            token: message.token,
            sell: message.sell,
            buy: message.buy,
            best_sell: message.best_sell,
            best_buy: message.best_buy
          });
          break;
          
        case 'token_added':
          this.triggerCallbacks('onTokenAdded', message.token);
          break;
          
        case 'token_removed':
          this.triggerCallbacks('onTokenRemoved', message.token);
          break;
          
        case 'exchange_added':
          this.triggerCallbacks('onExchangeAdded', message.exchange);
          break;
          
        case 'exchange_removed':
          this.triggerCallbacks('onExchangeRemoved', message.exchange);
          break;
          
        case 'orderbooks_cleared':
          this.triggerCallbacks('onOrderbooksCleared');
          break;
          
        case 'full_table_update':
          this.triggerCallbacks('onFullTableUpdate', message.data);
          break;
          
        case 'initial_data':
          this.triggerCallbacks('onInitialData', {
            tokens: message.tokens,
            exchanges: message.exchanges,
            orderbooks: message.orderbooks
          });
          break;
          
        case 'error':
          console.error('Server error:', message.message);
          this.triggerCallbacks('onError', message.message);
          break;
          
        default:
          console.warn('Unknown message type:', type);
          break;
      }
    }
  
    /**
     * Виклик зареєстрованих колбеків
     */
    triggerCallbacks(event, data) {
      if (this.callbacks[event]) {
        this.callbacks[event].forEach(callback => {
          try {
            callback(data);
          } catch (error) {
            console.error(`Error in ${event} callback:`, error);
          }
        });
      }
    }
  
    /**
     * Реєстрація колбеку
     */
    on(event, callback) {
      if (this.callbacks[event]) {
        this.callbacks[event].push(callback);
      } else {
        console.warn(`Unknown event: ${event}`);
      }
      
      return this; // Для ланцюгового виклику
    }
  
    /**
     * Видалення колбеку
     */
    off(event, callback) {
      if (this.callbacks[event]) {
        this.callbacks[event] = this.callbacks[event].filter(cb => cb !== callback);
      }
      
      return this;
    }
  
    /**
     * Підписка на оновлення ордербуків
     */
    subscribe(tokens = [], exchanges = []) {
      return this.send({
        action: 'subscribe',
        tokens,
        exchanges
      });
    }
  
    /**
     * Додавання нового токену
     */
    addToken(token) {
      return this.send({
        action: 'add_token',
        token
      });
    }
  
    /**
     * Видалення токену
     */
    removeToken(token) {
      return this.send({
        action: 'remove_token',
        token
      });
    }
  
    /**
     * Додавання нової біржі
     */
    addExchange(exchange, url, type = 'websocket') {
      return this.send({
        action: 'add_exchange',
        exchange,
        url,
        type
      });
    }
  
    /**
     * Видалення біржі
     */
    removeExchange(exchange) {
      return this.send({
        action: 'remove_exchange',
        exchange
      });
    }
  
    /**
     * Оновлення цін
     */
    updatePrices(exchange = null) {
      return this.send({
        action: 'update_prices',
        exchange
      });
    }
  
    /**
     * Очищення всіх ордербуків
     */
    clear() {
      return this.send({
        action: 'clear'
      });
    }
  }
  
  export default WebSocketService;