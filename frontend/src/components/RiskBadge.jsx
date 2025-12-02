import React from 'react';

const RiskBadge = ({ level, score }) => {
  const configs = {
    high: {
      bg: 'bg-red-100',
      text: 'text-red-800',
      label: 'High Risk',
    },
    medium: {
      bg: 'bg-yellow-100',
      text: 'text-yellow-800',
      label: 'Medium Risk',
    },
    low: {
      bg: 'bg-green-100',
      text: 'text-green-800',
      label: 'Low Risk',
    },
    acceptable: {
      bg: 'bg-blue-100',
      text: 'text-blue-800',
      label: 'Acceptable',
    },
  };
  
  const config = configs[level?.toLowerCase()] || configs.acceptable;
  
  return (
    <div className="flex items-center space-x-2">
      <span className={`badge ${config.bg} ${config.text}`}>
        {config.label}
      </span>
      {score !== undefined && (
        <span className="text-sm text-gray-600">
          Score: {(score * 100).toFixed(0)}%
        </span>
      )}
    </div>
  );
};

export default RiskBadge;
