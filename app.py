import os
import requests
import re
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from urllib.parse import urlparse
from bs4 import BeautifulSoup

load_dotenv()
app = Flask(__name__)

# --- CONFIGURATION ---
AUTHORITY_WEIGHT = 0.70
CITATION_WEIGHT = 0.30

# --- STATIC SAFETY NETS (NEW) ---
# Our reliable, hardcoded lists to use as a fallback.
STATIC_TOPIC_SOURCES = {
    'Health': { 'mayoclinic.org': 95, 'webmd.com': 80, 'healthline.com': 85, 'nih.gov': 98, 'cdc.gov': 98 },
    'Technology': { 'techcrunch.com': 85, 'wired.com': 80, 'theverge.com': 85, 'stackoverflow.com': 90, 'github.com': 80 },
    'Finance': { 'bloomberg.com': 90, 'wsj.com': 90, 'reuters.com': 85, 'forbes.com': 75 },
    'Default': { 'wikipedia.org': 70, 'reuters.com': 80, 'apnews.com': 80 }
}
# A single, high-quality citation list is more robust than a dynamic one.
STATIC_CITATION_LIST = [
    'nature.com', 'sciencemag.org', 'thelancet.com', 'nejm.org', # Science Journals
    'reuters.com', 'apnews.com', 'bbc.com', # News Agencies
    'nih.gov', 'cdc.gov', 'who.int' # Health Orgs
]

# --- DYNAMIC FUNCTIONS ---
def get_query_topic(query, api_key):
    prompt = (f"What is the single primary topic for the search query: '{query}'? Respond with only the single topic word.")
    try:
        response = requests.post("https://api.exa.ai/answer", json={"query": prompt}, headers={"accept": "application/json", "x-api-key": api_key})
        response.raise_for_status()
        return response.json().get('answer', 'Default').strip()
    except requests.RequestException:
        return "Default"

def get_dynamic_sources(topic, api_key):
    prompt = (f"List the top 5 most authoritative website domains for the topic of '{topic}'. Return only a comma-separated list.")
    try:
        response = requests.post("https://api.exa.ai/answer", json={"query": prompt}, headers={"accept": "application/json", "x-api-key": api_key})
        response.raise_for_status()
        answer_text = response.json().get('answer', '')
        print(f"--- LOG: [get_dynamic_sources] Raw answer: '{answer_text}' ---")
        domains = re.findall(r'[\w-]+\.(?:com|org|net|gov|edu|io|co\.uk)', answer_text.lower())
        # Sanity check: ensure we got at least 2 domains.
        return {domain: 85 for domain in domains} if len(domains) > 1 else {}
    except requests.RequestException:
        return {}

# --- CORE LOGIC ---
def get_authority_score(url, trusted_list):
    if not url: return 0
    domain = urlparse(url).netloc.replace('www.', '').lower()
    for trusted_domain, score in trusted_list.items():
        if domain.endswith(trusted_domain):
            return score
    # NEW: Bonus points for any .gov or .edu site
    if domain.endswith('.gov') or domain.endswith('.edu'):
        return 75
    return 50

def get_citation_score(url, reputable_list):
    if not url: return 0
    try:
        page_response = requests.get(url, timeout=5)
        soup = BeautifulSoup(page_response.content, 'html.parser')
        reputable_links_found = 0
        for link in soup.find_all('a', href=True):
            link_domain = urlparse(link['href']).netloc.replace('www.', '').lower()
            for reputable_site in reputable_list:
                if link_domain.endswith(reputable_site):
                    reputable_links_found += 1
                    break
        return min(reputable_links_found, 10)
    except requests.RequestException:
        return 0

def calculate_veracity_score(authority_score, citation_score):
    normalized_citation_score = citation_score * 10
    final_score = (authority_score * AUTHORITY_WEIGHT) + (normalized_citation_score * CITATION_WEIGHT)
    return int(final_score)

@app.route('/search')
def search_exa():
    query = request.args.get('q')
    if not query: return jsonify({"error": "Query not provided"}), 400

    api_key = os.getenv("EXA_API_KEY")
    topic = get_query_topic(query, api_key)
    print(f"--- LOG: Detected Topic: '{topic}' ---")

    # --- HYBRID STRATEGY IN ACTION ---
    trusted_list = get_dynamic_sources(topic, api_key)
    if not trusted_list:
        print("--- LOG: Dynamic source generation failed or was empty. Falling back to static lists. ---")
        trusted_list = STATIC_TOPIC_SOURCES.get(topic, STATIC_TOPIC_SOURCES['Default'])
    
    # Use the single, high-quality static list for citations
    citation_list = STATIC_CITATION_LIST
    
    print(f"--- LOG: Using trusted sources for scoring: {trusted_list} ---")
    
    site_operators = " OR ".join([f"site:{domain}" for domain in trusted_list.keys()])
    final_query = f"{query} ({site_operators})" if site_operators else query
    print(f"--- LOG: Final search query: '{final_query}' ---")

    response = requests.post("https://api.exa.ai/search", json={"query": final_query, "numResults": 5}, headers={"accept": "application/json", "x-api-key": api_key})
    results = response.json().get('results', [])

    for result in results:
        result_url = result.get('url')
        authority = get_authority_score(result_url, trusted_list)
        citations = get_citation_score(result_url, citation_list)
        # FINAL VALIDATION LOG
        print(f"--- LOG: Scoring '{result_url}' | Authority: {authority}, Citations: {citations} ---")
        result['veracityScore'] = calculate_veracity_score(authority, citations)
        result['topic'] = topic

    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, port=5000)