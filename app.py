# Guardian Gateway - Streamlit Frontend
# The Lens + Auditor: Visualization dashboard for formal proofs
# Imperative Shell: UI layer that uses the pure Functional Core

import streamlit as st
from core_parser import (
    DafnyParser, 
    parse_dafny_source, 
    humanize_clause, 
    get_clause_icon
)
from core_auditor import SpecAuditor, GapReport
from core_gateway import CodeVerifier, VerificationResult

# Page configuration
st.set_page_config(
    page_title="Guardian Gateway",
    page_icon="🛡️",
    layout="wide"
)

# Header
st.title("🛡️ Guardian Gateway")
st.caption("Autonomous Infrastructure for Mathematical AI Verification")

st.divider()


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


def render_auditor_tab():
    """
    Render the Spec Auditor tab.
    Uses LLM to analyze specifications for logic gaps and generate Dafny skeletons.
    """
    st.markdown("""
    The **Spec Auditor** analyzes English specifications using AI to find logic gaps,
    ambiguities, and generates formal Dafny skeleton code.
    """)
    
    # Initialize the auditor
    auditor = SpecAuditor()
    
    # Check configuration status
    if not auditor.is_configured():
        st.warning(f"⚠️ {auditor.get_configuration_error()}")
        st.info("💡 Create a `.env` file with your `GEMINI_API_KEY=your_key_here`")
    
    # Sample spec for demo
    sample_spec = """Rewards System Specification

Users earn points by completing tasks. Each task completion awards 10 points.
Premium users receive a 2x multiplier on all point earnings.

Users can redeem points for rewards from the reward catalog.
Each reward has a point cost. When a user redeems a reward, their points are deducted.

Monthly leaderboards track top point earners. The top 3 users receive bonus rewards.
"""
    
    # Text area for spec input
    spec_text = st.text_area(
        "Paste Specification Text",
        value=sample_spec,
        height=250,
        help="Paste your English specification here for analysis",
        key="auditor_spec_input"
    )
    
    # Audit button
    col_btn, col_status = st.columns([1, 3])
    with col_btn:
        audit_clicked = st.button(
            "🔍 Audit Specification",
            type="primary",
            disabled=not auditor.is_configured(),
            key="audit_button"
        )
    
    # Process audit
    if audit_clicked and spec_text:
        with st.spinner("Analyzing specification with Gemini..."):
            result = auditor.audit_spec(spec_text)
        
        # Display results
        _display_audit_results(result)
    
    # Show placeholder if not audited yet
    elif not audit_clicked:
        st.info("👆 Click 'Audit Specification' to analyze the spec for logic gaps.")


def _display_audit_results(result: GapReport):
    """
    Display the audit results in a structured format.
    
    Args:
        result: The GapReport from the auditor.
    """
    if result.error:
        st.error(f"Audit Failed: {result.error}")
        if result.raw_response:
            with st.expander("Raw Response (Debug)"):
                st.text(result.raw_response)
        return
    
    st.divider()
    st.markdown("## 📋 Audit Results")
    
    # Two-column layout for gaps and ambiguities
    col_gaps, col_ambig = st.columns([1, 1])
    
    # Display Gaps
    with col_gaps:
        st.markdown("### 🚨 Logic Gaps")
        if result.gaps:
            for gap in result.gaps:
                if gap.severity == "critical":
                    st.error(f"**CRITICAL**: {gap.description}")
                else:
                    st.warning(f"**Warning**: {gap.description}")
        else:
            st.success("No logic gaps detected!")
    
    # Display Ambiguities
    with col_ambig:
        st.markdown("### 🤔 Ambiguities")
        if result.ambiguities:
            for amb in result.ambiguities:
                st.info(f"• {amb}")
        else:
            st.success("No ambiguities detected!")
    
    # Display Dafny Skeleton
    st.divider()
    st.markdown("### 📝 Generated Dafny Skeleton")
    if result.dafny_skeleton:
        st.code(result.dafny_skeleton, language="csharp")
        
        # Copy hint
        st.caption("💡 Use this skeleton as a starting point for formal verification.")
    else:
        st.info("No Dafny skeleton was generated.")
    
    # Summary metrics
    st.divider()
    col1, col2, col3 = st.columns(3)
    critical_count = sum(1 for g in result.gaps if g.severity == "critical")
    warning_count = sum(1 for g in result.gaps if g.severity == "warning")
    
    col1.metric("Critical Gaps", critical_count)
    col2.metric("Warnings", warning_count)
    col3.metric("Ambiguities", len(result.ambiguities))


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


# Main App Layout with Tabs
tab_lens, tab_auditor, tab_gateway = st.tabs(["📊 Spec Lens", "🔍 Spec Auditor", "🔐 Gateway"])

with tab_lens:
    render_lens_tab()

with tab_auditor:
    render_auditor_tab()

with tab_gateway:
    render_gateway_tab()

# Footer
st.divider()
st.caption("Guardian Gateway - Autonomous Infrastructure for Mathematical AI Verification")
