# Feature Spec: File Operations Enhancement

## 1. The Logic Model

A robust file synchronization system handling high-frequency edits and race conditions. It uses a Finite State Machine (FSM) to ensure data consistency between Client and Server.

### Save State Machine

```
stateDiagram-v2
    [*] --> Clean
    Clean --> Dirty : User Types
    Dirty --> Saving : Debounce (2s) Ends
    Saving --> Clean : API Success
    Saving --> Error : API Fail
    Error --> Saving : Retry (Auto/Manual)
    
    note right of Dirty
        Condition: If user types while "Saving",
        the state must transition to "Dirty" 
        immediately after the current Save completes.
    end note
```

### Dependencies
- **File Management API:** Existing `/api/files` endpoints
- **Project Management:** Projects API (Phase 1)
- **Database:** File model with project_id foreign key

### Definitions
- **File Update:** Modifying existing file content (PUT/PATCH)
- **File Save:** Creating new file or updating existing (POST /save)
- **Auto-save:** Automatic file saving after edit with debounce
- **Save State:** Enum(Saved, Unsaved, Saving, Error)
- **File Conflict:** Concurrent edits to same file

### State Space
- `file_id: UUID`
- `content: String`
- `file_type: Enum(md, dfy, unit)`
- `project_id: UUID | null`
- `save_state: SaveState`
- `last_saved_at: DateTime | null`
- `last_modified_at: DateTime`

---

## 2. Capabilities

### Capability 2.1: Atomic Update (Backend)

**Goal:** Update file content atomically.

**Endpoint:** `PUT /api/files/{file_id}`

**Input:**
- Path parameter: `file_id: UUID`
- Body:
```python
class FileUpdateRequest(BaseModel):
    content: str (required)
    filename: Optional[str] (if renaming)
```

**Logic:**
1. Verify ownership (API key hash)
2. Update content and `updated_at`
3. Return `updated_at` timestamp

**Validation:**
- file_id must be valid UUID
- File must exist
- File must be owned by API key
- Content must be non-empty string
- Filename must be unique per project (if provided)

**Decision:**
- If validation fails: Return 400 Bad Request
- If not found/unauthorized: Return 404 Not Found
- If successful: Return 200 OK with updated file and timestamp

**Result:**
```python
class FileResponse(BaseModel):
    file_id: str
    filename: str
    content: str
    file_type: str
    project_id: Optional[str]
    created_at: str
    updated_at: str  # Returned timestamp used for sync verification
    size_bytes: int
```

**Postconditions:**
1. File content is updated atomically
2. `updated_at` timestamp is refreshed
3. `size_bytes` is recalculated
4. `created_at` remains unchanged
5. Timestamp returned for client sync verification

---

### Capability 2.2: Load File on Selection (Frontend)

**Goal:** Load file content when user selects a file in the explorer.

**Input:**
- `file_id: string`

**Logic:**
1. Check if file is already in cache
2. If cached and fresh (< 5 minutes old): Return cached content
3. Otherwise: Call `apiClient.getFile(file_id)`
4. Update ProjectContext state:
   - Set selectedFileId
   - Set markdownContent or dafnyCode based on file_type
   - Set save_state to "Saved"
   - Cache file content

**Validation:**
- file_id must be valid UUID format
- File must exist in project files list
- API call must succeed

**Decision:**
- If file not found: Show error, keep previous file selected
- If API error: Show error message, allow retry
- If successful: Display file content in editor

**Result:**
- File content displayed in appropriate editor
- Save state set to "Saved"
- File marked as selected in explorer

**Postconditions:**
1. Selected file content is loaded
2. Editor shows correct content
3. Save state reflects file status
4. Cache is updated

---

### Capability 2.3: Safe Auto-Save (Frontend Hook)

**Goal:** Save changes without overwriting newer edits.

**State Variables:**
- `local_content`: The text in the editor
- `synced_content`: The last text confirmed saved by server
- `status`: CLEAN | DIRTY | SAVING | ERROR

**Logic (The useAutoSave Hook):**

1. **Edit Event:** User types
   - Update `local_content`
   - Set `status = DIRTY`
   - Start/Reset Debounce Timer (2000ms)

2. **Timer Expires:**
   - Snapshot `local_content` -> `payload`
   - Set `status = SAVING`
   - Call `PUT /api/files/{id}`

3. **API Response:**
   - **Success:**
     - Update `synced_content = payload`
     - Check: Is `local_content == synced_content`?
       - **Yes:** Set `status = CLEAN`
       - **No:** Set `status = DIRTY` (User typed during save). Trigger immediate short debounce (500ms)
   - **Failure:**
     - Set `status = ERROR`
     - Show "Retry" toast

**Validation:**
- Content must be non-empty
- File must be selected
- Debounce prevents excessive saves

**Decision:**
- If content empty: Skip save (but allow deletion)
- If save fails: Show error, allow manual retry
- If successful: Update UI to show saved state
- If user types during save: Queue another save after current completes

**Result:**
- File is saved automatically
- Save indicator shows current state
- User can continue editing
- Race conditions are handled correctly

**Postconditions:**
1. File is saved within 2 seconds of last edit
2. Save state is accurately reflected
3. Errors are handled gracefully
4. No data loss on network errors (retry mechanism)
5. User edits during save are preserved and saved immediately after

---

### Capability 2.4: File Switch Guard

**Goal:** Prevent data loss when switching active files.

**Logic:**
1. User clicks File B in sidebar
2. Check File A status
3. **If DIRTY or SAVING:**
   - Trigger "Force Save" (bypass debounce) for File A
   - Optimistically navigate to File B
   - If File A save fails in background, push a Toast Notification: "Failed to save [Filename]"
4. **If CLEAN:**
   - Navigate immediately

**Validation:**
- File A must exist
- File B must be valid

**Decision:**
- If File A is dirty: Force save before switching
- If File A save fails: Show toast, allow user to return
- If File A is clean: Switch immediately

**Result:**
- No data loss when switching files
- User can continue working on new file
- Failed saves are notified

**Postconditions:**
1. All dirty files are saved before switching
2. User is notified of any save failures
3. File switching is smooth and predictable

---

### Capability 2.5: Delete File (Frontend)

**Goal:** Allow users to delete files with confirmation.

**Input:**
- `file_id: string`
- User confirmation (dialog)

**Logic:**
1. User clicks delete button
2. Show confirmation dialog: "Delete [filename]? This cannot be undone."
3. If confirmed:
   - Call `apiClient.deleteFile(file_id)`
   - Remove file from ProjectContext state
   - If deleted file was selected: Clear selection
   - Refresh file list
4. If cancelled: Do nothing

**Validation:**
- File must exist
- User must confirm
- File must be owned by API key

**Decision:**
- If user cancels: No action
- If delete fails: Show error, keep file
- If successful: Remove file from UI

**Result:**
- File is deleted from backend
- File removed from explorer
- Selection cleared if deleted file was selected

**Postconditions:**
1. File is deleted from database
2. File removed from UI
3. No orphaned references remain
4. User can undo by creating new file (if needed)

---

### Capability 2.6: Rename File (Frontend)

**Goal:** Allow users to rename files.

**Input:**
- `file_id: string`
- `new_filename: string`

**Logic:**
1. User initiates rename (double-click or context menu)
2. Show inline editor or dialog with current filename
3. User enters new filename
4. Validate filename (no invalid characters, unique in project)
5. Call `apiClient.updateFile(file_id, { filename: new_filename })`
6. Update file in ProjectContext state
7. Refresh file list

**Validation:**
- Filename must be non-empty
- Filename must be unique in project
- Filename must not contain invalid characters (/ \ : * ? " < > |)
- File extension should match file_type

**Decision:**
- If validation fails: Show error, keep old name
- If rename fails: Show error, keep old name
- If successful: Update filename in UI

**Result:**
- File is renamed in backend
- Filename updated in explorer
- File remains selected

**Postconditions:**
1. Filename is updated in database
2. Filename updated in UI
3. File remains accessible by same file_id
4. No duplicate filenames in project

---

### Capability 2.7: Create New File (Frontend)

**Goal:** Allow users to create new files (markdown or Dafny).

**Input:**
- `file_type: "md" | "dfy"`
- `filename: string` (optional, default based on type)
- `project_id: string` (required)

**Logic:**
1. User clicks "New File" button
2. Show dialog: Select type (Markdown or Dafny)
3. Generate default filename: `untitled-{timestamp}.{ext}`
4. Create file with empty content
5. Call `apiClient.saveFile({ filename, content: "", file_type, project_id })`
6. Add file to ProjectContext state
7. Select new file
8. Focus editor for immediate editing

**Validation:**
- file_type must be valid
- project_id must be valid UUID
- Filename must be unique in project

**Decision:**
- If validation fails: Show error
- If create fails: Show error
- If successful: Open file in editor

**Result:**
- New file created in backend
- File added to explorer
- File opened in editor
- User can start editing

**Postconditions:**
1. File exists in database
2. File appears in explorer
3. File is selected and editable
4. File has empty content initially

---

## 3. API Endpoints

### PUT /api/files/{file_id}

**Purpose:** Atomic update of file content

**Request:**
- Path: `/api/files/{file_id}`
- Method: `PUT`
- Body: `{ "content": "...", "filename": "optional_rename" }`

**Response:**
- Returns updated file with `updated_at` timestamp
- Timestamp used by client for sync verification

**Logic:**
1. Verify ownership (API key hash)
2. Update content and `updated_at`
3. Return `updated_at` timestamp

**PATCH /api/files/{file_id}** (Optional)
- Partial update (content or filename only)
- Same validation as PUT

### Enhanced Endpoints

**POST /api/files/save** (Existing)
- Should check if file with same name exists in project
- If exists: Update instead of create (or return error)
- If not: Create new

---

## 4. Frontend Implementation Details

### Context: FileContext

This context manages the currently active file and its status.

```typescript
type FileStatus = "clean" | "dirty" | "saving" | "error";

interface ActiveFileState {
  id: string;
  content: string; // The "source of truth" for the editor
  status: FileStatus;
  lastSavedAt: Date;
  syncedContent: string; // Last confirmed saved content
}
```

### Visual Indicators

**Dirty:** Small orange dot next to filename  
**Saving:** Spinning loader icon  
**Clean:** No icon (or fade-out green check)  
**Error:** Red alert icon (clickable to retry)

### UI Components

**Save Indicator:**
- "Clean" - No icon or fade-out green checkmark (when status === "clean")
- "Saving..." - Spinner (when status === "saving")
- "Dirty" - Orange dot (when status === "dirty")
- "Error" - Red X with retry button (when status === "error")

**File Explorer Actions:**
- Right-click menu: Rename, Delete
- Double-click filename: Rename inline
- Delete button: With confirmation dialog
- File switch: Automatically saves dirty files before switching

---

## 5. Error Handling

### Error Scenarios

1. **Network Error:**
   - Show error message
   - Allow manual retry
   - Queue save for retry when online

2. **File Conflict:**
   - Detect if file was modified elsewhere
   - Show conflict resolution dialog
   - Options: Overwrite, Keep Both, Cancel

3. **Validation Error:**
   - Show specific error message
   - Highlight invalid field
   - Prevent save until fixed

4. **Unauthorized:**
   - Show error: "You don't have permission to modify this file"
   - Disable edit controls
   - Allow read-only view

---

## 6. Postconditions (Global)

1. **Data Consistency:**
   - File content always matches backend
   - Save state accurately reflects file status
   - No orphaned file references

2. **User Experience:**
   - Files load quickly (< 200ms for cached)
   - Auto-save doesn't interrupt editing
   - Clear feedback on all operations

3. **Performance:**
   - Debounce prevents excessive API calls
   - Caching reduces load times
   - Batch operations where possible

4. **Reliability:**
   - Retry mechanism for failed saves
   - Conflict detection and resolution
   - No data loss on errors

---

## 7. Testing Requirements

### Unit Tests
- [ ] File update with valid/invalid content
- [ ] Filename uniqueness validation
- [ ] Auto-save debounce timing
- [ ] Save state transitions (Clean → Dirty → Saving → Clean/Error)
- [ ] Error handling and retry
- [ ] Race condition: Typing during save triggers second save
- [ ] File switch guard: Dirty files saved before switching

### Integration Tests
- [ ] Full CRUD workflow
- [ ] Auto-save after edits
- [ ] File deletion and cleanup
- [ ] Concurrent edit detection
- [ ] Network error recovery
- [ ] **Race Condition:** Typing during a save request triggers a second save immediately after the first finishes
- [ ] **Switching:** Switching files triggers an immediate save of the previous file
- [ ] **Debounce:** Typing continuously for 5 seconds results in only 1 save request (at the end/pause)

### Success Criteria
- ✅ Files load in < 200ms (cached) or < 1s (network)
- ✅ Auto-save triggers within 2 seconds of last edit
- ✅ Save state accurately reflects file status
- ✅ No data loss on network errors
- ✅ File operations are atomic
- ✅ Race conditions handled correctly (no lost edits)
- ✅ File switching prevents data loss

---

## 8. Implementation Checklist

### Backend
- [ ] Add PUT endpoint to `api/files.py`
- [ ] Add PATCH endpoint (optional)
- [ ] Update POST /save to handle existing files
- [ ] Add filename uniqueness check per project
- [ ] Write tests

### Frontend
- [ ] Add updateFile to `lib/api-client.ts`
- [ ] Implement FileContext with ActiveFileState interface
- [ ] Create useAutoSave hook with race condition handling
  - [ ] Implement local_content and synced_content tracking
  - [ ] Implement debounce timer (2s default, 500ms for post-save)
  - [ ] Handle state transitions: Clean → Dirty → Saving → Clean/Error
  - [ ] Handle race conditions (typing during save)
- [ ] Implement File Switch Guard
  - [ ] Check file status before switching
  - [ ] Force save dirty files before navigation
  - [ ] Show toast notifications for failed saves
- [ ] Implement file loading in `lib/project-context.tsx`
- [ ] Add save state indicator component with visual indicators
  - [ ] Orange dot for Dirty
  - [ ] Spinner for Saving
  - [ ] Green checkmark (fade-out) for Clean
  - [ ] Red alert with retry for Error
- [ ] Implement delete with confirmation
- [ ] Implement rename functionality
- [ ] Add "New File" creation flow
- [ ] Add error handling and retry
- [ ] Write tests for race conditions and file switching

---

**Status:** Ready for Implementation  
**Priority:** High (Core functionality)  
**Estimated Effort:** 3-4 days
