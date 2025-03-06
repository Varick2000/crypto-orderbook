/**
 * Розрахунок відсоткової різниці між двома значеннями.
 * 
 * @param {number} value1 - Перше значення
 * @param {number} value2 - Друге значення (базове)
 * @returns {number} - Відсоткова різниця value1 відносно value2
 */
export const calculatePercent = (value1, value2) => {
    return ((value1 - value2) / value2) * 100;
  };
  
  /**
   * Розрахунок абсолютної різниці між двома значеннями.
   * 
   * @param {number} value1 - Перше значення
   * @param {number} value2 - Друге значення
   * @returns {number} - Абсолютна різниця між value1 і value2
   */
  export const calculateDelta = (value1, value2) => {
    return value1 - value2;
  };