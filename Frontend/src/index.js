// index.js
import React from 'react';
import ReactDOM from 'react-dom/client'; // Import for React 18+
import './styles/index.css'; // Import your main CSS file (for Tailwind)
import App from './App'; // Import your main App component

// Get the root element from your public/index.html
const root = ReactDOM.createRoot(document.getElementById('root'));

// Render your App component inside the root element
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
