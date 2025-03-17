import React from 'react';

/**
 * Компонент для відображення детальної інформації про ордери
 */
const OrderDetail = ({ order, onClose }) => {
  if (!order) return null;
  
  const { token, exchange, type, orders = [] } = order;
  
  // Сортуємо ордери за ціною (для sell - від найвищої до найнижчої)
  const sortedOrders = [...orders].sort((a, b) => {
    const priceA = parseFloat(a[0]);
    const priceB = parseFloat(b[0]);
    return type === 'sell' ? priceB - priceA : priceA - priceB;
  });
  
  // Розрахунок глибини для кожного ордера
  let cumulativeDepth = 0;
  const ordersWithDepth = sortedOrders.map(order => {
    const price = parseFloat(order[0]);
    const amount = parseFloat(order[1]);
    const total = price * amount;
    cumulativeDepth += amount;
    
    return { price, amount, total, depth: cumulativeDepth };
  });
  
  // Обмежуємо кількість рядків до 100
  const limitedOrders = ordersWithDepth.slice(0, 100);
  
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{token} {type === 'sell' ? 'Sell' : 'Buy'} Orders on {exchange}</h2>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        
        {limitedOrders.length > 0 ? (
          <table className="order-detail-table">
            <thead>
              <tr>
                <th>Price</th>
                <th>Amount</th>
                <th>Total</th>
                <th>Depth</th>
              </tr>
            </thead>
            <tbody>
              {limitedOrders.map((order, index) => (
                <tr key={index}>
                  <td>{order.price.toFixed(8)}</td>
                  <td>{order.amount.toFixed(8)}</td>
                  <td>{order.total.toFixed(8)}</td>
                  <td>{order.depth.toFixed(8)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No orders available</p>
        )}
      </div>
    </div>
  );
};

export default OrderDetail;