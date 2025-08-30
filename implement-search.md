# Implement Dashboard Search Functionality

## Overview
Add search functionality to the web dashboard that allows users to search for videos by topic and rate them directly in the browser, similar to the CLI "Topic Rating Session (Search + Rate by Topic)" feature.

## Current State
- Dashboard has disabled search box in header
- Only shows pre-existing recommendations and liked videos
- Search functionality exists in CLI (`topic_rate.py`) but not in web interface

## Implementation Plan

### Phase 1: Backend API Endpoints

#### 1.1 Add Topic Search API Endpoint
- **File**: `dashboard_api.py`
- **Endpoint**: `POST /api/search-topic`
- **Functionality**:
  - Accept topic string from frontend
  - Use `TopicVideoSearchService` to search and save videos
  - Return search results with metadata
  - Handle errors gracefully (API quota, network issues)

#### 1.2 Add Search Results API Endpoint  
- **Endpoint**: `GET /api/search-results/<session_id>`
- **Functionality**:
  - Return videos from a specific search session
  - Include search metadata (topic, timestamp)
  - Format similar to recommendations endpoint

### Phase 2: Frontend UI Components

#### 2.1 Enable Search Box
- **File**: `templates/dashboard.html`
- Remove `disabled` attribute from search input
- Add search button functionality
- Implement search form submission

#### 2.2 Add Search Results View
- Create new view container for search results
- Add navigation button for "Search Results" 
- Display search results in same grid format as recommendations
- Show search topic and metadata

#### 2.3 Search Flow UX
- Loading states during search
- Progress indicators for search process
- Error handling for failed searches
- Empty state for no results

### Phase 3: Search Integration

#### 3.1 Topic Search Implementation
- **Frontend**: Capture search input and trigger API call
- **Backend**: Use existing `TopicVideoSearchService` and `OllamaClient`
- **Database**: Store search sessions with metadata and session tracking
- **Response**: Return searchable videos for rating with session ID

#### 3.2 Rating Integration
- Use existing rating system for search results
- Update ML model after ratings on search results
- Track which videos came from search vs recommendations

#### 3.3 Navigation Flow
- Search → Results View → Rate Videos → Back to Search or Recommendations
- Persistent search history/sessions
- Clear search functionality

### Phase 4: Enhanced Features

#### 4.1 Search History
- Store recent searches in localStorage or database
- Quick access to previous search topics
- Search suggestions based on history

#### 4.2 Advanced Search Options
- Number of results per query control
- Search within specific time ranges
- Filter by view count, etc.

#### 4.3 Search Session Management
- **Cleanup Old Searches**: Automatically archive searches older than 7 days
- **Session History**: View and manage previous search sessions
- **Search Statistics**: Dashboard showing search activity and cleanup status

#### 4.4 Bulk Operations
- Rate multiple videos at once
- Remove multiple search results
- Export search results
- Delete entire search sessions

## Technical Implementation Details

### Backend Changes Required

#### dashboard_api.py
```python
@app.route('/api/search-topic', methods=['POST'])
def search_topic():
    # Accept topic from frontend
    # Create search session with unique ID
    # Use TopicVideoSearchService to search and save videos
    # Link videos to search session
    # Return results with session_id and metadata

@app.route('/api/search-results/<session_id>')
def get_search_results(session_id):
    # Return videos from specific search session
    # Include search metadata and session info

@app.route('/api/cleanup-searches', methods=['POST'])
def cleanup_old_searches():
    # Clean up searches older than specified days
    # Return cleanup statistics

@app.route('/api/search-history')
def get_search_history():
    # Return recent search sessions
    # Include session metadata and video counts
```

#### New Database Schema (Required)
```sql
-- Track search sessions with status for cleanup
CREATE TABLE search_sessions (
    id TEXT PRIMARY KEY,
    topic TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    video_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active'
);

-- Link videos to search sessions with topic tracking
ALTER TABLE videos ADD COLUMN search_session_id TEXT;
ALTER TABLE videos ADD COLUMN search_topic TEXT;
CREATE INDEX idx_videos_search_session ON videos(search_session_id);
```

### Frontend Changes Required

#### HTML Structure
```html
<!-- Enable search box -->
<input type="text" class="search-box" placeholder="Search by topic..." id="searchInput">
<button class="search-button" onclick="searchByTopic()">🔍</button>

<!-- Add search results view -->
<div class="view-container" id="searchView">
    <h1 class="section-title" id="searchSectionTitle">
        Search Results
    </h1>
    <div class="video-grid" id="searchVideoGrid"></div>
</div>
```

#### JavaScript Functions
```javascript
async function searchByTopic() {
    // Get search input
    // Call /api/search-topic
    // Switch to search results view
    // Display loading state
}

function displaySearchResults(videos, topic) {
    // Similar to displayVideos but for search results
    // Include search topic and metadata
    // Enable rating functionality
}
```

## File Changes Summary

### New Files
- **src/database/search_operations.py**: Search session management and cleanup

### Modified Files
1. **dashboard_api.py**
   - Add search endpoints
   - Integrate with existing services

2. **templates/dashboard.html**
   - Enable search input
   - Add search results view
   - Add search JavaScript functions
   - Update navigation

3. **src/database/search_operations.py** (New File)
   - Complete search session management
   - Cleanup functionality for old searches
   - Session statistics and tracking

4. **src/database/manager.py**
   - Add search_sessions table
   - Add search tracking columns to videos table

## Dependencies
- All required services already exist (`TopicVideoSearchService`, `OllamaClient`)
- No new Python packages needed
- Uses existing database schema (optional enhancements)

## Testing Plan
1. Test search API endpoints with various topics
2. Verify video search and storage works correctly
3. Test rating functionality on search results
4. Verify ML model retraining after search result ratings
5. Test error handling for API quota/network issues
6. Test responsive design on mobile devices

## Success Criteria
- [ ] Users can search for videos by entering a topic
- [ ] Search results display in familiar video grid format
- [ ] Users can rate search results like recommendations
- [ ] Search integrates with existing ML model training
- [ ] Error states are handled gracefully
- [ ] Search functionality works on mobile devices
- [ ] Loading states provide good user feedback

## Future Enhancements
- Search suggestions/autocomplete
- Advanced filtering options
- Search result export functionality
- Search analytics and insights
- Integration with external topic databases