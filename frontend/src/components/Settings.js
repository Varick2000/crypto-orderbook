import React, { useState, useEffect } from 'react';

/**
 * Компонент для налаштування порогів підсвічування
 */
const Settings = ({ thresholds, onThresholdsChange }) => {
  const [percentThreshold, setPercentThreshold] = useState(thresholds.percentThreshold);
  const [deltaThreshold, setDeltaThreshold] = useState(thresholds.deltaThreshold);
  
  // Синхронізація зі значеннями з props
  useEffect(() => {
    setPercentThreshold(thresholds.percentThreshold);
    setDeltaThreshold(thresholds.deltaThreshold);
  }, [thresholds]);
  
  // Обробник зміни порогу відсотків
  const handlePercentChange = (e) => {
    const value = parseFloat(e.target.value);
    setPercentThreshold(value);
    onThresholdsChange({
      ...thresholds,
      percentThreshold: value
    });
  };
  
  // Обробник зміни порогу дельти
  const handleDeltaChange = (e) => {
    const value = parseFloat(e.target.value);
    setDeltaThreshold(value);
    onThresholdsChange({
      ...thresholds,
      deltaThreshold: value
    });
  };

  return (
    <div>
      <h3>Settings</h3>
      
      <div className="form-group">
        <div className="settings-slider">
          <label htmlFor="percent-threshold">Percent Threshold:</label>
          <input
            id="percent-threshold"
            type="range"
            min="0.1"
            max="20"
            step="0.1"
            value={percentThreshold}
            onChange={handlePercentChange}
          />
          <span className="value">{percentThreshold}%</span>
        </div>
      </div>
      
      <div className="form-group">
        <div className="settings-slider">
          <label htmlFor="delta-threshold">Delta Threshold:</label>
          <input
            id="delta-threshold"
            type="range"
            min="0.01"
            max="5"
            step="0.01"
            value={deltaThreshold}
            onChange={handleDeltaChange}
          />
          <span className="value">{deltaThreshold} USDT</span>
        </div>
      </div>
      
      <p>
        <small>
          Cells will be highlighted when price difference exceeds either the percent
          or delta threshold compared to other exchanges.
        </small>
      </p>
    </div>
  );
};

export default Settings;