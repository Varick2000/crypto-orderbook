import React, { useState } from 'react';

/**
 * Компонент для керування біржами
 */
const ExchangeManager = ({ exchanges, onAddExchange, onRemoveExchange, onUpdatePrices }) => {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [type, setType] = useState('websocket');
  
  // Обробник додавання біржі
  const handleAddExchange = (e) => {
    e.preventDefault();
    
    if (!name || !url) {
      alert('Please enter both name and URL');
      return;
    }
    
    onAddExchange(name, url, type);
    
    // Очищення форми
    setName('');
    setUrl('');
    setType('websocket');
  };

  return (
    <div>
      <h3>Exchanges</h3>
      
      <div className="exchange-list">
        {exchanges.map(exchange => (
          <div key={exchange} className="list-item">
            <span>{exchange}</span>
            <div>
              <button 
                onClick={() => onUpdatePrices(exchange)} 
                title="Update prices"
                style={{ marginRight: '5px' }}
              >
                ⟳
              </button>
              <button 
                className="remove-button" 
                onClick={() => onRemoveExchange(exchange)}
              >
                ✕
              </button>
            </div>
          </div>
        ))}
        
        {exchanges.length === 0 && (
          <div className="list-item">No exchanges added</div>
        )}
      </div>
      
      <form onSubmit={handleAddExchange}>
        <div className="form-group">
          <label htmlFor="exchange-name">Add Exchange:</label>
          <input
            id="exchange-name"
            type="text"
            placeholder="Exchange Name"
            value={name}
            onChange={e => setName(e.target.value)}
          />
        </div>
        
        <div className="form-group">
          <input
            type="text"
            placeholder="API URL"
            value={url}
            onChange={e => setUrl(e.target.value)}
          />
        </div>
        
        <div className="form-group">
          <select value={type} onChange={e => setType(e.target.value)}>
            <option value="websocket">WebSocket</option>
            <option value="http">HTTP</option>
          </select>
        </div>
        
        <button type="submit">Add Exchange</button>
      </form>
    </div>
  );
};

export default ExchangeManager;