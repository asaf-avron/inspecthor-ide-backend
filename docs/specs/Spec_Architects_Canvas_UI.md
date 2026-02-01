# Architect's Canvas UI Specification

> **Phase:** 2-3 (Parallel with backend work)  
> **Priority:** P1 - UX transformation for NASA-grade workflow  
> **Estimated Effort:** 2 sprints

---

## 1. Logic Model (State)

### Entities
- **Canvas** - Split-view workspace for Blueprint + Proof
- **BlueprintPane** - Left side: Claim editor, Contract viewer
- **ProofPane** - Right side: VC status, Proof certificates
- **ProofTimeline** - Historical verification chain

### Key State Variables
- `Canvas.splitRatio`: Number (0.3 to 0.7, default 0.5)
- `Canvas.activeBlueprint`: UUID
- `Canvas.activeClaim`: String (REQ-XX)
- `ProofPane.vcList`: List[VC] (current verification conditions)
- `ProofPane.selectedCertificate`: UUID (from Trust Registry)

### Invariants
- Canvas must always show both panes (min-width constraints)
- Selecting a Claim must highlight corresponding VCs
- Selecting a VC must scroll to source Claim line
- Proof Timeline must be read-only (reflects ledger)

---

## 2. Capabilities (Functional Core)

### Component: SplitViewCanvas

**Description:** Main workspace with resizable Blueprint/Proof panes.

**Props:**
- `blueprintId`: UUID - Active blueprint
- `defaultSplit`: Number (0.5)

**State:**
- `leftWidth`: Number (percentage)
- `isResizing`: Boolean

**Behavior:**
- Drag divider to resize panes
- Double-click divider to reset to 50/50
- Minimum pane width: 300px
- Keyboard: Ctrl+\ to toggle focus between panes

---

### Component: ClaimEditor

**Description:** Enhanced Markdown editor with formal annotation support.

**Props:**
- `claimContent`: String
- `onSave`: (content: string) => void
- `annotations`: List[Annotation] - VC markers

**Features:**
- Syntax highlighting for formal annotations
- Inline VC status badges (✓ verified, ✗ failed, ⏳ pending)
- Click REF-XX to jump to corresponding VC
- Autocomplete for precondition/postcondition keywords

**Visual:**
```
┌─────────────────────────────────────┐
│ ## Claim: REQ-101           [✓ 4/4] │
│ ### Preconditions                   │
│ - User balance >= amount    [✓ VC-1]│
│ - User is active            [✓ VC-2]│
│ ### Postconditions                  │
│ - Balance decreases         [✓ VC-3]│
│ - Ledger updated            [✓ VC-4]│
└─────────────────────────────────────┘
```

---

### Component: ProofLedgerPanel

**Description:** Displays proof certificates from Trust Registry.

**Props:**
- `blueprintId`: UUID
- `claimFilter`: String (optional REQ-XX filter)

**Features:**
- List of proof certificates (newest first)
- Each entry shows: sequence #, status, timestamp, hash prefix
- Click entry to expand full certificate
- Chain integrity indicator (✓ valid chain)
- Export as PDF/JSON

**Visual:**
```
┌─────────────────────────────────────┐
│ PROOF LEDGER           [Chain: ✓]  │
├─────────────────────────────────────┤
│ #1042 │ REQ-101 │ ✓ VERIFIED       │
│       │ 2026-02-01 10:30:00        │
│       │ Hash: 7f3a...              │
├─────────────────────────────────────┤
│ #1041 │ REQ-102 │ ✗ FAILED         │
│       │ Counterexample available   │
└─────────────────────────────────────┘
```

---

### Component: VCStatusPanel

**Description:** Real-time verification condition status.

**Props:**
- `vcs`: List[VC]
- `isVerifying`: Boolean
- `onVCClick`: (vcId: string) => void

**Features:**
- Group VCs by source Claim
- Show progress during verification
- Failed VCs expandable to show counterexample
- Click VC to highlight source in ClaimEditor

---

### Component: VerificationTimeline

**Description:** Historical proof chain visualization.

**Props:**
- `entries`: List[LedgerEntry]
- `selectedId`: UUID

**Features:**
- Horizontal timeline with proof events
- Color coded: green (verified), red (failed), gray (pending)
- Hover for summary, click for details
- Zoom in/out for different time scales

---

## 3. Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│ Header: Blueprint Name │ Run Verification │ ? │ Avatar          │
├────────────────────────┼────────────────────────────────────────┤
│                        │                                        │
│  BLUEPRINT NAVIGATOR   │  ┌─────────────┬─────────────────────┐ │
│  ├── Claims            │  │ CLAIM       │ PROOF LEDGER        │ │
│  │   ├── REQ-101 [✓]   │  │ EDITOR      │                     │ │
│  │   └── REQ-102 [✗]   │  │             │ #1042 ✓ REQ-101     │ │
│  ├── Contracts         │  │ [Markdown]  │ #1041 ✗ REQ-102     │ │
│  │   └── banking.dfy   │  │             │                     │ │
│  └── Proofs            │  │             │ VC STATUS           │ │
│      └── latest        │  │             │ VC-1 ✓ precond      │ │
│                        │  │             │ VC-2 ✓ precond      │ │
│                        │  └─────────────┴─────────────────────┘ │
│                        │                                        │
│                        │  VERIFICATION TIMELINE                 │
│                        │  ──●────●────●────●────●──→            │
└────────────────────────┴────────────────────────────────────────┘
```

---

## 4. Files to Create/Modify

### New Components

| File | Purpose |
|------|---------|
| `components/canvas/split-view-canvas.tsx` | Main split layout |
| `components/canvas/claim-editor.tsx` | Enhanced spec editor |
| `components/canvas/proof-ledger-panel.tsx` | Trust Registry viewer |
| `components/canvas/vc-status-panel.tsx` | VC verification status |
| `components/canvas/verification-timeline.tsx` | Historical proof chain |

### Modified Components

| File | Changes |
|------|---------|
| `components/ide/project-explorer.tsx` | Rename to `blueprint-navigator.tsx`, add proof tree |
| `components/ide/verification-panel.tsx` | Integrate with VC system |
| `components/ide/header.tsx` | Update branding, add canvas toggle |

### New Contexts

| File | Purpose |
|------|---------|
| `lib/contexts/canvas-context.tsx` | Split view state management |
| `lib/contexts/trust-context.tsx` | Trust Registry data fetching |

---

## 5. API Integration

### Required Endpoints

| Endpoint | Component |
|----------|-----------|
| `GET /api/v1/blueprints/{id}` | BlueprintNavigator |
| `GET /api/v1/verify/generate-vcs` | ClaimEditor |
| `POST /api/v1/verify/run` | VCStatusPanel |
| `GET /api/v1/trust/certificate/{seq}` | ProofLedgerPanel |
| `GET /api/v1/trust/audit` | VerificationTimeline |

---

## 6. Verification Plan

### Component Tests
1. SplitViewCanvas: resize, min-width constraints
2. ClaimEditor: annotation rendering, VC badge clicks
3. ProofLedgerPanel: list rendering, expansion, chain indicator
4. VCStatusPanel: progress states, counterexample display

### Integration Tests
1. Select Claim → VCs highlighted in panel
2. Click VC → Editor scrolls to source
3. Run verification → Real-time status updates
4. Verification complete → Ledger panel updates

### Manual Verification
1. Full workflow: Create claim → Generate VCs → Verify → View certificate
2. Failed verification: Inspect counterexample
3. Chain integrity: Verify ledger shows valid chain indicator
