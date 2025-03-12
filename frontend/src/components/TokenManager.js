import React, { useState, useEffect } from 'react';

/**
 * Компонент для керування токенами
 */
const TokenManager = ({ tokens, onAddToken, searchToken }) => {
  const [newToken, setNewToken] = useState('');
  const [filteredTokens, setFilteredTokens] = useState(tokens);
  
  useEffect(() => {
    if (searchToken) {
      setFilteredTokens(tokens.filter(token => 
        token.includes(searchToken.toUpperCase())
      ));
    } else {
      setFilteredTokens(tokens);
    }
  }, [tokens, searchToken]);

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
        {filteredTokens.map(token => (
          <div key={token} className="list-item">
            <span>{token}</span>
          </div>
        ))}
        
        {filteredTokens.length === 0 && (
          <div className="list-item">
            {searchToken ? 'Токени не знайдено' : 'Немає доданих токенів'}
          </div>
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
              onChange={e => setNewToken(e.target.value.toUpperCase())}
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