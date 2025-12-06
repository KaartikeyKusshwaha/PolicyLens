import axios from 'axios';

// Frontend is on port 3000, API is on port 8000
// Always use localhost:8000 for API calls
const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const policyService = {
  uploadPolicy: async (policyData) => {
    const response = await api.post('/api/policies/upload', policyData);
    return response.data;
  },
  
  getStats: async () => {
    const response = await api.get('/api/policies/stats');
    return response.data;
  },
  
  getAll: async () => {
    const response = await api.get('/api/policies');
    return response.data;
  },
};

export const transactionService = {
  evaluate: async (transaction) => {
    const response = await api.post('/api/transactions/evaluate', {
      transaction
    });
    return response.data;
  },
};

export const queryService = {
  ask: async (query, topic = null) => {
    const response = await api.post('/api/query', {
      query,
      topic,
      top_k: 5
    });
    return response.data;
  },
};

export const feedbackService = {
  submit: async (feedbackData) => {
    const response = await api.post('/api/feedback', feedbackData);
    return response.data;
  },
  
  getAll: async () => {
    const response = await api.get('/api/feedback');
    return response.data;
  },
  
  getForTransaction: async (traceId) => {
    const response = await api.get(`/api/feedback?trace_id=${traceId}`);
    return response.data;
  },
};

export const decisionService = {
  getAll: async () => {
    const response = await api.get('/api/decisions');
    return response.data;
  },
  
  getById: async (traceId) => {
    const response = await api.get(`/api/decisions/${traceId}`);
    return response.data;
  },
};

export const auditService = {
  getReport: async (traceId) => {
    const response = await api.get(`/api/audit/report/${traceId}`);
    return response.data;
  },
};

export const metricsService = {
  get: async () => {
    const response = await api.get('/api/metrics');
    return response.data;
  },
  getLatency: async (operationType = null, hours = null) => {
    const params = new URLSearchParams();
    if (operationType) params.append('operation_type', operationType);
    if (hours) params.append('hours', hours);
    const queryString = params.toString();
    const url = queryString ? `/api/metrics/latency?${queryString}` : '/api/metrics/latency';
    const response = await api.get(url);
    return response.data;
  },
  getCounters: async () => {
    const response = await api.get('/api/metrics/counters');
    return response.data;
  },
};

export const externalDataService = {
  fetchData: async (source) => {
    const response = await api.post(`/api/external-data/fetch?source=${source}`);
    return response.data;
  },
  
  syncAll: async () => {
    const response = await api.post('/api/external-data/sync');
    return response.data;
  },
  
  getSchedulerStatus: async () => {
    const response = await api.get('/api/external-data/scheduler/status');
    return response.data;
  },
  
  triggerScheduledFetch: async (source) => {
    const response = await api.post(`/api/external-data/scheduler/trigger?source=${source}`);
    return response.data;
  },
  
  getHistory: async (limit = 50) => {
    const response = await api.get(`/api/external-data/history?limit=${limit}`);
    return response.data;
  },
};

export const healthCheck = async () => {
  const response = await api.get('/');
  return response.data;
};

export default api;
