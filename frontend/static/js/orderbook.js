// Константи та налаштування
const CONFIG = {
    RECONNECT_INTERVAL: 5000,
    MAX_RECONNECT_ATTEMPTS: 5,
    CHECK_CONNECTION_INTERVAL: 30000,
    RENDER_DELAY: 1000,
    PRICE_UPDATE_THRESHOLD: 0.1
};

// Стан додатку
const state = {
    orderbooks: {},
    connectionStatus: false,
    reconnectAttempts: 0,
    lastUpdate: {},
    pendingUpdates: new Set()
};

// Оновлена функція оновлення ордербуку з оптимізацією
function updateOrderbook(data) {
    console.log('Отримано оновлення ордербуку:', data);
    
    const { exchange, token, best_sell, best_buy } = data;
    
    // Валідація отриманих даних
    if (!exchange || !token) {
        console.error('Відсутні обов\'язкові поля у оновленні ордербуку:', data);
        return;
    }
    
    // Ініціалізація структури даних
    if (!state.orderbooks[token]) state.orderbooks[token] = {};
    if (!state.orderbooks[token][exchange]) state.orderbooks[token][exchange] = {};
    
    const currentBook = state.orderbooks[token][exchange];
    const prevSell = currentBook.best_sell;
    const prevBuy = currentBook.best_buy;
    
    // Валідація та форматування цін
    const validBestSell = validatePrice(best_sell, prevSell);
    const validBestBuy = validatePrice(best_buy, prevBuy);
    
    // Оновлюємо дані
    state.orderbooks[token][exchange] = {
        best_sell: validBestSell,
        best_buy: validBestBuy,
        lastUpdate: Date.now()
    };
    
    // Додаємо до черги оновлень
    state.pendingUpdates.add(`${token}-${exchange}`);
    
    // Логуємо зміни
    logPriceChanges(token, exchange, prevSell, validBestSell, prevBuy, validBestBuy);
    
    // Запускаємо оновлення UI з затримкою
    requestAnimationFrame(() => {
        updateUI(token, exchange, validBestSell, validBestBuy);
    });
}

// Валідація ціни
function validatePrice(price, prevPrice) {
    if (!price || price === 'null' || price === 'undefined') {
        return 'X X X';
    }
    return price;
}

// Перевірка необхідності оновлення ціни
function shouldUpdatePrice(oldPrice, newPrice) {
    if (oldPrice === newPrice) return false;
    if (oldPrice === 'X X X' || newPrice === 'X X X') return true;
    
    const oldVal = parseFloat(oldPrice);
    const newVal = parseFloat(newPrice);
    
    if (isNaN(oldVal) || isNaN(newVal)) return true;
    
    // Перевіряємо, чи зміна ціни перевищує поріг
    return Math.abs((newVal - oldVal) / oldVal) > CONFIG.PRICE_UPDATE_THRESHOLD;
}

// Оновлення UI
function updateUI(token, exchange, sellPrice, buyPrice) {
    console.log(`Оновлення UI для ${token} на ${exchange}:`, { sellPrice, buyPrice });
    updateTableCell(token, exchange, 'sell', sellPrice);
    updateTableCell(token, exchange, 'buy', buyPrice);
    updateLastUpdateTime(token, exchange);
}

// Оновлена функція оновлення комірки таблиці
function updateTableCell(token, exchange, type, value) {
    const cellId = `${token}-${exchange}-${type}`;
    const cell = document.getElementById(cellId);
    
    if (!cell) {
        console.warn(`Комірка не знайдена: ${cellId}`);
        return;
    }
    
    const displayValue = value === "0.0" || value === "0" ? "X X X" : value;
    
    // Оновлюємо тільки якщо значення змінилося
    if (cell.textContent !== displayValue) {
        console.log(`Оновлення комірки ${cellId}:`, { oldValue: cell.textContent, newValue: displayValue });
        cell.textContent = displayValue;
        
        // Додаємо анімацію оновлення
        cell.classList.add('updated');
        setTimeout(() => cell.classList.remove('updated'), 1000);
    }
}

// WebSocket функції
class WebSocketClient {
    constructor(url) {
        this.url = url;
        this.socket = null;
        this.init();
    }
    
    init() {
        this.connect();
        setInterval(() => this.checkConnection(), CONFIG.CHECK_CONNECTION_INTERVAL);
    }
    
    connect() {
        try {
            this.socket = new WebSocket(this.url);
            this.setupEventHandlers();
        } catch (e) {
            console.error('Помилка підключення WebSocket:', e);
            this.handleConnectionError();
        }
    }
    
    setupEventHandlers() {
        this.socket.onopen = () => {
            console.log('WebSocket з\'єднання встановлено');
            state.connectionStatus = true;
            state.reconnectAttempts = 0;
            this.onConnect();
        };
        
        this.socket.onclose = () => {
            console.log('WebSocket з\'єднання закрито');
            state.connectionStatus = false;
            this.handleConnectionError();
        };
        
        this.socket.onerror = (error) => {
            console.error('WebSocket помилка:', error);
            this.handleConnectionError();
        };
        
        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error('Помилка обробки повідомлення:', e);
            }
        };
    }
    
    handleConnectionError() {
        state.connectionStatus = false;
        if (state.reconnectAttempts < CONFIG.MAX_RECONNECT_ATTEMPTS) {
            state.reconnectAttempts++;
            setTimeout(() => this.connect(), CONFIG.RECONNECT_INTERVAL);
        } else {
            showToast('Помилка підключення до сервера', 'error');
        }
    }
    
    checkConnection() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            state.connectionStatus = true;
            this.sendMessage({ action: 'update_prices' });
            return true;
        }
        
        state.connectionStatus = false;
        this.handleConnectionError();
        return false;
    }
    
    sendMessage(message) {
        if (!this.checkConnection()) {
            showToast('Немає з\'єднання з сервером', 'error');
            return false;
        }
        
        try {
            const messageStr = JSON.stringify(message);
            this.socket.send(messageStr);
            console.log(`Відправлено повідомлення: ${messageStr}`);
            return true;
        } catch (e) {
            console.error('Помилка відправки повідомлення:', e);
            showToast('Помилка відправки повідомлення', 'error');
            return false;
        }
    }
    
    onConnect() {
        // Запит на оновлення всіх даних
        this.sendMessage({ action: 'update_prices' });
        showToast('Підключено до сервера', 'success');
    }
    
    handleMessage(data) {
        if (data.type === 'orderbook_update') {
            console.log('Отримано оновлення ордербуку:', data);
            updateOrderbook(data);
        } else if (data.type === 'orderbook_data') {
            console.log('Отримано повні дані ордербуку:', data);
            // Оновлюємо повну таблицю
            updateOrderTable(data.token, data.exchange, data.data);
            // Також оновлюємо малі таблиці
            if (data.data && data.data.asks && data.data.bids) {
                const bestAsk = data.data.asks[0];
                const bestBid = data.data.bids[0];
                updateOrderbook({
                    type: 'orderbook_update',
                    exchange: data.exchange,
                    token: data.token,
                    best_sell: bestAsk ? bestAsk.p : "X X X",
                    best_buy: bestBid ? bestBid.p : "X X X"
                });
            }
        } else {
            console.log('Отримано невідоме повідомлення:', data);
        }
    }
}

// Спеціальне виправлення для проблеми з CoinEx
class CoinExFix {
    constructor(wsClient) {
        this.wsClient = wsClient;
        this.init();
    }
    
    init() {
        console.log('Спеціальне виправлення для проблеми з CoinEx активовано');
        this.setupEventHandlers();
        this.addRefreshButton();
        this.setupPeriodicUpdate();
    }
    
    setupEventHandlers() {
        // Перевизначаємо обробку повідомлень для CoinEx
        const originalHandleMessage = this.wsClient.handleMessage;
        this.wsClient.handleMessage = (data) => {
            originalHandleMessage.call(this.wsClient, data);
            
            if (data.type === 'initial_data') {
                console.log('Отримано початкові дані, перевіряємо дані CoinEx');
                this.processCoinExData(data.orderbooks);
                // Оновлюємо статус CoinEx
                this.updateExchangeStatus('CoinEx', 'connected');
            } else if (data.type === 'orderbook_update') {
                console.log('Отримано оновлення:', data);
                if (data.exchange === 'CoinEx') {
                    if (data.token && (data.best_sell || data.best_buy)) {
                        this.forceCoinExUpdate(data.token, data.best_sell, data.best_buy);
                        this.updateExchangeStatus('CoinEx', 'connected');
                    }
                } else {
                    // Оновлюємо статус інших бірж
                    this.updateExchangeStatus(data.exchange, 'connected');
                }
            } else if (data.type === 'exchange_status') {
                // Оновлюємо статус біржі на основі повідомлення
                this.updateExchangeStatus(data.exchange, data.status);
            }
        };
    }
    
    processCoinExData(allOrderbooks) {
        if (!allOrderbooks) return;
        
        console.log('Перевірка даних CoinEx в повному наборі даних:', allOrderbooks);
        
        for (const token in allOrderbooks) {
            const tokenData = allOrderbooks[token];
            if (tokenData && tokenData['CoinEx']) {
                const coinexData = tokenData['CoinEx'];
                console.log(`Знайдено дані CoinEx для ${token}:`, coinexData);
                
                if (coinexData.best_sell || coinexData.best_buy) {
                    this.forceCoinExUpdate(token, coinexData.best_sell, coinexData.best_buy);
                }
            }
        }
    }
    
    forceCoinExUpdate(token, best_sell, best_buy) {
        console.log(`Примусове оновлення даних CoinEx для ${token}: sell=${best_sell}, buy=${best_buy}`);
        
        // Валідація значень
        best_sell = this.validateCoinExPrice(best_sell);
        best_buy = this.validateCoinExPrice(best_buy);
        
        // Оновлення даних в стані
        if (!state.orderbooks[token]) state.orderbooks[token] = {};
        if (!state.orderbooks[token]['CoinEx']) state.orderbooks[token]['CoinEx'] = {};
        
        state.orderbooks[token]['CoinEx'] = {
            best_sell,
            best_buy,
            lastUpdate: Date.now()
        };
        
        // Оновлення UI
        this.updateCoinExTableCells(token, best_sell, best_buy);
    }
    
    validateCoinExPrice(price) {
        if (price === '0.0' || price === '0' || !price) {
            console.warn(`Невалідне значення ціни CoinEx: ${price}`);
            return '0.0';
        }
        return price;
    }
    
    updateCoinExTableCells(token, best_sell, best_buy) {
        const sellCellId = `${token}-CoinEx-sell`;
        const buyCellId = `${token}-CoinEx-buy`;
        
        const sellCell = document.getElementById(sellCellId);
        const buyCell = document.getElementById(buyCellId);
        
        if (sellCell) {
            sellCell.textContent = best_sell;
            this.highlightUpdatedCell(sellCell);
        }
        
        if (buyCell) {
            buyCell.textContent = best_buy;
            this.highlightUpdatedCell(buyCell);
        }
    }
    
    highlightUpdatedCell(cell) {
        cell.classList.add('coinex-updated');
        setTimeout(() => cell.classList.remove('coinex-updated'), 2000);
    }
    
    addRefreshButton() {
        const controlGroup = document.querySelector('.control-group');
        if (!controlGroup) return;
        
        const button = document.createElement('button');
        button.id = 'coinex-refresh-btn';
        button.className = 'refresh-btn';
        button.textContent = 'Оновити CoinEx';
        button.style.backgroundColor = '#f59e0b';
        
        button.addEventListener('click', () => {
            console.log('Запит на примусове оновлення даних CoinEx');
            this.wsClient.sendMessage({
                action: 'update_prices',
                exchange: 'CoinEx'
            });
            showToast('Запит на оновлення даних CoinEx відправлено', 'info');
        });
        
        controlGroup.appendChild(button);
    }
    
    setupPeriodicUpdate() {
        setInterval(() => {
            if (this.wsClient.socket?.readyState === WebSocket.OPEN) {
                console.log('Періодичне оновлення даних CoinEx');
                this.wsClient.sendMessage({
                    action: 'update_prices',
                    exchange: 'CoinEx'
                });
            }
        }, 60000);
    }

    updateExchangeStatus(exchange, status) {
        const statusElement = document.getElementById(`${exchange}-status`);
        if (!statusElement) return;

        // Видаляємо всі попередні класи статусу
        statusElement.classList.remove(
            'exchange-connected',
            'exchange-disconnected',
            'exchange-no-data',
            'exchange-error',
            'exchange-syncing'
        );

        // Додаємо новий клас статусу
        switch (status) {
            case 'connected':
                statusElement.classList.add('exchange-connected');
                break;
            case 'disconnected':
                statusElement.classList.add('exchange-disconnected');
                break;
            case 'no_data':
                statusElement.classList.add('exchange-no-data');
                break;
            case 'error':
                statusElement.classList.add('exchange-error');
                break;
            case 'syncing':
                statusElement.classList.add('exchange-syncing');
                break;
        }
    }
}

// Додаємо стилі для анімації
const coinexStyles = document.createElement('style');
coinexStyles.textContent = `
    .coinex-updated {
        background-color: rgba(255, 215, 0, 0.3) !important;
        transition: background-color 2s;
    }
`;
document.head.appendChild(coinexStyles);

// Модифікуємо ініціалізацію
document.addEventListener('DOMContentLoaded', () => {
    const wsClient = new WebSocketClient('ws://localhost:8000/ws');
    const coinexFix = new CoinExFix(wsClient);
    
    // Обробка кнопки оновлення
    const refreshButton = document.getElementById('refresh-btn');
    if (refreshButton) {
        refreshButton.addEventListener('click', () => {
            wsClient.sendMessage({ action: 'update_prices' });
            setTimeout(forceRenderTable, CONFIG.RENDER_DELAY);
        });
    }
});

// Допоміжні функції
function showToast(message, type = 'info') {
    // Реалізація показу повідомлень користувачу
    console.log(`[${type}] ${message}`);
}

function logPriceChanges(token, exchange, prevSell, newSell, prevBuy, newBuy) {
    console.log(
        `Оновлено ціни для ${token} на ${exchange}:`,
        `\n sell=${newSell} (було ${prevSell})`,
        `\n buy=${newBuy} (було ${prevBuy})`
    );
}

function updateLastUpdateTime(token, exchange) {
    const timeElement = document.getElementById(`${token}-${exchange}-update-time`);
    if (timeElement) {
        timeElement.textContent = new Date().toLocaleTimeString();
    }
}

// Функція оновлення таблиці ордерів
function updateOrderTable(token, exchange, data) {
    console.log('Оновлення таблиці ордерів:', { token, exchange, data });
    
    const { asks, bids } = data;
    if (!asks || !bids) {
        console.error('Відсутні дані для таблиці ордерів');
        return;
    }
    
    // Знаходимо таблиці
    const asksTableBody = document.querySelector(`#${token}-${exchange}-asks tbody`);
    const bidsTableBody = document.querySelector(`#${token}-${exchange}-bids tbody`);
    
    if (!asksTableBody || !bidsTableBody) {
        console.error('Не знайдено таблиці для оновлення');
        return;
    }
    
    // Очищаємо таблиці
    asksTableBody.innerHTML = '';
    bidsTableBody.innerHTML = '';
    
    // Функція для форматування числа
    const formatNumber = (num) => {
        if (typeof num === 'string') num = parseFloat(num);
        return num.toFixed(8);
    };
    
    // Функція для створення рядка таблиці
    const createRow = (price, size, sum, depth) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${formatNumber(price)}</td>
            <td>${formatNumber(size)}</td>
            <td>${formatNumber(sum)}</td>
            <td>${formatNumber(depth)}</td>
        `;
        return row;
    };
    
    // Обробка asks (продажі)
    let asksDepth = 0;
    asks.forEach((ask, index) => {
        const price = parseFloat(ask.p);
        const size = parseFloat(ask.s);
        const sum = price * size;
        asksDepth += sum;
        asksTableBody.appendChild(createRow(price, size, sum, asksDepth));
    });
    
    // Обробка bids (купівлі)
    let bidsDepth = 0;
    bids.forEach((bid, index) => {
        const price = parseFloat(bid.p);
        const size = parseFloat(bid.s);
        const sum = price * size;
        bidsDepth += sum;
        bidsTableBody.appendChild(createRow(price, size, sum, bidsDepth));
    });
    
    console.log('Таблиці ордерів оновлено');
}

// Експорт для тестування
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        updateOrderbook,
        validatePrice,
        shouldUpdatePrice,
        WebSocketClient
    };
} 