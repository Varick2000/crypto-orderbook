import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { calculatePercent, calculateDelta } from '../utils/calculations';

/**
 * Таблиця з ордербуками для всіх токенів і бірж
 */
const OrderBookTable = ({ 
  orderbooks, 
  exchanges, 
  tokens,
  thresholds,
  onCellClick,
  onTokenClick
}) => {
  // Стан для підсвічених клітин
  const [highlightedCells, setHighlightedCells] = useState({});
  // Зберігаємо попередні значення для порівняння
  const prevValues = useRef({});
  const [isAscending, setIsAscending] = useState(true);

  // Логуємо вхідні пропси при кожному рендері
  console.log('OrderBookTable props:', { 
    tokens,
    isAscending
  });

  // Функція для сортування токенів
  const getSortedTokens = () => {
    return [...tokens].sort((a, b) => {
      return isAscending ? a.localeCompare(b) : b.localeCompare(a);
    });
  };

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
        const lastUpdate = orderbooks[token][exchange].lastUpdate;
        
        // Перевіряємо чи змінилися значення
        const prevSell = prevValues.current[`${token}-${exchange}-sell`];
        const prevBuy = prevValues.current[`${token}-${exchange}-buy`];
        const prevUpdate = prevValues.current[`${token}-${exchange}-update`];
        
        const isUpdated = lastUpdate && (!prevUpdate || lastUpdate > prevUpdate);
        
        if (sellValue !== prevSell || isUpdated) {
          prevValues.current[`${token}-${exchange}-sell`] = sellValue;
        }
        
        if (buyValue !== prevBuy || isUpdated) {
          prevValues.current[`${token}-${exchange}-buy`] = buyValue;
        }
        
        prevValues.current[`${token}-${exchange}-update`] = lastUpdate;
        
        const sellHighlight = shouldHighlight(token, exchange, 'sell', sellValue);
        const buyHighlight = shouldHighlight(token, exchange, 'buy', buyValue);
        
        newHighlightedCells[token][exchange] = {
          sell: sellHighlight,
          buy: buyHighlight,
          sellUpdated: sellValue !== prevSell || isUpdated,
          buyUpdated: buyValue !== prevBuy || isUpdated
        };
      });
    });
    
    setHighlightedCells(newHighlightedCells);
  }, [orderbooks, tokens, exchanges, shouldHighlight]);

  // Функція для визначення класу CSS для клітини
  const getCellClass = (token, exchange, type) => {
    const highlight = highlightedCells[token]?.[exchange];
    let className = `price-cell ${type}-price`;
    
    if (highlight) {
      if (highlight[type]) {
        className += ` highlight-${highlight[type]}`;
      }
      if (highlight[`${type}Updated`]) {
        className += ' updated';
      }
    }
    
    return className;
  };

  return (
    <div className="orderbook-table-container">
      <table className="orderbook-table">
        <thead>
          <tr>
            <th 
              onClick={() => setIsAscending(!isAscending)}
              style={{ 
                cursor: 'pointer',
                backgroundColor: '#f2f2f2',
                userSelect: 'none',
                position: 'relative',
                paddingRight: '20px'
              }}
            >
              Token 
              <span style={{
                position: 'absolute',
                right: '5px',
                top: '50%',
                transform: 'translateY(-50%)'
              }}>
                {isAscending ? '↑' : '↓'}
              </span>
            </th>
            <th>Type</th>
            {exchanges.map(exchange => (
              <th key={exchange}>{exchange}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {getSortedTokens().map(token => (
            <React.Fragment key={token}>
              <tr>
                <td 
                  rowSpan="2" 
                  className="token-cell" 
                  onClick={() => onTokenClick(token)}
                  style={{ cursor: 'pointer' }}
                >
                  {token}
                </td>
                <td className="type-cell">Sell</td>
                {exchanges.map(exchange => (
                  <td 
                    key={`${token}-${exchange}-sell`}
                    className={getCellClass(token, exchange, 'sell')}
                    onClick={() => onCellClick(token, exchange, 'sell')}
                  >
                    {orderbooks[token]?.[exchange]?.best_sell || 'Немає даних'}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="type-cell">Buy</td>
                {exchanges.map(exchange => (
                  <td 
                    key={`${token}-${exchange}-buy`}
                    className={getCellClass(token, exchange, 'buy')}
                    onClick={() => onCellClick(token, exchange, 'buy')}
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