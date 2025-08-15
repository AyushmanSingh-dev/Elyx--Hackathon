// NavItem.js
import React from 'react';

// NavItem component for reusability
const NavItem = ({ label, section, activeSection, setActiveSection }) => (
  <button
    className={`px-4 py-2 rounded-md text-white font-medium transition-colors duration-300
      ${activeSection === section ? 'bg-indigo-600 shadow-lg' : 'hover:bg-indigo-700'}`}
    onClick={() => setActiveSection(section)}
  >
    {label}
  </button>
);

export default NavItem; // Export the component so App.js can import it
