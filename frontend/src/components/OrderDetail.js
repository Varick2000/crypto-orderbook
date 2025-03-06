import React from 'react';

/**
 * Компонент для відображення детальної інформації про ордери
 */
const OrderDetail = ({ order, onClose }) => {
  if (!order) return null;
  
  const { token, exchange, type, orders = [] } = order;
  
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{token} {type === 'sell' ? 'Sell' : 'Buy'} Orders on {exchange}</h2>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        
        {orders && orders.length > 0 ? (
          <table className="order-detail-table">
            <thead>
              <tr>
                <th>Price</th>
                <th>Amount</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order, index) => {
                const price = parseFloat(order[0]);
                const amount = parseFloat(order[1]);
                const total = price * amount;
                
                return (
                  <tr key={index}>
                    <td>{price.toFixed(8)}</td>
                    <td>{amount.toFixed(8)}</td>
                    <td>{total.toFixed(8)}</td>
                  </tr>
                );
              })}
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