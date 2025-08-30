# Topic-Based Video Search with Ollama

## Overview
Add functionality to search for YouTube videos based on user-provided topics, using Ollama LLMs to generate relevant search keywords.

## Implementation Plan

### 1. Create Ollama Integration Module
**File:** `src/ollama/keyword_generator.py`
- Function to check if Ollama is running
- Function to get model from .env (OLLAMA_MODEL)
- Function to generate keywords from topic using Ollama API
- Error handling for when Ollama is not available

### 2. Create Topic Search Script
**File:** `search_by_topic.py`
- Accept topic as command-line argument or interactive input
- Call Ollama to generate 10-15 relevant search queries
- Use existing YouTube search functionality to find videos
- Save videos to existing database structure

### 3. Environment Configuration
**File:** `.env`
```
YOUTUBE_API_KEY=existing_key
OLLAMA_MODEL=llama3.2
```
- Default to llama3.2 if not specified
- Allow users to choose any installed Ollama model

### 4. Ollama Prompt Engineering
**Prompt Template:**
```
Generate 15 YouTube search queries for finding programming/coding videos about: {topic}

Focus on:
- Tutorial keywords
- Project-based learning
- Practical applications
- Different skill levels
- Various programming languages if applicable

Return only the search queries, one per line.
```

### 5. Update Setup Script
**File:** `setup.sh`
- Add new menu option: "5) Search videos by topic"
- Check if Ollama is installed
- If not installed, provide installation instructions
- Run `search_by_topic.py` if selected

### 6. Ollama API Integration
**Endpoint:** `http://localhost:11434/api/generate`
**Method:** POST
**Payload:**
```json
{
  "model": "{from_env}", 
  "prompt": "...",
  "stream": false
}
```

### 7. Error Handling
- Check if Ollama service is running
- Verify selected model is available
- Fallback to manual topic entry if Ollama unavailable
- Handle API timeouts gracefully
- Clear error messages for missing model

### 8. Example Usage
```bash
# Interactive mode
python3 search_by_topic.py
> Enter topic: rust web development

# Command-line mode  
python3 search_by_topic.py --topic "rust web development"

# With specific model override
OLLAMA_MODEL=mistral python3 search_by_topic.py --topic "rust web development"
```

### 9. Generated Keywords Example
For topic "rust web development":
- rust web framework tutorial
- actix web tutorial
- rocket framework rust
- rust REST API
- warp web server rust
- rust websocket tutorial
- rust frontend wasm
- rust backend development
- etc.

## Implementation Steps

1. **First:** Create Ollama integration module with basic API calls
2. **Second:** Add OLLAMA_MODEL to .env configuration
3. **Third:** Test Ollama connectivity and keyword generation
4. **Fourth:** Create the main search_by_topic.py script
5. **Fifth:** Integrate with existing video search and save functions
6. **Sixth:** Update setup.sh with new menu option
7. **Finally:** Test end-to-end with various topics and models

## Testing Scenarios
### Topics to Test
- "rust web development"
- "machine learning for beginners"
- "vim productivity tips"
- "building CLI tools"
- "game development tutorials"

### Models to Test
- llama3.2 (default)
- mistral
- codellama
- phi

## Model Selection Logic
```python
# Pseudocode
model = os.getenv('OLLAMA_MODEL', 'llama3.2')
if not check_model_exists(model):
    print(f"Model {model} not found. Available models:")
    list_available_models()
    fallback_to_manual_entry()
```

## Future Enhancements
- Cache generated keywords by topic and model
- Allow users to review/edit keywords before searching
- Support multiple models in single search
- Rate limit awareness for YouTube API
- Keyword quality scoring