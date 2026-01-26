# User Interface Flow & API Mapping

This document details the user interface flow of the Guardian Gateway IDE and maps the interactive elements to their expected API endpoints.

## 1. Landing / Empty State

**State Condition:** `hasProject == false`

### Actions

| Component | Label | Action / Flow | Expected API | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **EmptyState** | **"Choose Template"** | Opens `TemplateGallery` modal. | None (Client-side) | Loads template list from local state/constants. |
| **EmptyState** | **"Upload File"** | Opens browser file picker (`.md`, `.markdown`). Reads file content. | None (Client-side) | `FileReader` API used. |
| **EmptyState** | **"Start from Scratch"** | Initializes project with default "New Specification" content. | None (Client-side) | Sets local state. |

## 2. Template Gallery (Modal)

**State Condition:** `showTemplateGallery == true`

### Actions

| Component | Label | Action / Flow | Expected API | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **TemplateCard** | **(Click on Template)** | Fetches template content -> Updates project state -> Closes modal. | `GET /templates/{templateFile}` | Fetches from public directory. |
| **TemplateGallery** | **"Close"** | Closes modal. | None (Client-side) | |

## 3. Main IDE Interface

**State Condition:** `hasProject == true`

### 3.1 Header Actions

| Component | Label | Action / Flow | Expected API | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Header** | **"New"** | Resets state to Empty State. | None (Client-side) | |
| **Header** | **"Open"** | Triggers file upload (same as Empty State). | None (Client-side) | |
| **Header** | **"Templates"** | Opens `TemplateGallery` modal. | None (Client-side) | |
| **Header** | **"Download"** | Downloads current requirements as `.md`. | None (Client-side) | Browser blob download. |
| **Header** | **"Generate Formal Spec"** | Sends requirements to backend -> Receives Dafny spec -> Updates UI. | `POST /api/generate/spec` | **Crucial Missing Link**. |

#### API Detail: Generate Formal Spec

*   **Endpoint:** `POST /api/generate/spec`
*   **Request Body (`GenerateSpecRequest`):**
    ```json
    {
      "english_spec": "# My Requirements\n\nThe system shall...",
      "options": {
        "strictness_level": "medium"
      }
    }
    ```
*   **Response Body (`GenerateSpecResponse`):**
    ```json
    {
      "dafny_skeleton": "method Main() { ... }",
      "gaps": [ ... ],
      "ambiguities": [ ... ],
      "traceability_matrix": [ ... ],
      "statistics": { ... }
    }
    ```

### 3.2 Content Area

#### Left Panel: Requirements

| Component | Label | Action / Flow | Expected API | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Header** | **"Edit"** | **TODO**: Switch View Mode to Edit Mode (Textarea/Editor). | None (Client-side) | Currently non-functional. |
| **Editor** | **(Text Input)** | Updates `selectedTemplate` state. | None (Client-side) | Needs implementation. |

#### Right Panel: Results & Verification

| Component | Label | Action / Flow | Expected API | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Panel** | **Display Code** | Shows `dafny_skeleton` from generation response. | None (Client-side) | Needs `MonacoEditor` or `Prism` for highlighting. |
| **Toolbar** | **"Verify"** (Proposed) | Sends Dafny code to backend for verification. | `POST /api/verify` | Not present in UI yet. |

#### API Detail: Verify (Proposed)

*   **Endpoint:** `POST /api/verify`
*   **Request Body (`VerifyRequest`):**
    ```json
    {
      "dafny_code": "method Main() ...",
      "timeout_seconds": 30
    }
    ```
*   **Response Body (`VerifyResponse`):**
    ```json
    {
      "verified": true,
      "results": [ ... ],
      "errors": [ ... ]
    }
    ```

## 4. AI Assistant (Sidebar/Floating)

**Status:** Not implemented in UI.

| Component | Label | Action / Flow | Expected API | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **ChatInput** | **Send** | Sends user message + context to backend. | `POST /api/assistant/chat` | |

#### API Detail: Chat

*   **Endpoint:** `POST /api/assistant/chat`
*   **Request Body (`ChatRequest`):**
    ```json
    {
      "message": "Why is this failing?",
      "context": {
        "code": "...",
        "error": "..."
      }
    }
    ```

## 5. Backend Status

| Endpoint | Status | Notes |
| :--- | :--- | :--- |
| `GET /api/health` | Active | Checks DB, Dafny, Gemini config. |
