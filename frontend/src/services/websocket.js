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
      if (this.socket) {
        console.log('WebSocket already exists, skipping connection');
        return;
      }
      
      console.log('Connecting to WebSocket:', this.url);
      this.socket = new WebSocket(this.url);
      
      this.socket.onopen = () => {
        console.log('WebSocket connection established');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.triggerCallbacks('onOpen');
        
        // Запит початкових даних при підключенні
        this.send({ action: 'update_prices' });
      };
      
      this.socket.onclose = () => {
        console.log('WebSocket connection closed');
        this.isConnected = false;
        this.socket = null;
        this.triggerCallbacks('onClose');
        this.reconnect();
      };
      
      this.socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.triggerCallbacks('onError', error);
      };
      
      this.socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('Отримано повідомлення:', message);

          if (message.type === 'initial_data') {
            this.emit('onInitialData', message.data);
          } else if (message.type === 'orderbook_update') {
            this.emit('onOrderbookUpdate', message);
          } else if (message.type === 'token_added') {
            this.emit('onTokenAdded', message.token);
          }
        } catch (error) {
          console.error('Помилка при обробці повідомлення:', error);
        }
      };
    }
  
    /**
     * Перепідключення до WebSocket
     */
    reconnect() {
      if (this.reconnectTimeout) {
        return;
      }
      
      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.error('Max reconnection attempts reached');
        return;
      }
      
      this.reconnectAttempts++;
      this.reconnectTimeout = setTimeout(() => {
        this.reconnectTimeout = null;
        this.connect();
      }, this.reconnectDelay);
    }
  
    /**
     * Відключення від WebSocket
     */
    disconnect() {
      if (this.socket) {
        this.socket.close();
        this.socket = null;
      }
      this.isConnected = false;
      if (this.reconnectTimeout) {
        clearTimeout(this.reconnectTimeout);
        this.reconnectTimeout = null;
      }
    }
  
    /**
     * Відправка повідомлення через WebSocket
     */
    send(message) {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
        console.error('WebSocket is not connected, readyState:', this.socket?.readyState);
        return;
      }
      
      try {
        const messageStr = JSON.stringify(message);
        console.log('Sending WebSocket message:', messageStr);
        this.socket.send(messageStr);
      } catch (error) {
        console.error('Error sending message:', error);
        this.triggerCallbacks('onError', error);
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
            best_sell: message.best_sell,
            best_buy: message.best_buy,
            sell: message.sell,
            buy: message.buy
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
     * Додавання обробника подій
     */
    on(event, callback) {
      if (this.callbacks[event]) {
        this.callbacks[event].push(callback);
      }
      return this;
    }
  
    /**
     * Виклик всіх обробників для події
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
     * Оновлення цін
     */
    updatePrices() {
      return new Promise((resolve, reject) => {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
          console.warn('WebSocket не підключений');
          reject(new Error('WebSocket не підключений'));
          return;
        }

        try {
          this.socket.send(JSON.stringify({ type: 'get_prices' }));
          resolve();
        } catch (error) {
          console.error('Помилка при відправці запиту на оновлення цін:', error);
          reject(error);
        }
      });
    }
  
    /**
     * Додавання токена
     */
    addToken(token) {
      return this.send({
        action: 'add_token',
        token
      });
    }
  
    /**
     * Видалення токена
     */
    removeToken(token) {
      return this.send({
        action: 'remove_token',
        token
      });
    }
  
    /**
     * Додавання біржі
     */
    addExchange(name, url, type = 'websocket') {
      return this.send({
        action: 'add_exchange',
        exchange: name,
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
     * Очищення всіх ордербуків
     */
    clear() {
      return this.send({
        action: 'clear'
      });
    }
  }
  
  export default WebSocketService;