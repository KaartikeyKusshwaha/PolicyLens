import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './contexts/ThemeContext';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import EvaluateTransaction from './pages/EvaluateTransaction';
import Policies from './pages/Policies';
import QueryAssistant from './pages/QueryAssistant';
import UploadPolicy from './pages/UploadPolicy';
import DecisionHistory from './pages/DecisionHistory';
import Metrics from './pages/Metrics';
import FeedbackViewer from './pages/FeedbackViewer';
import ExternalDataSources from './pages/ExternalDataSources';

function App() {
  return (
    <ThemeProvider>
      <Router>
        <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 transition-colors duration-200">
          <Navbar />
          <main className="container mx-auto px-4 py-8">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/evaluate" element={<EvaluateTransaction />} />
              <Route path="/policies" element={<Policies />} />
              <Route path="/query" element={<QueryAssistant />} />
              <Route path="/upload" element={<UploadPolicy />} />
              <Route path="/decisions" element={<DecisionHistory />} />
              <Route path="/metrics" element={<Metrics />} />
              <Route path="/feedback" element={<FeedbackViewer />} />
              <Route path="/external-data" element={<ExternalDataSources />} />
            </Routes>
          </main>
        </div>
      </Router>
    </ThemeProvider>
  );
}

export default App;
