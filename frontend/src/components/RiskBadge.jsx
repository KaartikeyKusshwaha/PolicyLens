import React from 'react';
import { AlertTriangle, CheckCircle, AlertCircle, Shield } from 'lucide-react';

const RiskBadge = ({ level, score }) => {
  const configs = {
    high: {
      bg: 'bg-gradient-to-r from-red-500 to-red-600 dark:from-red-600 dark:to-red-700',
      text: 'text-white',
      label: 'High Risk',
      icon: AlertTriangle,
    },
    medium: {
      bg: 'bg-gradient-to-r from-orange-500 to-orange-600 dark:from-orange-600 dark:to-orange-700',
      text: 'text-white',
      label: 'Medium Risk',
      icon: AlertCircle,
    },
    low: {
      bg: 'bg-gradient-to-r from-green-500 to-green-600 dark:from-green-600 dark:to-green-700',
      text: 'text-white',
      label: 'Low Risk',
      icon: CheckCircle,
    },
    acceptable: {
      bg: 'bg-gradient-to-r from-blue-500 to-blue-600 dark:from-blue-600 dark:to-blue-700',
      text: 'text-white',
      label: 'Acceptable',
      icon: Shield,
    },
  };
  
  const config = configs[level?.toLowerCase()] || configs.acceptable;
  const Icon = config.icon;
  
  return (
    <div className="flex items-center space-x-2">
      <span className={`badge ${config.bg} ${config.text} flex items-center gap-1.5 shadow-md`}>
        <Icon className="w-4 h-4" />
        {config.label}
      </span>
      {score !== undefined && (
        <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          Score: {(score * 100).toFixed(0)}%
        </span>
      )}
    </div>
  );
};

export default RiskBadge;
