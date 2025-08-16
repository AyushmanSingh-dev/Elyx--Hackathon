
# Backend/llm_service.py
from flask import Flask, request, jsonify
from flask_cors import CORS # Used to allow requests from your frontend
import json
import os # To potentially get API key from environment variables (though no longer used for LLM)

app = Flask(__name__)
CORS(app) # Enable CORS for all routes in your Flask app

# --- IMPORTANT ---
# This backend now uses a simple keyword-based response system instead of an external LLM API.
# The API_KEY and GEMINI_API_URL are no longer used for generating responses.

# Define a dictionary of keyword-based responses
KEYWORD_RESPONSES = {
    "poor digestion": "For poor digestion, consider incorporating more fiber into your diet through fruits, vegetables, and whole grains. Probiotics might also be helpful. If symptoms persist, consult a nutritionist like Carla.",
    "apo b": "ApoB is a key marker for cardiovascular risk. To lower it, focus on reducing saturated fats, increasing soluble fiber, and incorporating regular exercise. Your personalized plan likely includes dietary adjustments from Carla and exercise protocols from Rachel.",
    "apob": "ApoB is a key marker for cardiovascular risk. To lower it, focus on reducing saturated fats, increasing soluble fiber, and incorporating regular exercise. Your personalized plan likely includes dietary adjustments from Carla and exercise protocols from Rachel.",
    "travel protocol": "The travel protocol is designed to minimize jet lag and maintain your health routine during business trips. It includes precise light exposure schedules, hydration plans, and in-flight mobility routines. Advik and Rachel typically design these.",
    "couch stretch": "The couch stretch was recommended to address hip flexor tightness, a common cause of lower back pain, often exacerbated by prolonged sitting during travel. It's a foundational mobility exercise from Rachel to improve your structural health.",
    "hrv": "Heart Rate Variability (HRV) is a key indicator of your autonomic nervous system's balance and recovery. A consistent upward trend in HRV indicates improved resilience. Factors like sleep, stress, and exercise consistency significantly impact it.",
    "stress": "For stress management, Dr. Evans often recommends techniques like mindful breathing exercises and structured 'shutdown rituals' to help you disengage after demanding periods. Consistent sleep and proper nutrition also play a vital role.",
    "exercise": "Your exercise plan is dynamically updated based on your progress and goals. It typically includes a mix of Zone 2 cardio for autonomic health and structured strength training for overall fitness and longevity. Rachel and Advik oversee this.",
    "sleep": "Improving sleep quality is crucial. Strategies include optimizing your sleep environment, consistent sleep schedule, and avoiding late-night heavy meals or blue light exposure. Tracking sleep with devices like Whoop helps monitor progress.",
    "default": "I'm a simple keyword agent. I can explain decisions related to digestion, ApoB, travel protocols, specific exercises like the couch stretch, or general topics like HRV, stress, exercise, and sleep. Please try rephrasing your question with these keywords."
}

# This function now uses keyword matching instead of an external API call
def generate_text_response(prompt, chat_history=None):
    """
    Generates a keyword-based response.
    Args:
        prompt (str): The user's input prompt.
        chat_history (list): Not used for response generation in this simple agent.
    Returns:
        str: The generated text response based on keywords.
    """
    prompt_lower = prompt.lower()
    for keyword, response in KEYWORD_RESPONSES.items():
        if keyword != "default" and keyword in prompt_lower:
            return response
    return KEYWORD_RESPONSES["default"]


# This function now uses the keyword-based agent
def explain_decision_ai(query, journey_data):
    """
    Explains a decision based on the query using the keyword-based agent.
    Args:
        query (str): The user's question about a decision.
        journey_data (list): Not directly used for response generation in this simple agent.
    Returns:
        str: Keyword-based explanation.
    """
    return generate_text_response(query)

# --- Flask API Endpoints ---
@app.route('/api/generate-message', methods=['POST'])
def api_generate_message():
    data = request.json
    prompt = data.get('prompt')
    chat_history = data.get('chatHistory', []) # chat_history is received but not used by this simple agent
    if not prompt:
        return jsonify({"error": "Prompt is required."}), 400
    message = generate_text_response(prompt, chat_history) # Pass chat_history, though generate_text_response ignores it
    return jsonify({"message": message})

@app.route('/api/explain-decision', methods=['POST'])
def api_explain_decision():
    data = request.json
    query = data.get('query')
    journey_data = data.get('journeyData', []) # journey_data is received but not used by this simple agent
    if not query:
        return jsonify({"error": "Query is required."}), 400
    explanation = explain_decision_ai(query, journey_data) # Pass journey_data, though explain_decision_ai ignores it
    return jsonify({"explanation": explanation})

if __name__ == '__main__':
    # This block is for local testing. Render will use Gunicorn to run the app.
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
