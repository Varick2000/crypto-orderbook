// Функція для оновлення даних в таблиці
function updateOrderbookTable(data) {
    const table = document.getElementById('orderbook-table');
    if (!table) return;

    const tbody = table.querySelector('tbody');
    if (!tbody) return;

    // Очищаємо поточні дані
    tbody.innerHTML = '';

    // Додаємо нові дані
    data.forEach(order => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="token-cell">${order.token}</td>
            <td class="type-cell ${order.type === 'sell' ? 'sell-price' : 'buy-price'}">${order.type}</td>
            <td>${order.price}</td>
            <td>${order.amount}</td>
            <td>${order.total}</td>
            <td>${order.exchange}</td>
        `;
        tbody.appendChild(row);
    });
}

// Підключаємося до WebSocket при завантаженні сторінки
document.addEventListener('DOMContentLoaded', () => {
    // Отримуємо початкові дані через WebSocket
    const ws = new WebSocket('ws://localhost:8000/ws');
    
    ws.onopen = () => {
        console.log('WebSocket connected for orderbook table');
        ws.send(JSON.stringify({ action: 'get_initial_data' }));
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'orderbook') {
                updateOrderbookTable(data.data);
            }
        } catch (error) {
            console.error('Error parsing message:', error);
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
        console.log('WebSocket connection closed for orderbook table');
    };
}); 