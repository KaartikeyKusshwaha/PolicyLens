import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import EvaluateTransaction from './pages/EvaluateTransaction';
import Policies from './pages/Policies';
import QueryAssistant from './pages/QueryAssistant';
import UploadPolicy from './pages/UploadPolicy';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/evaluate" element={<EvaluateTransaction />} />
            <Route path="/policies" element={<Policies />} />
            <Route path="/query" element={<QueryAssistant />} />
            <Route path="/upload" element={<UploadPolicy />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
