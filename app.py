# Guardian Gateway - Streamlit Frontend
# 4-Stage Workflow: Triage -> Structure -> Audit -> Approve
# Imperative Shell: UI layer that uses the pure Functional Core

import streamlit as st
import pandas as pd
from core_parser import (
    DafnyParser, 
    parse_dafny_source, 
    humanize_clause, 
    get_clause_icon
)
from core_auditor import SpecAuditor, GapReport, TraceabilityEntry
from core_gateway import CodeVerifier, VerificationResult
from core_workflow import (
    DocType, RigorLevel, WorkflowStatus,
    run_triage, run_structuring,
    assess_risk, get_risk_status,
    RISK_THRESHOLDS
)

# Page configuration
st.set_page_config(
    page_title="Guardian Gateway",
    page_icon="🛡️",
    layout="wide"
)


# =============================================================================
# Session State Initialization
# =============================================================================

def init_workflow_state():
    """Initialize all workflow-related session state variables."""
    if "workflow_status" not in st.session_state:
        st.session_state.workflow_status = WorkflowStatus.DRAFT
    if "current_stage" not in st.session_state:
        st.session_state.current_stage = 1
    if "raw_input" not in st.session_state:
        st.session_state.raw_input = ""
    if "doc_type" not in st.session_state:
        st.session_state.doc_type = None
    if "structured_spec" not in st.session_state:
        st.session_state.structured_spec = ""
    if "audit_report" not in st.session_state:
        st.session_state.audit_report = None
    if "traceability_data" not in st.session_state:
        st.session_state.traceability_data = []
    if "risk_score" not in st.session_state:
        st.session_state.risk_score = 0
    if "rigor_level" not in st.session_state:
        st.session_state.rigor_level = RigorLevel.STANDARD
    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False


def reset_workflow():
    """Reset the workflow to initial state."""
    st.session_state.workflow_status = WorkflowStatus.DRAFT
    st.session_state.current_stage = 1
    st.session_state.raw_input = ""
    st.session_state.doc_type = None
    st.session_state.structured_spec = ""
    st.session_state.audit_report = None
    st.session_state.traceability_data = []
    st.session_state.risk_score = 0


# Initialize state
init_workflow_state()


# =============================================================================
# Header
# =============================================================================

st.title("🛡️ Guardian Gateway")
st.caption("Autonomous Infrastructure for Mathematical AI Verification")
st.divider()


# =============================================================================
# Stage Progress Indicator
# =============================================================================

def render_stage_progress():
    """Render the workflow stage progress indicator."""
    stages = ["📝 Triage", "📋 Structure", "🔍 Audit", "✅ Approve"]
    current = st.session_state.current_stage
    
    cols = st.columns(4)
    for i, (col, stage_name) in enumerate(zip(cols, stages), 1):
        with col:
            if i < current:
                st.success(f"~~{stage_name}~~")
            elif i == current:
                st.info(f"**{stage_name}**")
            else:
                st.markdown(f"*{stage_name}*")


# =============================================================================
# Stage 1: Triage
# =============================================================================

def render_stage_1_triage():
    """Render Stage 1: Input and Classification."""
    st.markdown("### Stage 1: Triage")
    st.markdown("Paste your specification text below. We'll classify it to ensure it's a valid functional spec.")
    
    # Sample spec for demo
    sample_spec = """Rewards System Specification

Users earn points by completing tasks. Each task completion awards 10 points.
Premium users receive a 2x multiplier on all point earnings.

Users can redeem points for rewards from the reward catalog.
Each reward has a point cost. When a user redeems a reward, their points are deducted.

Monthly leaderboards track top point earners. The top 3 users receive bonus rewards.
"""
    
    # Text area for input
    spec_text = st.text_area(
        "Specification Input",
        value=st.session_state.raw_input if st.session_state.raw_input else sample_spec,
        height=300,
        help="Paste your English specification here",
        key="triage_input"
    )
    
    col1, col2 = st.columns([1, 3])
    with col1:
        analyze_clicked = st.button("🔍 Analyze", type="primary", key="analyze_btn")
    
    if analyze_clicked and spec_text:
        st.session_state.raw_input = spec_text
        
        with st.spinner("Classifying document..."):
            result = run_triage(spec_text)
        
        if result.error:
            st.error(f"Classification Error: {result.error}")
            return
        
        st.session_state.doc_type = result.doc_type
        
        if result.doc_type == DocType.JUNK:
            st.error("❌ **Invalid Input**: Please provide a functional requirement or specification document.")
            st.info(f"Classification confidence: {result.confidence:.0%}")
        elif result.doc_type == DocType.CODE:
            st.warning("🔄 **Code Detected**: This appears to be source code. Redirecting to Gateway tab...")
            st.info("Please use the **Gateway** tab to verify code against contracts.")
        elif result.doc_type == DocType.SPEC:
            st.success(f"✅ **Valid Specification Detected** (confidence: {result.confidence:.0%})")
            st.session_state.current_stage = 2
            st.session_state.workflow_status = WorkflowStatus.ANALYZING
            st.rerun()


# =============================================================================
# Stage 2: Structure
# =============================================================================

def render_stage_2_structure():
    """Render Stage 2: Normalization to Standard Template."""
    st.markdown("### Stage 2: Structure")
    st.markdown("Normalizing your specification to the Guardian Standard Template...")
    
    # Check if we need to run structuring
    if not st.session_state.structured_spec:
        with st.spinner("Standardizing specification..."):
            result = run_structuring(st.session_state.raw_input)
        
        if result.error:
            st.error(f"Structuring Error: {result.error}")
            if st.button("⬅️ Back to Triage"):
                st.session_state.current_stage = 1
                st.rerun()
            return
        
        st.session_state.structured_spec = result.structured_spec
        
        if not result.validation_passed:
            st.warning("⚠️ **Normalization Warning**: The structured spec may be missing required sections. Please review and edit.")
    
    # Display the structured spec (editable)
    st.markdown("#### Structured Specification")
    st.caption("Review and edit the normalized specification below:")
    
    edited_spec = st.text_area(
        "Structured Spec",
        value=st.session_state.structured_spec,
        height=400,
        key="structure_editor",
        label_visibility="collapsed"
    )
    
    # Update if edited
    if edited_spec != st.session_state.structured_spec:
        st.session_state.structured_spec = edited_spec
    
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("⬅️ Back", key="back_to_triage"):
            st.session_state.current_stage = 1
            st.session_state.structured_spec = ""
            st.rerun()
    with col2:
        if st.button("🔍 Continue to Audit", type="primary", key="continue_to_audit"):
            st.session_state.current_stage = 3
            st.rerun()


# =============================================================================
# Stage 3: Audit & Traceability
# =============================================================================

def render_stage_3_audit():
    """Render Stage 3: Audit with Traceability Matrix."""
    st.markdown("### Stage 3: Audit & Traceability")
    
    # Controls row
    col_rigor, col_btn, col_spacer = st.columns([2, 1, 2])
    
    with col_rigor:
        rigor_options = {
            "🟢 Sanity (Lenient)": RigorLevel.SANITY,
            "🟡 Standard (Default)": RigorLevel.STANDARD,
            "🔴 Paranoid (Strict)": RigorLevel.PARANOID
        }
        selected_rigor = st.selectbox(
            "Rigor Level",
            options=list(rigor_options.keys()),
            index=1,  # Default to Standard
            help="Controls how strict the risk threshold is for approval"
        )
        st.session_state.rigor_level = rigor_options[selected_rigor]
    
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)  # Spacing
        run_audit_clicked = st.button("🔍 Run Audit", type="primary", key="run_audit_btn")
    
    # Run audit if clicked
    if run_audit_clicked:
        auditor = SpecAuditor()
        
        if not auditor.is_configured():
            st.error(f"⚠️ {auditor.get_configuration_error()}")
            st.info("💡 Create a `.env` file with your `GEMINI_API_KEY=your_key_here`")
            return
        
        with st.spinner("Running compliance audit with traceability extraction..."):
            result = auditor.audit_spec(st.session_state.structured_spec)
        
        if result.error:
            st.error(f"Audit Error: {result.error}")
            return
        
        st.session_state.audit_report = result
        st.session_state.traceability_data = result.traceability_matrix
        
        # Calculate risk
        critical_count = sum(1 for g in result.gaps if g.severity == "critical")
        warning_count = sum(1 for g in result.gaps if g.severity == "warning")
        st.session_state.risk_score = (10 * critical_count) + warning_count
        
        st.session_state.workflow_status = WorkflowStatus.READY
    
    # Display results if audit has been run
    if st.session_state.audit_report:
        _display_audit_results_with_traceability(st.session_state.audit_report)
        
        st.divider()
        
        # Gap Resolution Section
        report = st.session_state.audit_report
        critical_count = sum(1 for g in report.gaps if g.severity == "critical")
        warning_count = sum(1 for g in report.gaps if g.severity == "warning")
        
        if critical_count > 0 or warning_count > 0:
            st.markdown("#### 🔧 Resolve Issues")
            st.info(f"""
            **To resolve the {critical_count} critical gap(s) and {warning_count} warning(s):**
            1. Click "✏️ Edit Specification" below to modify the structured spec
            2. Address the critical gaps and warnings in the spec text
            3. Click "💾 Save & Re-audit" to verify your changes resolved the issues
            4. Repeat until all gaps are addressed to your satisfaction
            """)
            
            col_edit, col_reaudit = st.columns([1, 1])
            
            with col_edit:
                if st.button("✏️ Edit Specification", type="secondary", key="edit_spec_btn"):
                    st.session_state.edit_mode = True
                    st.rerun()
            
            with col_reaudit:
                if st.button("🔄 Re-audit Spec", type="primary", key="reaudit_btn"):
                    # Clear previous audit to force re-run
                    st.session_state.audit_report = None
                    st.rerun()
        
        # Edit Mode - Show editable spec
        if st.session_state.get("edit_mode", False):
            st.divider()
            st.markdown("#### ✏️ Edit Structured Specification")
            st.caption("Modify the specification below to address the identified gaps. When finished, save and re-audit.")
            
            edited_spec = st.text_area(
                "Structured Spec",
                value=st.session_state.structured_spec,
                height=400,
                key="audit_spec_editor",
                label_visibility="collapsed"
            )
            
            # Update structured spec if edited
            if edited_spec != st.session_state.structured_spec:
                st.session_state.structured_spec = edited_spec
            
            col_save, col_cancel = st.columns([1, 1])
            with col_save:
                if st.button("💾 Save & Re-audit", type="primary", key="save_and_reaudit"):
                    st.session_state.audit_report = None
                    st.session_state.edit_mode = False
                    st.rerun()
            with col_cancel:
                if st.button("❌ Cancel Editing", key="cancel_edit"):
                    st.session_state.edit_mode = False
                    st.rerun()
        
        st.divider()
        
        # Navigation buttons
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("⬅️ Back to Structure", key="back_to_structure"):
                st.session_state.current_stage = 2
                st.session_state.audit_report = None
                st.session_state.edit_mode = False
                st.rerun()
        with col2:
            # Change button style based on gap status
            if critical_count == 0 and warning_count == 0:
                button_label = "✅ Continue to Approval"
                button_type = "primary"
            else:
                button_label = f"⚠️ Continue with Issues ({critical_count + warning_count})"
                button_type = "secondary"
            
            if st.button(button_label, type=button_type, key="continue_to_approval"):
                st.session_state.current_stage = 4
                st.rerun()
    else:
        st.info("👆 Click 'Run Audit' to analyze the specification for logic gaps and generate the traceability matrix.")
        
        # Show structured spec preview
        with st.expander("View Structured Specification"):
            st.code(st.session_state.structured_spec, language="markdown")


def _display_audit_results_with_traceability(report: GapReport):
    """Display audit results with traceability matrix."""
    
    # Two-column layout: Tagged Spec | Dafny Skeleton
    col_spec, col_dafny = st.columns([1, 1])
    
    with col_spec:
        st.markdown("#### 📝 Tagged Specification")
        if report.tagged_spec:
            st.markdown(report.tagged_spec)
        else:
            st.info("No tagged specification generated.")
    
    with col_dafny:
        st.markdown("#### 📄 Dafny Skeleton")
        if report.dafny_skeleton:
            st.code(report.dafny_skeleton, language="csharp")
        else:
            st.info("No Dafny skeleton generated.")
    
    st.divider()
    
    # Gaps and Ambiguities
    col_gaps, col_ambig = st.columns([1, 1])
    
    with col_gaps:
        st.markdown("#### 🚨 Logic Gaps")
        if report.gaps:
            for gap in report.gaps:
                if gap.severity == "critical":
                    st.error(f"**CRITICAL**: {gap.description}")
                else:
                    st.warning(f"**Warning**: {gap.description}")
        else:
            st.success("No logic gaps detected!")
    
    with col_ambig:
        st.markdown("#### 🤔 Ambiguities")
        if report.ambiguities:
            for amb in report.ambiguities:
                st.info(f"• {amb}")
        else:
            st.success("No ambiguities detected!")
    
    st.divider()
    
    # Traceability Matrix
    st.markdown("#### 🔗 Traceability Matrix")
    
    if report.traceability_matrix:
        # Convert to DataFrame for display
        matrix_data = []
        for entry in report.traceability_matrix:
            # Status badge
            status_badges = {
                "Pending": "🟡 Pending",
                "Implemented": "🔵 Implemented",
                "Verified": "🟢 Verified",
                "Missing": "🔴 Missing",
                "Obsolete": "⚫ Obsolete"
            }
            status_display = status_badges.get(entry.status, f"⚪ {entry.status}")
            
            matrix_data.append({
                "ID": entry.id,
                "Requirement": entry.source_text[:80] + "..." if len(entry.source_text) > 80 else entry.source_text,
                "Status": status_display,
                "Logic Link": entry.code_line if entry.code_line else "-"
            })
        
        df = pd.DataFrame(matrix_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No traceability entries found. The auditor may not have identified atomic requirements.")
    
    # Summary metrics
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    critical_count = sum(1 for g in report.gaps if g.severity == "critical")
    warning_count = sum(1 for g in report.gaps if g.severity == "warning")
    
    col1.metric("Critical Gaps", critical_count)
    col2.metric("Warnings", warning_count)
    col3.metric("Ambiguities", len(report.ambiguities))
    col4.metric("Requirements Traced", len(report.traceability_matrix))


# =============================================================================
# Stage 4: Approval
# =============================================================================

def render_stage_4_approval():
    """Render Stage 4: Risk Assessment and Finalization."""
    st.markdown("### Stage 4: Approval")
    
    if not st.session_state.audit_report:
        st.warning("Please complete the audit stage first.")
        if st.button("⬅️ Back to Audit"):
            st.session_state.current_stage = 3
            st.rerun()
        return
    
    report = st.session_state.audit_report
    
    # Calculate risk assessment
    critical_count = sum(1 for g in report.gaps if g.severity == "critical")
    warning_count = sum(1 for g in report.gaps if g.severity == "warning")
    
    assessment = assess_risk(critical_count, warning_count, st.session_state.rigor_level)
    status_emoji, status_text = get_risk_status(assessment)
    
    # Risk Score Display
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Risk Score",
            assessment.score,
            delta=None
        )
    
    with col2:
        st.metric(
            "Threshold",
            assessment.threshold,
            delta=f"{st.session_state.rigor_level.value.title()} Mode"
        )
    
    with col3:
        if assessment.is_acceptable:
            st.success(f"## {status_emoji} {status_text}")
        else:
            st.warning(f"## {status_emoji} {status_text}")
    
    st.divider()
    
    # Summary of findings
    st.markdown("#### 📊 Audit Summary")
    
    col_summary1, col_summary2 = st.columns(2)
    
    with col_summary1:
        st.markdown(f"""
        - **Critical Gaps:** {critical_count}
        - **Warnings:** {warning_count}
        - **Ambiguities:** {len(report.ambiguities)}
        - **Requirements Traced:** {len(report.traceability_matrix)}
        """)
    
    with col_summary2:
        if assessment.is_acceptable:
            st.success("✅ Specification meets the selected rigor threshold and is ready for finalization.")
        else:
            st.warning("⚠️ Specification exceeds the risk threshold. Consider addressing critical gaps before finalizing.")
    
    # Show recommendation to resolve issues if present
    if critical_count > 0 or warning_count > 0:
        st.divider()
        st.warning(f"""
        **⚠️ Unresolved Issues Detected**
        
        You have **{critical_count} critical gap(s)** and **{warning_count} warning(s)** that haven't been addressed.
        
        **Recommended:** Go back to Stage 3 to edit the specification and resolve these issues before finalizing.
        """)
        
        if st.button("⬅️ Go Back to Resolve Issues", key="back_to_resolve", type="primary"):
            st.session_state.current_stage = 3
            st.rerun()
    
    st.divider()
    
    # Finalization controls
    is_finalized = st.session_state.workflow_status == WorkflowStatus.FINALIZED
    
    if is_finalized:
        st.success("🔒 **Specification Finalized**")
        st.info("The specification is now locked and ready for Dafny code generation.")
        
        # Show finalized spec (read-only)
        with st.expander("View Finalized Specification", expanded=False):
            st.code(st.session_state.structured_spec, language="markdown")
        
        # Show Dafny skeleton
        with st.expander("View Dafny Skeleton", expanded=True):
            st.code(report.dafny_skeleton, language="csharp")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🔄 Start New Workflow", key="restart_workflow"):
                reset_workflow()
                st.rerun()
        with col2:
            st.download_button(
                "📥 Download Dafny Skeleton",
                data=report.dafny_skeleton,
                file_name="specification.dfy",
                mime="text/plain"
            )
    else:
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("⬅️ Back to Audit", key="back_to_audit"):
                st.session_state.current_stage = 3
                st.rerun()
        
        with col2:
            # Finalize button - enabled even if not acceptable (with warning)
            finalize_clicked = st.button(
                "🔒 Finalize Spec",
                type="primary",
                key="finalize_btn"
            )
            
            if finalize_clicked:
                if not assessment.is_acceptable:
                    st.session_state.show_finalize_warning = True
                else:
                    st.session_state.workflow_status = WorkflowStatus.FINALIZED
                    st.rerun()
        
        # Confirmation dialog for risky finalization
        if st.session_state.get("show_finalize_warning", False):
            st.warning("⚠️ The specification has unresolved issues. Are you sure you want to finalize?")
            col_confirm1, col_confirm2 = st.columns([1, 1])
            with col_confirm1:
                if st.button("Yes, Finalize Anyway", key="confirm_finalize"):
                    st.session_state.workflow_status = WorkflowStatus.FINALIZED
                    st.session_state.show_finalize_warning = False
                    st.rerun()
            with col_confirm2:
                if st.button("Cancel", key="cancel_finalize"):
                    st.session_state.show_finalize_warning = False
                    st.rerun()


# =============================================================================
# Legacy Tabs (Lens & Gateway)
# =============================================================================

def render_lens_tab():
    """
    Render the Spec Lens tab.
    Visualizes Dafny contracts as human-readable cards.
    """
    st.markdown("""
    The **Spec Lens** translates formal Dafny contracts into human-readable cards.
    Upload a `.dfy` file to see its guardrails (preconditions) and promises (postconditions).
    """)
    
    # File upload section
    uploaded_file = st.file_uploader(
        "Upload a Dafny contract file",
        type=["dfy"],
        help="Upload a .dfy file containing Dafny method specifications",
        key="lens_uploader"
    )
    
    # Demo mode with sample file
    use_demo = st.checkbox("Use demo file (interface.dfy)", value=uploaded_file is None, key="lens_demo")
    
    # Get the source code
    source_code = None
    
    if uploaded_file is not None:
        source_code = uploaded_file.read().decode("utf-8")
    elif use_demo:
        try:
            with open("tests/fixtures/interface.dfy", "r") as f:
                source_code = f.read()
        except FileNotFoundError:
            st.warning("Demo file not found at tests/fixtures/interface.dfy")
    
    # Parse and display
    if source_code:
        st.divider()
        
        # Parse the Dafny source
        contract = parse_dafny_source(source_code)
        
        # Two-column layout
        col_left, col_right = st.columns([1, 1])
        
        # Left column: Raw Code
        with col_left:
            st.markdown("### 📄 Raw Contract")
            st.code(source_code, language="csharp")  # csharp syntax highlighting works well for Dafny
        
        # Right column: Visual Cards
        with col_right:
            st.markdown("### 🎴 Contract Cards")
            
            if not contract.methods:
                st.info("No methods found in the contract.")
            else:
                for method in contract.methods:
                    # Method card as an expander
                    with st.expander(f"**{method.name}**", expanded=True):
                        # Method signature
                        st.caption(method.signature)
                        
                        # Guardrails (Preconditions)
                        if method.preconditions:
                            st.markdown("#### 🟢 Guardrails (Preconditions)")
                            for clause in method.preconditions:
                                humanized = humanize_clause(clause, "requires")
                                icon = get_clause_icon("requires")
                                
                                # Display both raw and humanized
                                st.markdown(f"{icon} **{humanized}**")
                                st.code(clause, language="csharp")
                        else:
                            st.markdown("*No preconditions defined*")
                        
                        st.divider()
                        
                        # Promises (Postconditions)
                        if method.postconditions:
                            st.markdown("#### 🔵 Promises (Postconditions)")
                            for clause in method.postconditions:
                                humanized = humanize_clause(clause, "ensures")
                                icon = get_clause_icon("ensures")
                                
                                # Display both raw and humanized
                                st.markdown(f"{icon} **{humanized}**")
                                st.code(clause, language="csharp")
                        else:
                            st.markdown("*No postconditions defined*")
            
            # Summary stats
            st.divider()
            st.markdown("### 📊 Contract Summary")
            total_methods = len(contract.methods)
            total_preconditions = sum(len(m.preconditions) for m in contract.methods)
            total_postconditions = sum(len(m.postconditions) for m in contract.methods)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Methods", total_methods)
            col2.metric("Guardrails", total_preconditions)
            col3.metric("Promises", total_postconditions)
    
    else:
        st.info("👆 Upload a Dafny file or enable the demo to get started.")


def render_gateway_tab():
    """
    Render the Gateway tab.
    Verifies Python implementations against Dafny contracts.
    """
    st.markdown("""
    The **Gateway** verifies that Python code satisfies formal Dafny contracts.
    It transpiles Python to Dafny and runs the Dafny verifier to check correctness.
    """)
    
    # Initialize the verifier
    verifier = CodeVerifier()
    
    # Check configuration status
    if not verifier.is_configured():
        st.warning(f"⚠️ {verifier.get_configuration_error()}")
        st.info("💡 Create a `.env` file with your `GEMINI_API_KEY=your_key_here`")
    
    # Load sample contract from fixture
    sample_contract = ""
    try:
        with open("tests/fixtures/interface.dfy", "r") as f:
            sample_contract = f.read()
    except FileNotFoundError:
        sample_contract = """// Sample Dafny Contract
trait Calculator {
    method Add(a: int, b: int) returns (result: int)
        ensures result == a + b
}
"""
    
    # Sample Python implementation
    sample_python = """def send_kudos(db: dict, sender: str, receiver: str, amount: int):
    '''
    Transfer kudos points from sender to receiver.
    
    Args:
        db: Dictionary mapping user IDs to their point balances
        sender: The ID of the user sending kudos
        receiver: The ID of the user receiving kudos
        amount: The number of points to transfer
    
    Returns:
        Tuple of (new_db, success) where new_db is the updated database
        and success indicates if the transfer was completed.
    '''
    # Create a copy of the database
    new_db = db.copy()
    
    # Deduct from sender
    new_db[sender] = db[sender] - amount
    
    # Add to receiver
    new_db[receiver] = db[receiver] + amount
    
    return new_db, True
"""
    
    st.divider()
    
    # Two-column layout
    col_contract, col_python = st.columns([1, 1])
    
    # Left column: Contract (read-only display)
    with col_contract:
        st.markdown("### 📜 Dafny Contract (Specification)")
        st.caption("This is the formal contract that your code must satisfy.")
        st.code(sample_contract, language="csharp")
    
    # Right column: Python implementation (editable)
    with col_python:
        st.markdown("### 🐍 Python Implementation")
        st.caption("Write or paste your Python implementation here.")
        python_code = st.text_area(
            "Python Code",
            value=sample_python,
            height=400,
            help="Enter the Python function that implements the contract logic",
            key="gateway_python_input",
            label_visibility="collapsed"
        )
    
    st.divider()
    
    # Verify button
    col_btn, col_spacer = st.columns([1, 3])
    with col_btn:
        verify_clicked = st.button(
            "🔐 Verify Logic",
            type="primary",
            disabled=not verifier.is_configured(),
            key="verify_button"
        )
    
    # Process verification
    if verify_clicked and python_code:
        with st.status("Verifying...", expanded=True) as status:
            st.write("🔄 Transpiling Python to Dafny...")
            result = verifier.verify(sample_contract, python_code)
            
            if result.error:
                status.update(label="Verification Error", state="error", expanded=True)
            elif result.verified:
                status.update(label="Verification Passed!", state="complete", expanded=True)
            else:
                status.update(label="Verification Failed", state="error", expanded=True)
        
        # Display results
        _display_verification_results(result)
    
    # Show placeholder if not verified yet
    elif not verify_clicked:
        st.info("👆 Click 'Verify Logic' to check if your Python code satisfies the contract.")


def _display_verification_results(result: VerificationResult):
    """
    Display the verification results.
    
    Args:
        result: The VerificationResult from the verifier.
    """
    st.divider()
    
    # Error case
    if result.error:
        st.error(f"**Error**: {result.error}")
        if result.dafny_output:
            with st.expander("Dafny Output (Debug)", expanded=False):
                st.code(result.dafny_output, language="text")
        return
    
    # Success/Failure display
    if result.verified:
        st.success("✅ **Verification Successful!** Your code satisfies all contract requirements.")
    else:
        st.error("❌ **Verification Failed.** Your code does not satisfy the contract.")
    
    # Show transpiled code
    st.markdown("### 🔄 Transpiled Dafny Code")
    if result.transpiled_code:
        st.code(result.transpiled_code, language="csharp")
    else:
        st.info("No transpiled code available.")
    
    # Show Dafny output
    if result.dafny_output:
        st.markdown("### 📋 Dafny Verifier Output")
        with st.expander("View Full Output", expanded=not result.verified):
            st.code(result.dafny_output, language="text")
    
    # Summary
    st.divider()
    col1, col2 = st.columns(2)
    col1.metric("Status", "PASSED" if result.verified else "FAILED")
    col2.metric("Result", result.logs)


# =============================================================================
# Main App Layout
# =============================================================================

# Create tabs
tab_workflow, tab_lens, tab_gateway = st.tabs(["🔄 Design Studio", "📊 Spec Lens", "🔐 Gateway"])

with tab_workflow:
    # Show stage progress
    render_stage_progress()
    st.divider()
    
    # Render current stage
    if st.session_state.current_stage == 1:
        render_stage_1_triage()
    elif st.session_state.current_stage == 2:
        render_stage_2_structure()
    elif st.session_state.current_stage == 3:
        render_stage_3_audit()
    elif st.session_state.current_stage == 4:
        render_stage_4_approval()

with tab_lens:
    render_lens_tab()

with tab_gateway:
    render_gateway_tab()

# Footer
st.divider()
st.caption("Guardian Gateway - Autonomous Infrastructure for Mathematical AI Verification")
