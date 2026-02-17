import requests
import json
import time

GITHUB_TOKEN = "{YOUR_GITHUB_TOKEN_HERE}"

def graphql_search(query):
    """Search repositories using GraphQL"""
    url = "https://api.github.com/graphql"
    
    graphql_query = f'''
    {{
      search(query: "{query}", type: REPOSITORY, first: 1) {{
        repositoryCount
      }}
    }}
    '''
    
    headers = {
        "Authorization": f"bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, json={"query": graphql_query}, headers=headers)
    return response.json()

def rest_code_search(query):
    """Search code using REST API"""
    url = f"https://api.github.com/search/code?q={query}&per_page=1"
    
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return {"total_count": response.json()["total_count"]}
    else:
        return {"error": response.text}

# Repository searches
print("=" * 60)
print("REPOSITORY SEARCHES (GraphQL)")
print("=" * 60)

repo_searches = {
    "CUDA language": "language:CUDA",
    "C++ with cuda in name": "cuda language:C++",
    "Repos with .cu files": "extension:cu",
    "Repos with .cl files": "extension:cl",
    "HIP in code": "hipLaunchKernelGGL",
    "SYCL in code": "sycl::queue",
    "CUDA topic": "topic:cuda",
    "OpenCL topic": "topic:opencl",
    "HIP topic": "topic:hip",
    "SYCL topic": "topic:sycl",
}

for name, query in repo_searches.items():
    result = graphql_search(query)
    if "data" in result and "search" in result["data"]:
        count = result["data"]["search"]["repositoryCount"]
        print(f"{name:30} {count:>10,}")
    else:
        print(f"{name:30} ERROR: {result}")
    time.sleep(1)  # Rate limiting

# Code searches
print("\n" + "=" * 60)
print("CODE SEARCHES (REST API)")
print("=" * 60)

code_searches = {
    "CUDA kernel calls": "__global__",
    "OpenCL kernel calls": "clCreateKernel",
    "HIP kernel calls": "hipLaunchKernelGGL",
    "SYCL queue usage": "sycl::queue",
}

for name, query in code_searches.items():
    result = rest_code_search(query)
    if "total_count" in result:
        print(f"{name:30} {result['total_count']:>10,}")
    else:
        error_msg = result.get('error', 'Unknown error')
        print(f"{name:30} ERROR: {error_msg}")
    time.sleep(2)  # REST API has stricter rate limits