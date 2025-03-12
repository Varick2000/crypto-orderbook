import React, { useState, useEffect, useCallback } from 'react';
import { calculatePercent, calculateDelta } from '../utils/calculations';

/**
 * Таблиця з ордербуками для всіх токенів і бірж
 */
const OrderBookTable = ({ 
  orderbooks, 
  exchanges, 
  tokens,
  thresholds,
  onCellClick
}) => {
  // Стан для підсвічених клітин
  const [highlightedCells, setHighlightedCells] = useState({});

  // Функція для визначення чи потрібно підсвітити клітину
  const shouldHighlight = useCallback((token, exchange, type, value) => {
    if (value === 'X X X' || !exchanges || exchanges.length < 2) return null;

    const currentValue = parseFloat(value);
    if (isNaN(currentValue)) return null;

    // Порівнюємо з іншими біржами
    let highlightType = null;
    
    for (const otherExchange of exchanges) {
      if (otherExchange === exchange) continue;
      
      const otherValue = orderbooks[token]?.[otherExchange]?.[type === 'sell' ? 'best_sell' : 'best_buy'];
      if (otherValue === 'X X X') continue;
      
      const otherValueFloat = parseFloat(otherValue);
      if (isNaN(otherValueFloat)) continue;
      
      // Розрахунок відсотка і дельти
      const percent = calculatePercent(currentValue, otherValueFloat);
      const delta = calculateDelta(currentValue, otherValueFloat);
      
      if (type === 'sell') {
        // Для sell ордерів підсвічуємо, якщо поточна ціна нижча
        if (
          (percent <= -thresholds.percentThreshold) || 
          (delta <= -thresholds.deltaThreshold)
        ) {
          highlightType = 'green';
          break;
        }
      } else {
        // Для buy ордерів підсвічуємо, якщо поточна ціна вища
        if (
          (percent >= thresholds.percentThreshold) || 
          (delta >= thresholds.deltaThreshold)
        ) {
          highlightType = 'green';
          break;
        }
      }
    }

    return highlightType;
  }, [orderbooks, exchanges, thresholds]);

  // Оновлення підсвічених клітин при зміні даних
  useEffect(() => {
    const newHighlightedCells = {};
    
    tokens.forEach(token => {
      newHighlightedCells[token] = {};
      
      exchanges.forEach(exchange => {
        if (!orderbooks[token] || !orderbooks[token][exchange]) return;
        
        const sellValue = orderbooks[token][exchange].best_sell;
        const buyValue = orderbooks[token][exchange].best_buy;
        
        const sellHighlight = shouldHighlight(token, exchange, 'sell', sellValue);
        const buyHighlight = shouldHighlight(token, exchange, 'buy', buyValue);
        
        newHighlightedCells[token][exchange] = {
          sell: sellHighlight,
          buy: buyHighlight
        };
      });
    });
    
    setHighlightedCells(newHighlightedCells);
  }, [orderbooks, tokens, exchanges, shouldHighlight]);

  // Функція для визначення класу CSS для клітини
  const getCellClass = (token, exchange, type) => {
    const highlight = highlightedCells[token]?.[exchange]?.[type];
    let className = `price-cell ${type}-price`;
    
    if (highlight) {
      className += ` highlight-${highlight}`;
    }
    
    return className;
  };

  // Обробник кліку на клітину
  const handleCellClick = (token, exchange, type) => {
    if (onCellClick) {
      onCellClick(token, exchange, type);
    }
  };

  return (
    <div className="orderbook-table-container">
      <table className="orderbook-table">
        <thead>
          <tr>
            <th>Token</th>
            <th>Type</th>
            {exchanges.map(exchange => (
              <th key={exchange}>{exchange}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tokens.map(token => (
            <React.Fragment key={token}>
              {/* Рядок для цін Sell */}
              <tr>
                <td rowSpan="2" className="token-cell">{token}</td>
                <td className="type-cell">Sell</td>
                {exchanges.map(exchange => (
                  <td 
                    key={`${token}-${exchange}-sell`}
                    className={getCellClass(token, exchange, 'sell')}
                    onClick={() => handleCellClick(token, exchange, 'sell')}
                  >
                    {orderbooks[token]?.[exchange]?.best_sell || 'Немає даних'}
                  </td>
                ))}
              </tr>
              {/* Рядок для цін Buy */}
              <tr>
                <td className="type-cell">Buy</td>
                {exchanges.map(exchange => (
                  <td 
                    key={`${token}-${exchange}-buy`}
                    className={getCellClass(token, exchange, 'buy')}
                    onClick={() => handleCellClick(token, exchange, 'buy')}
                  >
                    {orderbooks[token]?.[exchange]?.best_buy || 'Немає даних'}
                  </td>
                ))}
              </tr>
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default OrderBookTable;