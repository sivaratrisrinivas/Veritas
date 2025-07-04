import os
import requests
import re
from flask import Flask, jsonify, request, render_template
from dotenv import load_dotenv
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# Load environment variables from the .env file
load_dotenv()

# Initialize the Flask application
app = Flask(__name__)

# --- CONFIGURATION ---
# Define the specific topics this proof of concept will focus on.
ALLOWED_TOPICS = {'Health', 'Technology', 'Finance'}

# Define the weights for the final Veracity Score calculation.
AUTHORITY_WEIGHT = 0.70
CITATION_WEIGHT = 0.30

# A robust, static list of globally reputable domains for citation checking.
# This is more reliable than a dynamic list for a proof of concept.
STATIC_CITATION_LIST = [
    'nature.com', 'sciencemag.org', 'thelancet.com', 'nejm.org', # Science Journals
    'reuters.com', 'apnews.com', 'bbc.com', # News Agencies
    'nih.gov', 'cdc.gov', 'who.int', # Health Orgs
    'wsj.com', 'bloomberg.com', # Finance News
    'github.com', 'stackoverflow.com' # Tech Resources
]


# --- DYNAMIC FUNCTIONS ---

def get_query_topic(query, api_key):
    """Asks Exa's /answer endpoint to classify the query's topic."""
    prompt = (f"What is the single primary topic for the search query: '{query}'? "
              f"Choose from Health, Technology, or Finance. Respond with only the single topic word.")
    try:
        response = requests.post(
            "https://api.exa.ai/answer",
            json={"query": prompt},
            headers={"accept": "application/json", "x-api-key": api_key}
        )
        response.raise_for_status()
        # Capitalize the topic for consistent matching with our ALLOWED_TOPICS set.
        topic = response.json().get('answer', 'Default').strip().capitalize()
        return topic
    except requests.RequestException:
        return "Default"

def get_dynamic_sources(topic, api_key):
    """Asks Exa to define the most authoritative sources for a given topic."""
    prompt = (f"List the top 5 most authoritative website domains for the topic of '{topic}'. "
              f"Return only a comma-separated list of domains, like 'domain1.com, domain2.net'.")
    try:
        response = requests.post(
            "https://api.exa.ai/answer",
            json={"query": prompt},
            headers={"accept": "application/json", "x-api-key": api_key}
        )
        response.raise_for_status()
        answer_text = response.json().get('answer', '')
        # Use regex to find all domain-like strings in the AI's response.
        domains = re.findall(r'[\w-]+\.(?:com|org|net|gov|edu|io|co\.uk)', answer_text.lower())
        # Sanity check: ensure we got at least 2 valid domains before returning.
        return {domain: 85 for domain in domains} if len(domains) > 1 else {}
    except requests.RequestException:
        return {}


# --- CORE SCORING LOGIC ---

def get_authority_score(url, trusted_list):
    """Calculates authority score, correctly handling subdomains."""
    if not url:
        return 0
    domain = urlparse(url).netloc.replace('www.', '').lower()
    for trusted_domain, score in trusted_list.items():
        if domain.endswith(trusted_domain):
            return score
    # Give a small bonus to any .gov or .edu site, as they are generally trustworthy.
    if domain.endswith('.gov') or domain.endswith('.edu'):
        return 75
    return 50

def get_citation_score(url, reputable_list):
    """Visits a URL and counts how many links go to reputable domains."""
    if not url:
        return 0
    try:
        page_response = requests.get(url, timeout=5)
        soup = BeautifulSoup(page_response.content, 'html.parser')
        reputable_links_found = 0
        for link in soup.find_all('a', href=True):
            link_domain = urlparse(link['href']).netloc.replace('www.', '').lower()
            for reputable_site in reputable_list:
                if link_domain.endswith(reputable_site):
                    reputable_links_found += 1
                    break  # Move to the next link once a match is found to avoid double counting.
        return min(reputable_links_found, 10)
    except requests.RequestException:
        return 0

def calculate_veracity_score(authority_score, citation_score):
    """Calculates the final weighted score from 0 to 100."""
    # Normalize citation score (0-10) to be on the same scale as authority score (0-100).
    normalized_citation_score = citation_score * 10
    final_score = (authority_score * AUTHORITY_WEIGHT) + (normalized_citation_score * CITATION_WEIGHT)
    return int(final_score)


# --- FLASK ROUTES ---

@app.route('/')
def home():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/search')
def search_exa():
    """The main API endpoint that powers the Veritas engine."""
    query = request.args.get('q')
    if not query:
        return jsonify({"error": "Please provide a search query using ?q="}), 400

    api_key = os.getenv("EXA_API_KEY")
    topic = get_query_topic(query, api_key)

    # Check if the detected topic is on our supported list.
    if topic not in ALLOWED_TOPICS:
        error_message = f"Veritas is currently optimized for: {', '.join(ALLOWED_TOPICS)}. Your query was detected as '{topic}'."
        return jsonify({"error": error_message}), 400

    # Proceed with the dynamic scoring process for allowed topics.
    trusted_list = get_dynamic_sources(topic, api_key)
    citation_list = STATIC_CITATION_LIST # Use the reliable static list for citations.

    # Enhance the user's query to prioritize results from our trusted sources.
    site_operators = " OR ".join([f"site:{domain}" for domain in trusted_list.keys()])
    final_query = f"{query} ({site_operators})" if site_operators else query

    # Perform the main search.
    response = requests.post(
        "https://api.exa.ai/search",
        json={"query": final_query, "numResults": 5},
        headers={"accept": "application/json", "x-api-key": api_key}
    )
    results = response.json().get('results', [])

    # Score each result and add the new data.
    for result in results:
        result_url = result.get('url')
        authority = get_authority_score(result_url, trusted_list)
        citations = get_citation_score(result_url, citation_list)
        result['veracityScore'] = calculate_veracity_score(authority, citations)
        result['topic'] = topic

    return jsonify(results)


if __name__ == '__main__':
    # Runs the Flask development server.
    app.run(debug=True, port=5000)
