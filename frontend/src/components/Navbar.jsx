import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Shield, FileText, Search, BarChart3, Upload, History, Activity, MessageSquare } from 'lucide-react';

const Navbar = () => {
  const location = useLocation();
  
  const navItems = [
    { path: '/', label: 'Dashboard', icon: BarChart3 },
    { path: '/evaluate', label: 'Evaluate', icon: Shield },
    { path: '/decisions', label: 'Decisions', icon: History },
    { path: '/policies', label: 'Policies', icon: FileText },
    { path: '/query', label: 'Query', icon: Search },
    { path: '/metrics', label: 'Metrics', icon: Activity },
    { path: '/feedback', label: 'Feedback', icon: MessageSquare },
    { path: '/upload', label: 'Upload', icon: Upload },
  ];
  
  return (
    <nav className="bg-white shadow-lg">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-2">
            <Shield className="w-8 h-8 text-primary" />
            <span className="text-xl font-bold text-gray-800">PolicyLens</span>
          </div>
          
          <div className="flex space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-primary text-white'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="font-medium">{item.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
