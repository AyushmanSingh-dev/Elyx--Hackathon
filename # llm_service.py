# llm_service.py (conceptual backend)
import requests
import json
import time

# --- IMPORTANT ---
# For the hackathon environment, leave API_KEY as an empty string.
# The Canvas environment will automatically provide it at runtime.
# If running locally outside Canvas, you would replace this with your actual API key.
API_KEY = ""
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent"

def _make_api_call(url, payload, headers, retries=5, backoff_factor=1.0):
    """Handles API calls with exponential backoff."""
    for i in range(retries):
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429: # Too Many Requests
                sleep_time = backoff_factor * (2 ** i) + (time.time() % 1)
                print(f"Rate limit hit. Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            else:
                raise e
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            raise e
    raise Exception(f"Failed after {retries} retries: {url}")


def generate_text_response(prompt, chat_history=None):
    """
    Generates a text response using the Gemini API.
    Args:
        prompt (str): The user's input prompt.
        chat_history (list): Optional list of previous chat messages for context.
    Returns:
        str: The generated text response.
    """
    if chat_history is None:
        chat_history = []

    # Add the current user prompt to chat history
    chat_history.append({"role": "user", "parts": [{"text": prompt}]})

    payload = {"contents": chat_history}
    headers = {"Content-Type": "application/json"}

    api_url_with_key = f"{GEMINI_API_URL}?key={API_KEY}" if API_KEY else GEMINI_API_URL

    try:
        result = _make_api_call(api_url_with_key, payload, headers)
        if result.get("candidates") and result["candidates"][0].get("content") and result["candidates"][0]["content"].get("parts"):
            return result["candidates"][0]["content"]["parts"][0]["text"]
        else:
            print(f"Unexpected API response structure: {result}")
            return "Error: Could not generate response."
    except Exception as e:
        print(f"Error in generate_text_response: {e}")
        return "Error: Failed to communicate with AI model."


def explain_decision_ai(query, journey_data):
    """
    Explains a decision based on the query and existing journey data using LLM.
    Args:
        query (str): The user's question about a decision.
        journey_data (list): The full historical journey data for context.
    Returns:
        str: AI-generated explanation.
    """
    context_str = json.dumps(journey_data, indent=2) # Stringify for LLM context
    prompt = f"""
    Rohan Patel is reviewing his health journey. He has a question about a decision made in his plan.
    His question is: "{query}"

    Here is a summary of his health journey and relevant events/messages so far:
    {context_str}

    Please act as an Elyx AI Concierge. Based on the provided journey data and understanding Rohan's profile (analytical, data-driven, values efficiency), explain the rationale behind the decision in a clear, concise, and professional manner. If the specific decision isn't clear from the provided context, state that and provide a general explanation of how such decisions are made. Focus on linking the decision to Rohan's goals or observed health data.
    """
    return generate_text_response(prompt)

# Example Usage (for local testing of the Python script)
if __name__ == "__main__":
    print("--- Testing LLM Service ---")

    # Dummy data for testing explain_decision_ai locally
    dummy_journey_for_test = [
        {"type": "message", "sender": "Rohan", "timestamp": "2025-08-01 10:00", "content": "My Garmin HR is off."},
        {"type": "message", "sender": "Advik", "timestamp": "2025-08-01 10:15", "content": "Let's investigate. We need more granular data."},
        {"type": "event", "eventId": "whoop_suggested", "timestamp": "2025-08-05 11:00", "description": "Whoop strap recommended", "decisionRationale": "To get high-fidelity data on autonomic nervous system and recovery, addressing inaccurate Garmin readings."}
    ]

    print("\nAttempting to explain a decision:")
    explanation = explain_decision_ai("Why was the Whoop strap suggested?", dummy_journey_for_test)
    print(f"Decision Explanation: {explanation}")

    print("\nAttempting to generate a simple chat message:")
    simple_chat_history = []
    simple_chat_history.append({"role": "user", "parts": [{"text": "What are your immediate recommendations for improving sleep?"}]})
    chat_response = generate_text_response("Based on Rohan's profile (high stress, analytical), what's a simple, actionable sleep recommendation?", chat_history=simple_chat_history)
    print(f"Chat Response: {chat_response}")
