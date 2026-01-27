# Feature Spec: Deconstruct Specification to Units

## 1. The Logic Model

Automated breakdown of monolithic specifications into verifiable units with granular traceability links. This feature uses AI to identify logic boundaries and maps them to specific line numbers for UI highlighting.

### Deconstruction Flow

```
sequenceDiagram
    participant User
    participant API
    participant AI_Service
    participant DB

    User->>API: POST /deconstruct (Root_ID)
    API->>AI_Service: Analyze MD Structure (AST)
    AI_Service-->>API: Return JSON { units: [{title, range, reqs}] }
    
    loop For Each Unit
        API->>AI_Service: Generate Dafny Spec
        API->>DB: Create .unit.md File
        API->>DB: Create .dfy File
        API->>DB: Create Link Record (TraceabilityMap)
    end
    
    API-->>User: Success (New File Tree + Links)
```

### Dependencies
- **Project Management:** Projects API (Phase 1)
- **File Management:** File API (Phase 2)
- **Specification Generation:** Existing `/api/generate/spec` endpoint
- **AI/Gemini:** For intelligent unit identification

### Definitions
- **Root Specification:** A complete specification file (`.md`) that needs to be broken down
- **Unit:** A logical component of the specification that can be independently verified
- **Unit File:** A markdown file (`.unit.md`) containing a single unit's requirements
- **Unit Dafny File:** A Dafny file (`.dfy`) containing the formal verification code for a unit
- **Unit Link:** A mapping between a unit file and its corresponding Dafny file
- **Deconstruction Strategy:** Enum(Auto, Manual) - how units are identified

### State Space
- `source_file_id: UUID` (root spec file)
- `project_id: UUID`
- `strategy: DeconstructionStrategy`
- `units: List[Unit]`
- `unit_links: List[UnitLink]`
- `deconstruction_status: Enum(Pending, Processing, Complete, Failed)`

### Unit Structure
```python
class Unit(BaseModel):
    unit_id: str (UUID)
    unit_filename: str (e.g., "unit-001-token-minting.md")
    dafny_filename: str (e.g., "unit-001-token-minting.dfy")
    title: str
    description: str
    requirements: List[str]  # Extracted from root spec
    dafny_code: str
    line_range: Tuple[int, int]  # Lines in root spec
```

---

## 2. Capabilities

### Capability 2.1: Intelligent Unit Identification

**Goal:** Identify logical boundaries and return Line Ranges.

**Input:**
- Markdown Content (from Root File)

**Logic:**
1. Send content to AI Service with prompt: "Identify independent logical units. Return title, requirements, and start/end line numbers from source."
2. **Constraint:** Line numbers must map exactly to the provided markdown.

**Validation:**
- Root spec must have structure (headers, functions)
- At least one unit must be identifiable
- Line numbers must be valid (within markdown bounds)
- Units must not overlap

**Decision:**
- If no units found: Return error "Specification structure not suitable for deconstruction"
- If validation fails: Return error with details
- If successful: Return list of identified units with line ranges

**Result:**
```python
class UnitCandidate(BaseModel):
    title: str
    description: str
    requirements: List[str]
    line_range: Tuple[int, int]  # start_line, end_line from source
    dependencies: List[str]  # Other unit titles
```

**Postconditions:**
1. All units are identified with accurate line ranges
2. Line numbers map exactly to markdown source
3. Units cover entire specification
4. No overlapping units

---

### Capability 2.2: Linkage & Traceability Map

**Goal:** Provide the frontend with data to render "Ghost Links".

**Data Structure:** TraceabilityMap (See section 3)

**Logic:**
When generating the `.dfy` file, create a UnitLink record that stores:
- `root_file_id`: The big spec
- `unit_file_id`: The small chunk
- `dafny_file_id`: The code
- `source_range`: `{ start: 10, end: 25 }`

**Input:**
- `source_file_id: UUID`
- `project_id: UUID`
- `units: List[UnitCandidate]`

**Logic:**
1. Load source file content
2. For each unit candidate:
   a. Extract content from source (using line_range)
   b. Create unit markdown file:
      - Title: Unit title
      - Description: Unit description
      - Requirements: List of requirements
      - Dependencies: List of dependent units
   c. Generate Dafny code for unit:
      - Use existing `/api/generate/spec` logic
      - Input: Unit requirements only
      - Output: Dafny code for this unit
   d. Create Dafny file with generated code
   e. Save both files to database:
      - Unit file: `{unit_id}.unit.md`
      - Dafny file: `{unit_id}.dfy`
   f. Create UnitLink record with source_range
3. Update source file metadata (mark as deconstructed)

**Validation:**
- Source file must exist and be owned by API key
- Project must exist
- All units must be valid
- File creation must succeed

**Decision:**
- If validation fails: Rollback all created files, return error
- If Dafny generation fails for a unit: Mark unit as failed, continue with others
- If successful: Return list of created units

**Result:**
```python
class DeconstructResponse(BaseModel):
    units: List[Unit]
    links: List[UnitLink]
    statistics: DeconstructStats
    errors: List[str]  # Any unit-level errors
```

**Postconditions:**
1. Unit files are created in database
2. Dafny files are created in database
3. Unit links are established
4. Source file is marked as deconstructed
5. All files are associated with project

---

### Capability 2.3: UI Visualization (Frontend)

**Goal:** Render clickable badges on the Root Spec.

**Logic:**
1. **View Mode:** When viewing a Root Spec (`is_root=true`)
2. **Fetch:** Get TraceabilityMap for this file
3. **Render:**
   - Display Markdown
   - For each Link, calculate vertical offset based on `source_range.start_line`
   - Render a floating `<Badge>` component in the margin or overlay: 🔗 [Unit: Auth]
4. **Interaction:**
   - Clicking the Badge splits the view and loads the corresponding `.dfy` file in the Right Pane

**Validation:**
- Root file must exist
- TraceabilityMap must be available
- Line numbers must be valid

**Decision:**
- If no links found: Show no badges
- If successful: Display badges with correct positioning

**Result:**
- Badges visible on root spec
- Clicking badge opens unit Dafny file
- User can navigate between root and units

**Postconditions:**
1. Badges are positioned correctly based on line numbers
2. Clicking badge opens correct Dafny file
3. View is split appropriately

---

### Capability 2.4: Create Unit Links (Backend)

**Goal:** Establish traceability between unit files and Dafny files.

**Input:**
- `units: List[Unit]` (with file_ids)

**Logic:**
1. For each unit:
   - Create UnitLink record:
     - unit_file_id → unit markdown file
     - dafny_file_id → unit Dafny file
     - source_file_id → root spec file
     - link_type: "unit-implementation"
2. Store links in database (new table or JSON in unit file metadata)

**Validation:**
- All file_ids must exist
- Links must be unique
- Files must belong to same project

**Decision:**
- If validation fails: Return error
- If successful: Return link list

**Result:**
```python
class UnitLink(BaseModel):
    link_id: str (UUID)
    unit_file_id: str
    dafny_file_id: str
    source_file_id: str
    link_type: str
    created_at: str
```

**Postconditions:**
1. All units have corresponding links
2. Links are stored in database
3. Links can be queried efficiently

---

### Capability 2.5: Deconstruct API Endpoint (Backend)

**Goal:** Expose deconstruction functionality via REST API.

**Input:**
```python
class DeconstructRequest(BaseModel):
    project_id: str (UUID, required)
    source_file_id: str (UUID, required)
    strategy: Literal["auto", "manual"] = "auto"
    max_units: Optional[int] = None  # Limit number of units
    unit_boundaries: Optional[List[Tuple[int, int]]] = None  # For manual strategy
```

**Logic:**
1. Validate request:
   - Project exists and is owned by API key
   - Source file exists and is owned by API key
   - Source file is markdown type
   - Source file is root spec (not already a unit)
2. Load source file content
3. Identify units (Capability 2.1)
4. Generate unit files (Capability 2.2)
5. Create unit links (Capability 2.3)
6. Calculate statistics
7. Return response

**Validation:**
- All IDs must be valid UUIDs
- Project and file ownership must match API key
- Source file must be markdown
- Strategy must be valid

**Decision:**
- If validation fails: Return 400 Bad Request
- If source file invalid: Return 400 with specific error
- If deconstruction fails: Return 500 with error details
- If successful: Return 200 with units and links

**Result:**
```python
class DeconstructResponse(BaseModel):
    units: List[Unit]
    links: List[UnitLink]
    statistics: DeconstructStats
    errors: List[str]

class DeconstructStats(BaseModel):
    total_units: int
    successful_units: int
    failed_units: int
    total_files_created: int
    processing_time_seconds: float
```

**Postconditions:**
1. Units are created and saved
2. Dafny files are generated
3. Links are established
4. Statistics are accurate
5. Source file is marked appropriately

---

### Capability 2.6: Deconstruct UI Flow (Frontend)

**Goal:** Provide user interface for deconstructing specifications.

**Input:**
- User clicks "Deconstruct to Units" button
- Current file is root specification

**Logic:**
1. Validate preconditions:
   - File is markdown type
   - File is root spec (not unit)
   - File has content
2. Show confirmation dialog:
   - "This will create unit files from your specification. Continue?"
3. If confirmed:
   - Set loading state: "Deconstructing..."
   - Call `apiClient.deconstruct({ project_id, source_file_id })`
   - Show progress indicator
4. On success:
   - Refresh file list
   - Show success message: "Created {N} units"
   - Highlight unit files in explorer
   - Optionally: Open first unit file
5. On error:
   - Show error message
   - Allow retry

**Validation:**
- File must be root spec
- File must have content
- Project must be selected

**Decision:**
- If preconditions not met: Disable button, show tooltip
- If user cancels: No action
- If API error: Show error, allow retry
- If successful: Update UI, show results

**Result:**
- Unit files visible in explorer
- Deconstruct button disabled for root file (already deconstructed)
- Success feedback shown

**Postconditions:**
1. UI reflects deconstruction results
2. Unit files are accessible
3. User can navigate to units
4. Traceability view shows unit links

---

## 3. API Endpoints

### POST /api/deconstruct

**Input:**
```json
{
  "project_id": "...",
  "source_file_id": "..."
}
```

**Process:** Runs the AI analysis and generation loop.

**Response:** 200 OK (Refreshes file tree)

### GET /api/files/{file_id}/traceability

**Input:** `root_file_id`

**Response:**
```json
{
  "source_file_id": "uuid-root",
  "links": [
    {
      "unit_id": "uuid-1",
      "dafny_file_id": "uuid-dfy-1",
      "title": "Token Minting",
      "source_range": {
        "start_line": 12,
        "end_line": 45
      },
      "status": "verified"
    }
  ]
}
```

**Request:**
```json
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "source_file_id": "660e8400-e29b-41d4-a716-446655440000",
  "strategy": "auto",
  "max_units": 10
}
```

**Response (200 OK):**
```json
{
  "units": [
    {
      "unit_id": "770e8400-e29b-41d4-a716-446655440000",
      "unit_filename": "unit-001-token-minting.unit.md",
      "dafny_filename": "unit-001-token-minting.dfy",
      "title": "Token Minting",
      "description": "Handles token minting with limits",
      "requirements": ["Mint tokens up to max supply", "Track total minted"],
      "dafny_code": "module TokenMinting { ... }",
      "line_range": [10, 45]
    }
  ],
  "links": [
    {
      "link_id": "880e8400-e29b-41d4-a716-446655440000",
      "unit_file_id": "770e8400-e29b-41d4-a716-446655440000",
      "dafny_file_id": "990e8400-e29b-41d4-a716-446655440000",
      "source_file_id": "660e8400-e29b-41d4-a716-446655440000",
      "link_type": "unit-implementation",
      "created_at": "2026-01-26T12:00:00Z"
    }
  ],
  "statistics": {
    "total_units": 5,
    "successful_units": 5,
    "failed_units": 0,
    "total_files_created": 10,
    "processing_time_seconds": 12.5
  },
  "errors": []
}
```

---

## 4. Database Schema Updates

### Table: unit_links

```python
class UnitLink(Base):
    __tablename__ = "unit_links"
    
    id = Column(String(36), primary_key=True, default=uuid)
    root_file_id = Column(String(36), ForeignKey('files.file_id'))
    unit_file_id = Column(String(36), ForeignKey('files.file_id'))
    dafny_file_id = Column(String(36), ForeignKey('files.file_id'))
    
    # Traceability Data
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    
    # Metadata
    title = Column(String(255))
    verification_status = Column(Enum('verified', 'failed', 'unknown'), default='unknown')
```

### File Metadata Enhancement

Add to File model:
```python
is_root_spec: bool (default False)
is_unit: bool (default False)
deconstructed_at: datetime | null
parent_file_id: str | null (for units, points to root spec)
```

---

## 5. Unit Identification Algorithm

### Markdown Parsing Rules

1. **Header-Based Units:**
   - Each `## Header` → potential unit
   - Content under header → unit content
   - Stop at next `##` or end of file

2. **Function-Based Units:**
   - Each `### Function: Name` → unit
   - Includes function description and requirements
   - Stops at next function or section

3. **Entity-Based Units:**
   - `**Entities:**` section → unit
   - Includes all entity definitions
   - Stops at next major section

### Unit Validation Rules

1. Unit must have:
   - Clear title
   - At least one requirement
   - Verifiable logic

2. Unit should not:
   - Be too large (> 100 lines)
   - Have circular dependencies
   - Overlap with other units

3. Unit boundaries:
   - Should align with markdown structure
   - Should be semantically meaningful
   - Should be independently testable

---

## 6. Postconditions (Global)

1. **Completeness:**
   - All units cover entire specification
   - No gaps in coverage
   - No overlapping content

2. **Traceability:**
   - Each unit links to its Dafny file
   - Root spec links to all units
   - Links are bidirectional queryable

3. **Verifiability:**
   - Each unit can be verified independently
   - Dafny code is syntactically correct
   - Units can be composed for full spec verification

4. **Data Integrity:**
   - All files are saved to database
   - All links are established
   - Source file is marked appropriately
   - No orphaned files or links

---

## 7. Testing Requirements

### Unit Tests
- [ ] Unit identification from markdown
- [ ] Unit validation rules
- [ ] Dafny code generation for units
- [ ] Link creation
- [ ] Error handling

### Integration Tests
- [ ] Full deconstruction workflow
- [ ] Multiple units creation
- [ ] File and link persistence
- [ ] Error recovery (partial success)
- [ ] Concurrent deconstruction prevention

### Success Criteria
- ✅ Units are correctly identified from spec structure
- ✅ All units have corresponding Dafny files
- ✅ Links are correctly established
- ✅ Deconstruction completes in < 30 seconds for typical spec
- ✅ Partial failures don't corrupt data
- [ ] **Line Mapping:** The AI-identified line numbers accurately match the markdown text (visual inspection)
- [ ] **Navigation:** Clicking a link badge opens the correct `.dfy` file
- [ ] **Isolation:** Deconstructing a file only affects that file and creates new sub-files; it does not overwrite the root

---

## 8. Implementation Checklist

### Backend
- [ ] Create `api/deconstruct.py` router
- [ ] Implement markdown parsing logic
- [ ] Implement unit identification algorithm
- [ ] Integrate with Dafny generation
- [ ] Create unit links table/model
- [ ] Add file metadata fields
- [ ] Implement deconstruct endpoint
- [ ] Write tests
- [ ] Include router in `api/main.py`

### Frontend
- [ ] Add deconstruct to `lib/api-client.ts`
- [ ] Implement deconstructToUnits in `lib/project-context.tsx`
- [ ] Add loading state and progress
- [ ] Update file explorer to show units
- [ ] Update traceability view for unit links
- [ ] Add deconstruct button (root files only)
- [ ] Write tests

---

**Status:** Ready for Implementation  
**Priority:** Medium (Enhancement feature)  
**Estimated Effort:** 4-5 days
