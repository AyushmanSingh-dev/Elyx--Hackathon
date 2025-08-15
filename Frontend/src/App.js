// App.js
import React, { useState, useEffect, useCallback } from 'react';
// Import the NavItem component.
// This path assumes NavItem.js is located at: Frontend/src/components/NavItem.js
import NavItem from './components/NavItem'; 
// FIXED: Corrected import path for sampleJourneyData.
// This path assumes sample_journey.json is located at the project root level in the 'Data' folder (e.g., my-elyx-hackathon/Data/sample_journey.json),
// and App.js is located in 'Frontend/src/App.js'.
import sampleJourneyData from '../../Data/sample_journey.json'; 

function App() {
  const [activeSection, setActiveSection] = useState('dashboard');
  const [userId, setUserId] = useState('');
  const [isAuthReady, setIsAuthReady] = useState(false);
  const [decisionQuery, setDecisionQuery] = useState('');
  const [decisionResponse, setDecisionResponse] = useState('');
  const [isLoadingDecision, setIsLoadingDecision] = useState(false);
  const [journeyData, setJourneyData] = useState([]);
  const [isGeneratingConversation, setIsGeneratingConversation] = useState(true); // Set to true initially

  // IMPORTANT: Replace this with YOUR ACTUAL RENDER BACKEND URL
  // You got this URL from Render after your backend deployment was successful (e.g., https://elyx-hackathon-4.onrender.com)
  const BACKEND_API_BASE_URL = "https://elyx-hackathon-4.onrender.com"; // <-- Update this line with your Render URL!

  // Function to call the backend API for decision explanation
  const handleDecisionQuery = async () => {
    if (!decisionQuery.trim()) {
      setDecisionResponse("Please enter a question about a decision.");
      return;
    }

    setIsLoadingDecision(true);
    setDecisionResponse("Thinking...");

    try {
      // Make a fetch request to your deployed Python backend
      const response = await fetch(`${BACKEND_API_BASE_URL}/api/explain-decision`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        // Send the user's query and the entire journey data as context to the backend
        body: JSON.stringify({ query: decisionQuery, journeyData: journeyData }),
      });

      const data = await response.json();

      if (response.ok) {
        // If the response is successful, set the explanation
        setDecisionResponse(data.explanation);
      } else {
        // Handle errors from the backend
        setDecisionResponse(`Error from backend: ${data.error || 'Unknown error'}`);
        console.error("Backend error response:", data);
      }

    } catch (error) {
      // Handle network errors or issues with the fetch request itself
      console.error("Error calling backend API:", error);
      setDecisionResponse("An error occurred while connecting to the backend. Please ensure the backend is running and the URL is correct.");
    } finally {
      setIsLoadingDecision(false);
    }
  };

  // Authenticate user and load journey data
  useEffect(() => {
    const firebaseConfig = typeof __firebase_config !== 'undefined' ? JSON.parse(__firebase_config) : null;
    const initialAuthToken = typeof __initial_auth_token !== 'undefined' ? __initial_auth_token : null; 

    if (firebaseConfig) {
      import('https://www.gstatic.com/firebasejs/11.6.1/firebase-app.js')
        .then(module => {
          const { initializeApp } = module;
          const app = initializeApp(firebaseConfig);
          return import('https://www.gstatic.com/firebasejs/11.6.1/firebase-auth.js');
        })
        .then(module => {
          const { getAuth, signInAnonymously, signInWithCustomToken, onAuthStateChanged } = module;
          const auth = getAuth();
          onAuthStateChanged(auth, (user) => {
            if (user) {
              setUserId(user.uid);
            } else {
              if (initialAuthToken) {
                signInWithCustomToken(auth, initialAuthToken)
                  .then(() => console.log('Signed in with custom token'))
                  .catch(error => console.error('Error signing in with custom token:', error));
              } else {
                signInAnonymously(auth)
                  .then(() => console.log('Signed in anonymously'))
                  .catch(error => console.error('Error signing in anonymously:', error));
              }
            }
            setIsAuthReady(true);
          });
        })
        .catch(error => console.error('Failed to load Firebase modules:', error));
    } else {
      console.warn('Firebase config not found. Running without Firebase authentication.');
      setUserId('mock-user-id-' + Math.random().toString(36).substring(2, 9));
      setIsAuthReady(true);
    }

    // Load the pre-generated journey data from JSON
    setJourneyData(sampleJourneyData);
    setIsGeneratingConversation(false); // No longer generating, just loading
  }, []); // Empty dependency array ensures this runs once on mount

  const renderContent = () => {
    switch (activeSection) {
      case 'dashboard':
        const recentMessages = journeyData.filter(item => item.type === 'message').slice(-3).reverse();
        const latestMetrics = {
          hrv: { value: "65ms", trend: "up", change: "5%" },
          restingHR: { value: "58bpm", trend: "down", change: "3bpm" },
          glucoseAvg: { value: "95mg/dL", trend: "stable" }
        };
        return (
          <div className="p-6 text-gray-700">
            <h2 className="text-3xl font-semibold mb-4">Welcome, Rohan!</h2>
            <p className="text-lg mb-4">This is your personalized health dashboard. Here, you'll find an overview of your progress, key metrics, and upcoming activities.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300">
                <h3 className="text-xl font-medium mb-2 text-indigo-700">Current Health Snapshot</h3>
                <ul className="list-disc list-inside space-y-1 text-gray-600">
                  <li>HRV: <span className="font-semibold text-green-600">{latestMetrics.hrv.value} ({latestMetrics.hrv.trend === 'up' ? '↑' : '↓'}{latestMetrics.hrv.change})</span></li>
                  <li>Resting HR: <span className="font-semibold text-green-600">{latestMetrics.restingHR.value} ({latestMetrics.restingHR.trend === 'up' ? '↑' : '↓'}{latestMetrics.restingHR.change})</span></li>
                  <li>Glucose Avg: <span className="font-semibold text-green-600">{latestMetrics.glucoseAvg.value} ({latestMetrics.glucoseAvg.trend})</span></li>
                </ul>
                <p className="text-sm mt-3 text-gray-500">Last updated: {journeyData.length > 0 ? journeyData[journeyData.length - 1].timestamp.split(' ')[0] : 'N/A'}</p>
              </div>
              <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300">
                <h3 className="text-xl font-medium mb-2 text-indigo-700">Upcoming Activities</h3>
                <ul className="list-disc list-inside space-y-1 text-gray-600">
                  <li>Aug 22: Water Quality Test (Ruby)</li>
                  <li>Sept 5: VO2 Max Test (Advik)</li>
                  <li>Sept 28: Prenuvo MRI (Ruby)</li>
                </ul>
                <p className="text-sm mt-3 text-gray-500">Stay on track with your personalized plan!</p>
              </div>
              <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300">
                <h3 className="text-xl font-medium mb-2 text-indigo-700">Recent Communications</h3>
                {recentMessages.length > 0 ? (
                  recentMessages.map((msg, index) => (
                    <p key={index} className="text-gray-600 italic text-sm mb-1">
                      "{msg.content.length > 70 ? msg.content.substring(0, 70) + '...' : msg.content}" - {msg.sender} ({msg.timestamp.split(' ')[0]})
                    </p>
                  ))
                ) : (
                  <p className="text-gray-500">No recent messages yet.</p>
                )}
                <p className="text-sm mt-3 text-gray-500">See full chat history for details.</p>
              </div>
            </div>
          </div>
        );
      case 'journey':
        return (
          <div className="p-6 text-gray-700">
            <h2 className="text-3xl font-semibold mb-4">Your Health Journey Timeline</h2>
            <p className="text-lg mb-6">Visualize your progress, key decisions, and interventions over time.</p>
            {isGeneratingConversation ? (
              <div className="text-center py-10 text-xl text-indigo-600">
                <p>Loading journey data...</p>
                <div className="spinner mt-4"></div>
              </div>
            ) : (
              <div className="bg-white p-8 rounded-lg shadow-md overflow-y-auto max-h-[600px] border border-gray-200">
                {journeyData.length > 0 ? (
                  <div className="relative pl-6">
                    <div className="absolute left-0 top-0 bottom-0 w-1 bg-indigo-200 rounded-full"></div>
                    {journeyData.map((item, index) => (
                      <div key={index} className="mb-8 relative">
                        <div className="absolute -left-2 top-1 w-5 h-5 bg-indigo-600 rounded-full flex items-center justify-center text-white text-xs z-10">
                          {item.type === 'message' ? '💬' : '✨'}
                        </div>
                        <div className="ml-6 pb-4 border-b border-gray-100 last:border-b-0">
                          <p className="text-sm text-gray-500 mb-1">{item.timestamp}</p>
                          <h3 className="font-semibold text-lg text-gray-800">
                            {item.type === 'message' ? `${item.sender}:` : item.description}
                          </h3>
                          <p className="text-gray-700">{item.content || item.details}</p>
                          {item.decisionRationale && (
                            <div className="mt-2 p-3 bg-blue-50 rounded-md border border-blue-200 text-blue-700 text-sm">
                              <p className="font-medium">Rationale:</p>
                              <p>{item.decisionRationale}</p>
                            </div>
                          )}
                           {item.pillar && (
                            <p className="mt-1 text-xs text-gray-600">Pillar: {item.pillar}</p>
                           )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center text-gray-400 text-xl py-20">No journey data available yet.</div>
                )}
              </div>
            )}
            <style jsx>{`
              .spinner { border: 4px solid rgba(0, 0, 0, 0.1); border-left-color: #6366f1; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto; }
              @keyframes spin { to { transform: rotate(360deg); } }
            `}</style>
          </div>
        );
      case 'messages':
        return (
          <div className="p-6 text-gray-700">
            <h2 className="text-3xl font-semibold mb-4">Your Conversations</h2>
            <p className="text-lg mb-6">Here, you'll find all your WhatsApp-style communications with the Elyx team.</p>
            {isGeneratingConversation ? (
              <div className="text-center py-10 text-xl text-indigo-600">
                <p>Loading messages...</p>
                <div className="spinner mt-4"></div>
              </div>
            ) : (
              <div className="bg-white p-6 rounded-lg shadow-md overflow-y-auto max-h-[600px] flex flex-col-reverse">
                {journeyData.filter(item => item.type === 'message').reverse().map((msg, index) => (
                  <div key={index} className={`mb-4 p-3 rounded-lg max-w-[80%] ${msg.sender === 'Rohan' ? 'bg-blue-100 self-end text-right' : 'bg-gray-100 self-start text-left'}`}>
                    <p className="font-semibold text-sm mb-1">{msg.sender}</p>
                    <p className="text-gray-800">{msg.content}</p>
                    <p className="text-xs text-gray-500 mt-1">{msg.timestamp}</p>
                  </div>
                ))}
                <style jsx>{`
                  .spinner { border: 4px solid rgba(0, 0, 0, 0.1); border-left-color: #6366f1; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto; }
                  @keyframes spin { to { transform: rotate(360deg); } }
                `}</style>
              </div>
            )}
          </div>
        );
      case 'specialists':
        return (
          <div className="p-6 text-gray-700">
            <h2 className="text-3xl font-semibold mb-4">Elyx Health Specialists</h2>
            <p className="text-lg mb-6">Meet the team of experts guiding your health journey and review their direct communications.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300">
                <h3 className="text-xl font-medium mb-2 text-indigo-700">Dr. Warren <span className="text-sm text-gray-500">(Medical Strategist)</span></h3>
                <p className="text-gray-600 mb-3">**Role:** Physician and final clinical authority, interprets lab results, approves diagnostic strategies.<br/>**Voice:** Authoritative, precise, scientific.</p>
                <p className="text-sm text-gray-500"><a href="#" className="text-indigo-600 hover:underline">View Dr. Warren's Chats</a></p>
              </div>
              <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300">
                <h3 className="text-xl font-medium mb-2 text-indigo-700">Advik <span className="text-sm text-gray-500">(Performance Scientist)</span></h3>
                <p className="text-gray-600 mb-3">**Role:** Data analysis expert (wearables data), focuses on nervous system, sleep, cardiovascular training.<br/>**Voice:** Analytical, curious, pattern-oriented.</p>
                <p className="text-sm text-gray-500"><a href="#" className="text-indigo-600 hover:underline">View Advik's Chats</a></p>
              </div>
              <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300">
                <h3 className="text-xl font-medium mb-2 text-indigo-700">Carla <span className="text-sm text-gray-500">(Nutritionist)</span></h3>
                <p className="text-gray-600 mb-3">**Role:** Designs nutrition plans, analyzes food logs and CGM data, supplement recommendations.<br/>**Voice:** Practical, educational, focused on behavioral change.</p>
                <p className="text-sm text-gray-500"><a href="#" className="text-indigo-600 hover:underline">View Carla's Chats</a></p>
              </div>
              <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300">
                <h3 className="text-xl font-medium mb-2 text-indigo-700">Rachel <span className="text-sm text-gray-500">(PT / Physiotherapist)</span></h3>
                <p className="text-gray-600 mb-3">**Role:** Manages physical movement: strength training, mobility, injury rehabilitation.<br/>**Voice:** Direct, encouraging, focused on form and function.</p>
                <p className="text-sm text-gray-500"><a href="#" className="text-indigo-600 hover:underline">View Rachel's Chats</a></p>
              </div>
              <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300">
                <h3 className="text-xl font-medium mb-2 text-indigo-700">Dr. Evans <span className="text-sm text-gray-500">(Stress Management)</span></h3>
                <p className="text-gray-600 mb-3">**Role:** Provides tools and strategies for stress resilience and cognitive load management.<br/>**Voice:** Practical, insightful, calm (assumed based on context).</p>
                <p className="text-sm mt-3 text-gray-500"><a href="#" className="text-indigo-600 hover:underline">View Dr. Evans' Chats</a></p>
              </div>
              <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300">
                <h3 className="text-xl font-medium mb-2 text-indigo-700">Ruby <span className="text-sm text-gray-500">(Concierge)</span></h3>
                <p className="text-gray-600 mb-3">**Role:** Primary point of contact for logistics, scheduling, reminders, and follow-ups.<br/>**Voice:** Empathetic, organized, proactive.</p>
                 <p className="text-sm mt-3 text-gray-500"><a href="#" className="text-indigo-600 hover:underline">View Ruby's Chats</a></p>
              </div>
              <div className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition-shadow duration-300">
                <h3 className="text-xl font-medium mb-2 text-indigo-700">Neel <span className="text-sm text-gray-500">(Concierge Lead)</span></h3>
                <p className="text-gray-600 mb-3">**Role:** Senior leader, major strategic reviews, de-escalates frustrations, connects work to goals.<br/>**Voice:** Strategic, reassuring, focused on the big picture.</p>
                 <p className="text-sm mt-3 text-gray-500"><a href="#" className="text-indigo-600 hover:underline">View Neel's Chats</a></p>
              </div>
            </div>
          </div>
        );
      case 'decision-query':
        return (
          <div className="p-6 text-gray-700">
            <h2 className="text-3xl font-semibold mb-4">Ask About a Decision</h2>
            <p className="text-lg mb-6">Have a question about a specific recommendation, medication, or plan change? Type it below and our AI will provide the rationale.</p>
            <div className="bg-white p-6 rounded-lg shadow-md">
              <textarea className="w-full p-4 border border-gray-300 rounded-lg mb-4 focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all duration-200" rows="5" placeholder="E.g., Why was the blue-light blocking glasses suggested?" value={decisionQuery} onChange={(e) => setDecisionQuery(e.target.value)} disabled={isLoadingDecision}></textarea>
              <button className={`w-full bg-indigo-600 text-white py-3 px-6 rounded-lg font-semibold text-lg shadow-md transition-all duration-300 ${isLoadingDecision ? 'opacity-70 cursor-not-allowed' : 'hover:bg-indigo-700 hover:shadow-lg'}`} onClick={handleDecisionQuery} disabled={isLoadingDecision}>
                {isLoadingDecision ? 'Asking AI...' : 'Ask Elyx AI'}
              </button>
              {decisionResponse && (
                <div className="mt-6 p-4 bg-indigo-50 rounded-lg border border-indigo-200 text-indigo-800 break-words">
                  <p className="font-semibold mb-2">Elyx AI's Explanation:</p>
                  <p>{decisionResponse}</p>
                </div>
              )}
            </div>
          </div>
        );
      case 'profile':
        return (
          <div className="p-6 text-gray-700">
            <h2 className="text-3xl font-semibold mb-4">Rohan's Profile</h2>
            <div className="bg-white p-6 rounded-lg shadow-md">
              <p className="text-lg font-medium text-indigo-700 mb-2">Personal Details:</p>
              <ul className="list-disc list-inside space-y-1 text-gray-600 mb-4">
                <li>**Preferred Name:** Rohan Patel</li>
                <li>**Age:** 46</li>
                <li>**Gender:** Male</li>
                <li>**Primary Residence:** Singapore</li>
                <li>**Occupation:** Regional Head of Sales (FinTech)</li>
              </ul>
              <p className="text-lg font-medium text-indigo-700 mb-2">Core Goals:</p>
              <ul className="list-disc list-inside space-y-1 text-gray-600 mb-4">
                <li>Reduce risk of heart disease (by Dec 2026)</li>
                <li>Enhance cognitive function and focus (by June 2026)</li>
                <li>Implement annual full-body health screenings (starting Nov 2025)</li>
              </ul>
              <p className="text-lg font-medium text-indigo-700 mb-2">Behavioral Insights:</p>
              <ul className="list-disc list-inside space-y-1 text-gray-600 mb-4">
                <li>Analytical, driven, values efficiency and evidence-based approaches.</li>
                <li>Highly motivated but time-constrained. Needs clear, concise plans.</li>
                <li>Wife supportive, 2 young kids, employs a cook.</li>
              </ul>
              <p className="text-lg font-medium text-indigo-700 mb-2">Tech Stack:</p>
              <ul className="list-disc list-inside space-y-1 text-gray-600">
                <li>Garmin watch (used for runs), considering Oura ring/Whoop.</li>
                <li>Willing to enable full data sharing.</li>
              </ul>
            </div>
            {isAuthReady && userId && (
              <div className="mt-6 p-4 bg-blue-50 rounded-lg text-blue-800 break-words">
                <p className="font-semibold">Your User ID:</p>
                <p className="text-sm">{userId}</p>
              </div>
            )}
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 font-sans text-gray-900 flex flex-col">
      <script src="https://cdn.tailwindcss.com"></script>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
      <style>
        {` body { font-family: 'Inter', sans-serif; } `}
      </style>
      <nav className="bg-indigo-800 p-4 shadow-md">
        <div className="container mx-auto flex justify-between items-center flex-wrap">
          <div className="text-white text-2xl font-bold rounded-md px-3 py-1 bg-indigo-600">Elyx Life</div>
          <div className="flex space-x-4 mt-2 md:mt-0">
            <NavItem label="Dashboard" section="dashboard" activeSection={activeSection} setActiveSection={setActiveSection} />
            <NavItem label="Journey" section="journey" activeSection={activeSection} setActiveSection={setActiveSection} />
            <NavItem label="Messages" section="messages" activeSection={activeSection} setActiveSection={setActiveSection} />
            <NavItem label="Specialists" section="specialists" activeSection={activeSection} setActiveSection={setActiveSection} />
            <NavItem label="Decision Query" section="decision-query" activeSection={activeSection} setActiveSection={setActiveSection} />
            <NavItem label="Profile" section="profile" activeSection={activeSection} setActiveSection={setActiveSection} />
          </div>
        </div>
      </nav>
      <main className="flex-grow container mx-auto px-4 py-8">{renderContent()}</main>
      <footer className="bg-indigo-800 p-4 text-white text-center text-sm mt-8">
        <div className="container mx-auto">&copy; {new Date().getFullYear()} Elyx Life. All rights reserved.</div>
      </footer>
    </div>
  );
}

export default App;

