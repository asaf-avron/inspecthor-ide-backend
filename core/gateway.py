# Guardian Gateway - Core Gateway
# Verification engine that transpiles Python to Dafny and verifies against contracts
# Functional Core: No Streamlit imports allowed

"""
The Code Verifier: Transpiles Python code to Dafny and verifies it against contracts.
Uses Google Gemini for transpilation and Dafny CLI for formal verification.
"""

import os
import subprocess
import tempfile
import json
import glob
from dataclasses import dataclass
from typing import Optional

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class VerificationResult:
    """
    Represents the result of a verification attempt.
    
    Attributes:
        verified: True if the code passes all Dafny checks
        logs: Human-readable summary of the verification
        dafny_output: Raw output from the Dafny CLI
        transpiled_code: The generated Dafny class code
        error: Error message if verification failed due to an error
    """
    verified: bool
    logs: str
    dafny_output: str = ""
    transpiled_code: str = ""
    error: Optional[str] = None


# System prompt for the transpiler
TRANSPILER_PROMPT = """You are a Transpiler that converts Python functions to Dafny implementations.

INPUT 1 (Dafny Trait):
You will receive a Dafny trait that defines the contract interface with:
- Method signatures
- Preconditions (requires clauses)
- Postconditions (ensures clauses)

INPUT 2 (Python Function):
You will receive a Python function that implements the logic.

YOUR TASK:
Generate a Dafny class that:
1. Extends the given trait
2. Implements all methods from the trait
3. Contains the logic translated from the Python function
4. Satisfies all requires/ensures clauses

CRITICAL RULES:
- Output ONLY the Dafny class code, no explanations
- Do NOT include the trait definition in your output
- Do NOT wrap the code in markdown code blocks
- The class must compile and verify with Dafny
- Match the method signatures exactly from the trait
- Translate Python logic to equivalent Dafny logic

Example output format:
class ImplementationName extends TraitName {
    method MethodName(...) returns (...) {
        // implementation
    }
}"""


class PromptLoader:
    """
    Loads and formats example prompts from JSON files for few-shot learning.
    
    Manages the library of "Golden Examples" that teach the LLM correct
    Dafny transpilation patterns without hardcoding them in Python.
    """
    
    DEFAULT_EXAMPLES_DIR = "assets/examples"
    
    @staticmethod
    def load_examples(dir_path: Optional[str] = None) -> str:
        """
        Load all JSON examples from the directory and format for LLM prompt.
        
        Args:
            dir_path: Path to examples directory. Defaults to assets/examples/.
            
        Returns:
            Formatted string with Input -> Output pairs for few-shot learning.
            Returns empty string if no examples found or directory doesn't exist.
        """
        if dir_path is None:
            # Resolve relative to this file's location
            base_dir = os.path.dirname(os.path.abspath(__file__))
            dir_path = os.path.join(base_dir, PromptLoader.DEFAULT_EXAMPLES_DIR)
        
        # Check if directory exists
        if not os.path.isdir(dir_path):
            return ""
        
        # Find all JSON files
        pattern = os.path.join(dir_path, "*.json")
        json_files = glob.glob(pattern)
        
        if not json_files:
            return ""
        
        examples = []
        for json_file in sorted(json_files):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Extract required fields
                name = data.get("name", os.path.basename(json_file))
                contract = data.get("contract", "")
                python = data.get("python", "")
                dafny_impl = data.get("dafny_impl", "")
                
                # Skip if missing required fields
                if not contract or not python or not dafny_impl:
                    continue
                
                # Format as example block
                example_block = f"""--- EXAMPLE: {name} ---
INPUT (Trait):
{contract}

INPUT (Python):
{python}

OUTPUT (Dafny Class):
{dafny_impl}
--- END EXAMPLE ---"""
                examples.append(example_block)
                
            except (json.JSONDecodeError, IOError):
                # Skip malformed files silently
                continue
        
        if not examples:
            return ""
        
        # Join all examples with separator
        header = "\n\n=== FEW-SHOT EXAMPLES (Follow these patterns) ===\n\n"
        return header + "\n\n".join(examples) + "\n\n=== END EXAMPLES ===\n"


class CodeVerifier:
    """
    Verification engine that transpiles Python to Dafny and verifies against contracts.
    
    Preconditions: GEMINI_API_KEY must be set in environment.
    Postconditions: Returns a VerificationResult with verification status.
    """
    
    DEFAULT_MODEL = "gemini-2.0-flash-001"
    FALLBACK_MODEL = "gemini-2.0-flash-001"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the verifier with an API key.
        
        Args:
            api_key: Google Gemini API key. If not provided, reads from 
                     GEMINI_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._model = self.DEFAULT_MODEL
        self._init_error: Optional[str] = None
        
        if genai is None:
            self._init_error = "google-genai package not installed. Run: pip install google-genai"
        elif not self.api_key:
            self._init_error = "GEMINI_API_KEY not found. Set it in .env file or environment."
        else:
            self._init_error = None
            self._configure_genai()
    
    def _configure_genai(self) -> None:
        """Configure the Gemini API with the provided key."""
        if genai and self.api_key:
            try:
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                self._init_error = f"Failed to initialize client: {e}"
    
    def is_configured(self) -> bool:
        """Check if the verifier is properly configured."""
        return self._init_error is None and hasattr(self, '_client')
    
    def get_configuration_error(self) -> Optional[str]:
        """Get the configuration error message if any."""
        return self._init_error
    
    def verify(self, contract_str: str, python_str: str) -> VerificationResult:
        """
        Verify Python code against a Dafny contract.
        
        Args:
            contract_str: The Dafny trait/contract code.
            python_str: The Python implementation to verify.
            
        Returns:
            VerificationResult with verification status and logs.
        """
        # Check configuration
        if self._init_error:
            return VerificationResult(
                verified=False,
                logs="Configuration error",
                error=self._init_error
            )
        
        if not contract_str or not contract_str.strip():
            return VerificationResult(
                verified=False,
                logs="Contract is empty",
                error="Dafny contract text is empty."
            )
        
        if not python_str or not python_str.strip():
            return VerificationResult(
                verified=False,
                logs="Python code is empty",
                error="Python implementation text is empty."
            )
        
        # Step 1: Transpile Python to Dafny
        transpile_result = self._transpile(contract_str, python_str)
        if transpile_result.error:
            return transpile_result
        
        transpiled_code = transpile_result.transpiled_code
        
        # Step 2: Combine contract + implementation
        combined_dafny = f"{contract_str}\n\n{transpiled_code}"
        
        # Step 3: Write to temp file and verify
        verify_result = self._run_dafny_verify(combined_dafny)
        verify_result.transpiled_code = transpiled_code
        
        return verify_result
    
    def _transpile(self, contract_str: str, python_str: str) -> VerificationResult:
        """
        Transpile Python code to Dafny using Gemini.
        
        Uses dynamic few-shot examples from assets/examples/*.json to improve
        transpilation accuracy.
        
        Args:
            contract_str: The Dafny contract/trait.
            python_str: The Python implementation.
            
        Returns:
            VerificationResult with transpiled_code set on success.
        """
        # Load dynamic examples for few-shot learning
        examples_text = PromptLoader.load_examples()
        
        # FAITHFUL TRANSPILATION PROMPT
        prompt = f"""You are a Python-to-Dafny Transpiler.

YOUR GOAL: 
FAITHFULLY translate the Python code into Dafny. The Dafny code must have the EXACT SAME LOGIC as the Python.

CRITICAL RULE - FAITHFUL TRANSPILATION:
- You MUST translate the Python code EXACTLY as written
- If Python says `x + y`, Dafny must say `x + y`
- If Python says `x - y`, Dafny must say `x - y`  
- Do NOT "fix" or "correct" the Python logic
- Do NOT look at the ensures clauses to figure out what the code "should" do
- Your job is to TRANSLATE, not to WRITE CORRECT CODE

GENERATION RULES (FOLLOW IN ORDER):
1. Define the Class extending the Trait.
2. Do NOT re-declare predicates or functions from the Trait (they are inherited automatically).
3. Define the Method Signature exactly as in the Trait.
4. COPY ALL `requires` CLAUSES.
5. COPY ALL `ensures` CLAUSES.
6. Write the Method Body by DIRECTLY TRANSLATING the Python line-by-line.

OUTPUT RULES:
- Output ONLY the Dafny class code, no explanations
- Do NOT include the trait definition in your output
- Do NOT wrap the code in markdown code blocks
- Do NOT re-declare predicates/functions that are already defined in the trait

---
{examples_text}
---

### REAL INPUT (Contract)
{contract_str}

### REAL INPUT (Python Logic)
{python_str}

### OUTPUT (The Full Dafny Class)
"""
        
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt
            )
            raw_text = response.text or ""
            
            # Clean up the response - remove markdown code blocks if present
            cleaned = raw_text.strip()
            if cleaned.startswith("```dafny"):
                cleaned = cleaned[8:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
            
            return VerificationResult(
                verified=False,  # Not verified yet, just transpiled
                logs="Transpilation successful",
                transpiled_code=cleaned
            )
            
        except Exception as e:
            return VerificationResult(
                verified=False,
                logs="Transpilation failed",
                error=f"Gemini API call failed: {str(e)}"
            )
    
    def _run_dafny_verify(self, dafny_code: str) -> VerificationResult:
        """
        Write Dafny code to a temp file and run verification.
        
        Args:
            dafny_code: The complete Dafny code to verify.
            
        Returns:
            VerificationResult with verification status.
        """
        temp_file = None
        try:
            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.dfy',
                delete=False
            )
            temp_file.write(dafny_code)
            temp_file.close()
            
            # Run Dafny verify
            cmd = ["dafny", "verify", temp_file.name]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 second timeout
            )
            
            # Combine stdout and stderr
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            
            # Parse the result
            verified = self._parse_dafny_output(output, result.returncode)
            
            if verified:
                logs = "Verification successful! Code satisfies all contract requirements."
            else:
                logs = "Verification failed. See Dafny output for details."
            
            return VerificationResult(
                verified=verified,
                logs=logs,
                dafny_output=output
            )
            
        except subprocess.TimeoutExpired:
            return VerificationResult(
                verified=False,
                logs="Verification timed out",
                error="Dafny verification timed out after 60 seconds."
            )
        except FileNotFoundError:
            return VerificationResult(
                verified=False,
                logs="Dafny not found",
                error="Dafny CLI not found. Ensure 'dafny' is installed and in PATH."
            )
        except Exception as e:
            return VerificationResult(
                verified=False,
                logs="Verification error",
                error=f"Error running Dafny: {str(e)}"
            )
        finally:
            # Cleanup temp file
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except Exception:
                    pass  # Best effort cleanup
    
    def _parse_dafny_output(self, output: str, return_code: int) -> bool:
        """
        Parse Dafny output to determine if verification passed.
        
        Args:
            output: The stdout/stderr from Dafny.
            return_code: The process return code.
            
        Returns:
            True if verification passed, False otherwise.
        """
        # Check return code first
        if return_code != 0:
            return False
        
        # Look for success indicators
        output_lower = output.lower()
        
        # Dafny 4.x outputs "0 errors" on success
        if "0 errors" in output_lower:
            return True
        
        # Also check for verification confirmed
        if "verification succeeded" in output_lower:
            return True
        
        # Check for no errors reported
        if "error" not in output_lower and return_code == 0:
            return True
        
        return False


def verify_code(contract_str: str, python_str: str, api_key: Optional[str] = None) -> VerificationResult:
    """
    Convenience function to verify Python code against a Dafny contract.
    
    Args:
        contract_str: The Dafny contract/trait code.
        python_str: The Python implementation.
        api_key: Optional API key (uses environment if not provided).
        
    Returns:
        VerificationResult with verification status.
    """
    verifier = CodeVerifier(api_key=api_key)
    return verifier.verify(contract_str, python_str)


if __name__ == "__main__":
    # Simple test harness
    sample_contract = """
trait Calculator {
    method Add(a: int, b: int) returns (result: int)
        ensures result == a + b
}
"""
    
    sample_python = """
def add(a: int, b: int) -> int:
    return a + b
"""
    
    print("Testing Code Verifier...")
    verifier = CodeVerifier()
    
    if not verifier.is_configured():
        print(f"Configuration Error: {verifier.get_configuration_error()}")
    else:
        print("Verifier configured successfully!")
        result = verifier.verify(sample_contract, sample_python)
        
        print(f"\nVerification Result: {'PASSED' if result.verified else 'FAILED'}")
        print(f"Logs: {result.logs}")
        
        if result.error:
            print(f"Error: {result.error}")
        
        if result.transpiled_code:
            print(f"\nTranspiled Dafny Code:\n{result.transpiled_code}")
        
        if result.dafny_output:
            print(f"\nDafny Output:\n{result.dafny_output}")
