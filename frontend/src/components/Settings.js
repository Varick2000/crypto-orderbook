import React, { useState, useEffect } from 'react';
import '../styles/Settings.css';

/**
 * Компонент для налаштування порогів підсвічування
 */
const Settings = ({ thresholds, onThresholdsChange }) => {
  const [percentThreshold, setPercentThreshold] = useState(thresholds.percentThreshold);
  const [deltaThreshold, setDeltaThreshold] = useState(thresholds.deltaThreshold);
  const [isIndicatorActive, setIsIndicatorActive] = useState(false);
  
  // Синхронізація зі значеннями з props
  useEffect(() => {
    setPercentThreshold(thresholds.percentThreshold);
    setDeltaThreshold(thresholds.deltaThreshold);
    setIsIndicatorActive(thresholds.isIndicatorActive || false);
  }, [thresholds]);

  // Ефект для автоматичного оновлення
  useEffect(() => {
    let interval;
    if (isIndicatorActive) {
      interval = setInterval(() => {
        onThresholdsChange({
          ...thresholds,
          percentThreshold,
          deltaThreshold,
          forceUpdate: true
        });
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isIndicatorActive, percentThreshold, deltaThreshold]);
  
  // Обробник зміни порогу відсотків
  const handlePercentChange = (e) => {
    const newValue = parseFloat(e.target.value);
    setPercentThreshold(newValue);
    onThresholdsChange({
      ...thresholds,
      percentThreshold: newValue,
      forceUpdate: true
    });
  };
  
  // Обробник зміни порогу дельти
  const handleDeltaChange = (e) => {
    const newValue = parseFloat(e.target.value);
    setDeltaThreshold(newValue);
    onThresholdsChange({
      ...thresholds,
      deltaThreshold: newValue,
      forceUpdate: true
    });
  };

  // Обробник перемикання індикації
  const toggleIndicator = () => {
    const newState = !isIndicatorActive;
    setIsIndicatorActive(newState);
    onThresholdsChange({
      ...thresholds,
      isIndicatorActive: newState,
      forceUpdate: true
    });
  };

  const togglePercentActive = () => {
    onThresholdsChange({
      ...thresholds,
      isPercentActive: !thresholds.isPercentActive
    });
  };

  const toggleDeltaActive = () => {
    onThresholdsChange({
      ...thresholds,
      isDeltaActive: !thresholds.isDeltaActive
    });
  };

  return (
    <div className="settings-container">
      <h3>Налаштування індикації</h3>
      
      <div className="settings-slider">
        <div className="slider-header">
          <label>Відсотковий поріг:</label>
          <button 
            className={`indicator-toggle ${thresholds.isPercentActive ? 'active' : ''}`}
            onClick={togglePercentActive}
          >
            {thresholds.isPercentActive ? 'Вимкнено' : 'Увімкнено'}
          </button>
        </div>
        <input
          type="range"
          min="0.1"
          max="10"
          step="0.1"
          value={thresholds.percentThreshold}
          onChange={handlePercentChange}
          disabled={!thresholds.isPercentActive}
        />
        <div className="value">{thresholds.percentThreshold.toFixed(1)}%</div>
      </div>

      <div className="settings-slider">
        <div className="slider-header">
          <label>Поріг дельти (USDT):</label>
          <button 
            className={`indicator-toggle ${thresholds.isDeltaActive ? 'active' : ''}`}
            onClick={toggleDeltaActive}
          >
            {thresholds.isDeltaActive ? 'Вимкнено' : 'Увімкнено'}
          </button>
        </div>
        <input
          type="range"
          min="0.1"
          max="5"
          step="0.1"
          value={thresholds.deltaThreshold}
          onChange={handleDeltaChange}
          disabled={!thresholds.isDeltaActive}
        />
        <div className="value">${thresholds.deltaThreshold.toFixed(1)}</div>
      </div>

      <div className="form-group">
        <button 
          className={`indicator-toggle ${isIndicatorActive ? 'active' : ''}`}
          onClick={toggleIndicator}
        >
          {isIndicatorActive ? 'Вимкнути індикацію' : 'Увімкнути індикацію'}
        </button>
      </div>
      
      <p className="settings-description">
        <small>
          Клітинки будуть підсвічуватися, коли різниця в ціні перевищує встановлений відсотковий поріг 
          або поріг дельти порівняно з іншими біржами.
        </small>
      </p>
    </div>
  );
};

export default Settings;