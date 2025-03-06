import React, { useState } from 'react';

/**
 * Компонент для керування токенами
 */
const TokenManager = ({ tokens, onAddToken, onRemoveToken }) => {
  const [newToken, setNewToken] = useState('');
  
  // Обробник додавання токена
  const handleAddToken = (e) => {
    e.preventDefault();
    
    if (!newToken) {
      return;
    }
    
    onAddToken(newToken);
    setNewToken('');
  };

  return (
    <div>
      <h3>Tokens</h3>
      
      <div className="token-list">
        {tokens.map(token => (
          <div key={token} className="list-item">
            <span>{token}</span>
            <button 
              className="remove-button" 
              onClick={() => onRemoveToken(token)}
            >
              ✕
            </button>
          </div>
        ))}
        
        {tokens.length === 0 && (
          <div className="list-item">No tokens added</div>
        )}
      </div>
      
      <form onSubmit={handleAddToken}>
        <div className="form-group">
          <label htmlFor="token-input">Add Token:</label>
          <div style={{ display: 'flex' }}>
            <input
              id="token-input"
              type="text"
              placeholder="Token Symbol (e.g. BTC)"
              value={newToken}
              onChange={e => setNewToken(e.target.value)}
              style={{ marginRight: '5px' }}
            />
            <button type="submit">Add</button>
          </div>
        </div>
      </form>
    </div>
  );
};

export default TokenManager;