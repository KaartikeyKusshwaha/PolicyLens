import React from 'react';
import { AlertCircle, CheckCircle, AlertTriangle, Info } from 'lucide-react';

const Alert = ({ type = 'info', title, message, onClose }) => {
  const configs = {
    success: {
      bg: 'bg-green-50',
      border: 'border-green-200',
      text: 'text-green-800',
      icon: CheckCircle,
      iconColor: 'text-green-500',
    },
    error: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      text: 'text-red-800',
      icon: AlertCircle,
      iconColor: 'text-red-500',
    },
    warning: {
      bg: 'bg-yellow-50',
      border: 'border-yellow-200',
      text: 'text-yellow-800',
      icon: AlertTriangle,
      iconColor: 'text-yellow-500',
    },
    info: {
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      text: 'text-blue-800',
      icon: Info,
      iconColor: 'text-blue-500',
    },
  };
  
  const config = configs[type];
  const Icon = config.icon;
  
  return (
    <div className={`${config.bg} ${config.border} border rounded-lg p-4 mb-4`}>
      <div className="flex items-start">
        <Icon className={`w-5 h-5 ${config.iconColor} mt-0.5`} />
        <div className="ml-3 flex-1">
          {title && (
            <h3 className={`text-sm font-medium ${config.text}`}>{title}</h3>
          )}
          {message && (
            <p className={`text-sm ${config.text} ${title ? 'mt-1' : ''}`}>
              {message}
            </p>
          )}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className={`ml-3 ${config.text} hover:opacity-75`}
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
};

export default Alert;
