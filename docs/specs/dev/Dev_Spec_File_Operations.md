# Feature Spec: File Operations Enhancement

## 1. The Logic Model

Enhanced file management system supporting full CRUD operations with proper state management, auto-save, and file versioning.

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

### Capability 2.1: Update File (Backend)

**Goal:** Update existing file content without creating new file.

**Input:**
- Path parameter: `file_id: UUID`
- Body:
```python
class FileUpdateRequest(BaseModel):
    content: str (required)
    filename: Optional[str] (if renaming)
```

**Logic:**
1. Extract API key and hash
2. Find file WHERE file_id = id AND api_key_hash = hash
3. Update content and size_bytes
4. Update updated_at timestamp
5. If filename provided, update filename
6. Save changes

**Validation:**
- file_id must be valid UUID
- File must exist
- File must be owned by API key
- Content must be non-empty string
- Filename must be unique per project (if provided)

**Decision:**
- If validation fails: Return 400 Bad Request
- If not found/unauthorized: Return 404 Not Found
- If successful: Return 200 OK with updated file

**Result:**
```python
class FileResponse(BaseModel):
    file_id: str
    filename: str
    content: str
    file_type: str
    project_id: Optional[str]
    created_at: str
    updated_at: str
    size_bytes: int
```

**Postconditions:**
1. File content is updated
2. updated_at timestamp is refreshed
3. size_bytes is recalculated
4. created_at remains unchanged

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

### Capability 2.3: Auto-Save (Frontend)

**Goal:** Automatically save file changes after user stops typing.

**Input:**
- File content changes (debounced)

**Logic:**
1. User types in editor
2. Debounce timer starts (2 seconds)
3. On timer expiration:
   - Set save_state to "Saving"
   - If file_id exists: Call `apiClient.updateFile(file_id, content)`
   - If no file_id: Call `apiClient.saveFile(...)` (create new)
4. On success: Set save_state to "Saved", update last_saved_at
5. On error: Set save_state to "Error", show error message

**Validation:**
- Content must be non-empty
- File must be selected
- Debounce prevents excessive saves

**Decision:**
- If content empty: Skip save (but allow deletion)
- If save fails: Show error, allow manual retry
- If successful: Update UI to show saved state

**Result:**
- File is saved automatically
- Save indicator shows current state
- User can continue editing

**Postconditions:**
1. File is saved within 2 seconds of last edit
2. Save state is accurately reflected
3. Errors are handled gracefully
4. No data loss on network errors (retry mechanism)

---

### Capability 2.4: Delete File (Frontend)

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

### Capability 2.5: Rename File (Frontend)

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

### Capability 2.6: Create New File (Frontend)

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

### New Endpoint

**PUT /api/files/{file_id}**
- Updates existing file content
- Requires file ownership
- Returns updated file

**PATCH /api/files/{file_id}** (Optional)
- Partial update (content or filename only)
- Same validation as PUT

### Enhanced Endpoints

**POST /api/files/save** (Existing)
- Should check if file with same name exists in project
- If exists: Update instead of create (or return error)
- If not: Create new

---

## 4. Frontend State Management

### Save State Indicator

```typescript
type SaveState = "saved" | "unsaved" | "saving" | "error";

interface FileState {
  file_id: string | null;
  content: string;
  save_state: SaveState;
  last_saved_at: Date | null;
  last_modified_at: Date;
}
```

### UI Components

**Save Indicator:**
- "Saved" - Green checkmark (when save_state === "saved")
- "Saving..." - Spinner (when save_state === "saving")
- "Unsaved" - Orange dot (when save_state === "unsaved")
- "Error" - Red X with retry button (when save_state === "error")

**File Explorer Actions:**
- Right-click menu: Rename, Delete
- Double-click filename: Rename inline
- Delete button: With confirmation dialog

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
- [ ] Save state transitions
- [ ] Error handling and retry

### Integration Tests
- [ ] Full CRUD workflow
- [ ] Auto-save after edits
- [ ] File deletion and cleanup
- [ ] Concurrent edit detection
- [ ] Network error recovery

### Success Criteria
- ✅ Files load in < 200ms (cached) or < 1s (network)
- ✅ Auto-save triggers within 2 seconds of last edit
- ✅ Save state accurately reflects file status
- ✅ No data loss on network errors
- ✅ File operations are atomic

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
- [ ] Implement file loading in `lib/project-context.tsx`
- [ ] Add auto-save with debounce
- [ ] Add save state indicator component
- [ ] Implement delete with confirmation
- [ ] Implement rename functionality
- [ ] Add "New File" creation flow
- [ ] Add error handling and retry
- [ ] Write tests

---

**Status:** Ready for Implementation  
**Priority:** High (Core functionality)  
**Estimated Effort:** 3-4 days
