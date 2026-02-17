import requests
import time
import json
import os
import sys

# ==========================================
# CONFIGURATION
# ==========================================
GITHUB_TOKEN = "{YOUR_GITHUB_TOKEN_HERE}" 
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}
CHECKPOINT_FILE = "cuda_research_checkpoint.json"

def generate_overnight_size_bins():
    """Generates ~2,100 ultra-fine-grained size bins."""
    bins = []
    for i in range(0, 5000, 5): bins.append(f"{i}..{i+4}")
    for i in range(5000, 15000, 20): bins.append(f"{i}..{i+19}")
    for i in range(15000, 50000, 100): bins.append(f"{i}..{i+99}")
    for i in range(50000, 100000, 500): bins.append(f"{i}..{i+499}")
    for i in range(100000, 384000, 2000): bins.append(f"{i}..{i+1999}")
    bins.append(">384000")
    return bins

SIZE_BINS = generate_overnight_size_bins()

# ==========================================
# CHECKPOINT LOGIC
# ==========================================
def save_checkpoint(phase, last_bin_idx, set_a, set_b):
    """Saves the current progress to a JSON file."""
    state = {
        "phase": phase,                   # "A" or "B"
        "last_bin_idx": last_bin_idx,     # The index of the bin we just finished
        "set_a": list(set_a),             # Convert sets to lists for JSON serialization
        "set_b": list(set_b)
    }
    # Write to a temporary file first, then rename, to prevent corruption if the script
    # crashes exactly while writing the JSON file.
    temp_file = CHECKPOINT_FILE + ".tmp"
    with open(temp_file, "w") as f:
        json.dump(state, f)
    os.replace(temp_file, CHECKPOINT_FILE)

def load_checkpoint():
    """Loads the checkpoint file if it exists."""
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r") as f:
                state = json.load(f)
                # Convert the lists back to Python sets
                state["set_a"] = set(state["set_a"])
                state["set_b"] = set(state["set_b"])
                return state
        except Exception as e:
            print(f"  [!] Failed to load checkpoint: {e}")
            return None
    return None

def prompt_resume(state):
    """Asks the user whether to resume or start fresh."""
    print("\n" + "="*50)
    print("⚠️  CHECKPOINT FOUND ⚠️")
    print(f"Phase interrupted: {state['phase']} (Completed bin index: {state['last_bin_idx']})")
    print(f"Partial data saved - Set A: {len(state['set_a'])} repos | Set B: {len(state['set_b'])} repos")
    print("="*50)
    
    while True:
        choice = input("Do you want to resume from this checkpoint? (y/n): ").strip().lower()
        if choice == 'y':
            return True
        elif choice == 'n':
            print("Starting fresh. Previous checkpoint will be overwritten.")
            return False
        else:
            print("Please enter 'y' or 'n'.")

# ==========================================
# CORE EXECUTION WITH RESUME SUPPORT
# ==========================================
def fetch_repositories(base_query, phase_name, start_idx, current_set, other_set):
    total_bins = len(SIZE_BINS)
    
    for idx in range(start_idx, total_bins):
        size_bin = SIZE_BINS[idx]
        query = f'"{base_query}" size:{size_bin}'
        print(f"[{idx+1}/{total_bins}] Phase {phase_name} - Fetching: {query}")
        
        page = 1
        while True:
            url = f"https://api.github.com/search/code?q={query}&per_page=100&page={page}"
            try:
                response = requests.get(url, headers=HEADERS)
                
                if response.status_code == 403:
                    print("  -> Rate limit hit. Sleeping for 65 seconds...")
                    time.sleep(65)
                    continue
                
                if response.status_code != 200:
                    print(f"  -> Error {response.status_code}: {response.text}")
                    break
                    
                data = response.json()
                
                if page == 1 and data.get("total_count", 0) >= 1000:
                    print(f"  [WARNING] Bin {size_bin} returned 1000+ results! Density is critically high.")
                    
                items = data.get("items", [])
                if not items:
                    break
                    
                for item in items:
                    current_set.add(item["repository"]["full_name"])
                    
                if len(items) < 100:
                    break 
                    
                page += 1
                time.sleep(6.5) 
                
            except Exception as e:
                # Catch unexpected network drops without crashing the whole script
                print(f"  [!] Unexpected network error: {e}. Retrying in 30 seconds...")
                time.sleep(30)
                # Does not increment `page`, so the loop will re-try the failed page
                continue
                
        # --- SAVE CHECKPOINT AFTER EVERY SUCCESSFUL BIN ---
        if phase_name == "A":
            save_checkpoint("A", idx, current_set, other_set)
        else:
            save_checkpoint("B", idx, other_set, current_set)
            
    return current_set

# ==========================================
# MAIN ROUTINE
# ==========================================
if __name__ == "__main__":
    print(f"Generated {len(SIZE_BINS)} micro-bins for an overnight run.")
    
    # 1. Initialize Default State
    start_phase = "A"
    start_idx_a = 0
    start_idx_b = 0
    set_a_cuda = set()
    set_b_hip = set()
    
    # 2. Check for existing checkpoint
    existing_state = load_checkpoint()
    
    if existing_state:
        if prompt_resume(existing_state):
            # Load the partial data
            set_a_cuda = existing_state["set_a"]
            set_b_hip = existing_state["set_b"]
            start_phase = existing_state["phase"]
            
            # If it crashed in phase A, resume A from the NEXT bin.
            if start_phase == "A":
                start_idx_a = existing_state["last_bin_idx"] + 1
                start_idx_b = 0
            # If it crashed in phase B, phase A is 100% done. Resume B from the NEXT bin.
            elif start_phase == "B":
                start_idx_a = len(SIZE_BINS) # Skip A completely
                start_idx_b = existing_state["last_bin_idx"] + 1
        else:
            # User chose 'n', delete the old file so we start completely clean
            os.remove(CHECKPOINT_FILE)
            
    # 3. Execute Phase A
    if start_idx_a < len(SIZE_BINS):
        print("\n--- STEP 1: Fetching Set A (cudaMalloc) ---")
        try:
            set_a_cuda = fetch_repositories("cudaMalloc", "A", start_idx_a, set_a_cuda, set_b_hip)
        except KeyboardInterrupt:
            print("\n[!] Script manually stopped by user. Progress saved.")
            sys.exit(0)
    
    # 4. Execute Phase B
    if start_idx_b < len(SIZE_BINS):
        print("\n--- STEP 2: Fetching Set B (hip_runtime.h) ---")
        try:
            # We pass set_a_cuda so it can be preserved in the JSON when B saves its checkpoints
            set_b_hip = fetch_repositories("hip_runtime.h", "B", start_idx_b, set_b_hip, set_a_cuda)
        except KeyboardInterrupt:
            print("\n[!] Script manually stopped by user. Progress saved.")
            sys.exit(0)
            
    # 5. Calculate Final Result
    print("\n--- STEP 3: Calculating Pure CUDA Lock-in ---")
    pure_cuda_repos = set_a_cuda - set_b_hip
    hybrid_repos = set_a_cuda.intersection(set_b_hip)
    
    print(f"Total Repositories using cudaMalloc: {len(set_a_cuda)}")
    print(f"Total Repositories including HIP runtime: {len(set_b_hip)}")
    print(f"Hybrid Repositories (Support both): {len(hybrid_repos)}")
    print(f"PURE CUDA REPOSITORIES (Lock-in): {len(pure_cuda_repos)}")
    
    with open("pure_cuda_repos.txt", "w") as f:
        for repo in pure_cuda_repos:
            f.write(f"{repo}\n")
    print("\nSaved pure CUDA repository list to pure_cuda_repos.txt")
    
    # 6. Clean up: Once completely done, remove the checkpoint file
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)