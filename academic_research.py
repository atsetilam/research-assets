import requests
import time
import pandas as pd

# CONFIGURATION
# -----------------------------
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
LANGUAGES = {
    "CUDA": '"CUDA" | "NVIDIA GPU" | "cuBLAS"',  # Boolean OR logic
    "HIP": '"HIP" | "ROCm" | "AMD GPU" | "MI250"',
    "SYCL": '"SYCL" | "OneAPI" | "DPC++" | "Intel GPU"',
    "OpenCL": '"OpenCL" | "SPIR-V"'
}

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

# FUNCTION TO GET COUNTS
# -----------------------------
def get_paper_count(query, year, api_key=None):
    """
    Fetches the total number of papers for a given query and year.
    """
    params = {
        'query': query,
        'year': str(year),
        'limit': 1,  # We only need the metadata 'total', not the papers
        'fields': 'title'
    }
    
    headers = {}
    if api_key:
        headers = {'x-api-key': api_key}

    try:
        response = requests.get(API_URL, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('total', 0)
        elif response.status_code == 429:
            print("  [!] Rate limit hit. Waiting 2 seconds...")
            time.sleep(2)
            return get_paper_count(query, year, api_key) # Retry
        else:
            print(f"  [!] Error {response.status_code}: {response.text}")
            return 0
            
    except Exception as e:
        print(f"  [!] Exception: {e}")
        return 0

# MAIN EXECUTION
# -----------------------------
print(f"Starting Research Layer 3: Citation Analysis...")
results = []

for lang, query in LANGUAGES.items():
    print(f"\nProcessing {lang}...")
    for year in YEARS:
        count = get_paper_count(query, year)
        print(f"  - {year}: {count} papers")
        
        results.append({
            "Language": lang,
            "Year": year,
            "Count": count
        })
        
        # Respect API rate limits (1 req/sec for unauthenticated users)
        time.sleep(1.1) 

# SAVE RESULTS
# -----------------------------
df = pd.DataFrame(results)
print("\n--- Summary Table ---")
print(df.pivot(index='Year', columns='Language', values='Count'))

# Optional: Save to CSV
# df.to_csv("hpc_language_citations.csv", index=False)