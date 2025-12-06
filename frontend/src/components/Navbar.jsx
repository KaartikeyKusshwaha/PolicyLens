import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Shield, FileText, Search, BarChart3, Upload, History, Activity, MessageSquare, Database } from 'lucide-react';
import ThemeToggle from './ThemeToggle';

const Navbar = () => {
  const location = useLocation();
  
  const navItems = [
    { path: '/', label: 'Dashboard', icon: BarChart3, color: 'blue' },
    { path: '/evaluate', label: 'Evaluate', icon: Shield, color: 'red' },
    { path: '/decisions', label: 'Decisions', icon: History, color: 'orange' },
    { path: '/policies', label: 'Policies', icon: FileText, color: 'blue' },
    { path: '/external-data', label: 'Data Sources', icon: Database, color: 'blue' },
    { path: '/query', label: 'Query', icon: Search, color: 'orange' },
    { path: '/metrics', label: 'Metrics', icon: Activity, color: 'red' },
    { path: '/feedback', label: 'Feedback', icon: MessageSquare, color: 'blue' },
    { path: '/upload', label: 'Upload', icon: Upload, color: 'orange' },
  ];

  const getColorClasses = (color, isActive) => {
    if (!isActive) return '';
    
    const colors = {
      blue: 'bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700',
      red: 'bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700',
      orange: 'bg-gradient-to-r from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700',
    };
    return colors[color] || colors.blue;
  };
  
  return (
    <nav className="bg-white dark:bg-gray-800 shadow-lg transition-colors duration-200 sticky top-0 z-50">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="flex items-center space-x-2 group">
            <Shield className="w-8 h-8 text-blue-600 dark:text-blue-400 group-hover:scale-110 transition-transform" />
            <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 dark:from-blue-400 dark:to-purple-400 bg-clip-text text-transparent">
              PolicyLens
            </span>
          </Link>
          
          <div className="flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-all transform hover:scale-105 ${
                    isActive
                      ? `${getColorClasses(item.color, true)} text-white shadow-lg`
                      : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="font-medium">{item.label}</span>
                </Link>
              );
            })}
            <ThemeToggle />
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
