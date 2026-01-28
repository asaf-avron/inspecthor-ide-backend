"""
Gemini-powered transpiler for InSpecThor.
Converts Python/TypeScript code to Dafny implementations.
"""

import os
from typing import Optional, Dict, Any
import google.generativeai as genai
from pydantic import BaseModel

from ..crawler.python_crawler import ExecutionSlice


class TranspilationResult(BaseModel):
    """Result of transpilation."""
    dafny_code: str
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}


# Transpiler prompt template
TRANSPILER_PROMPT_TEMPLATE = """You are a formal verification expert specializing in Dafny.
Convert the following {language} code into a Dafny method implementation that satisfies the provided contract.

CRITICAL RULES:
1. Preserve the exact logic - do NOT optimize or simplify
2. Map types precisely:
   Python:
   - str → string
   - int → int
   - bool → bool
   - list[T] → seq<T>
   - dict[K,V] → map<K,V>
   - Optional[T] → T?
   - None → null
   
   TypeScript:
   - string → string
   - number → int (or real if needed)
   - boolean → bool
   - Array<T> → seq<T>
   - Map<K,V> → map<K,V>
   - T | undefined → T?

3. External API calls and I/O operations become axiomatized functions
4. Database queries become map lookups
5. The output MUST compile with the provided contract
6. Include ALL necessary preconditions and postconditions from the contract
7. Use Dafny's verification-friendly idioms:
   - Use 'decreases' clauses for loops
   - Add loop invariants for correctness
   - Use 'assert' statements to help the verifier

CONTRACT (must satisfy):
```dafny
{contract}
```

SOURCE CODE:
```{language}
{execution_slice}
```

{dependencies_section}

{stubs_section}

OUTPUT REQUIREMENTS:
- Return ONLY the Dafny method implementation
- Include the method signature with all requires/ensures clauses from the contract
- Include the method body with loop invariants and decreases clauses
- Do NOT include explanations or markdown formatting
- Do NOT include any text outside the Dafny code block

Begin your response with 'method' and nothing else.
"""


class GeminiTranspiler:
    """
    Transpiles source code to Dafny using Google Gemini.
    """
    
    def __init__(self):
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        genai.configure(api_key=api_key)
        
        # Use Gemini 1.5 Pro for code generation
        self.model = genai.GenerativeModel(
            'gemini-1.5-pro',
            generation_config={  # type: ignore[arg-type]
                'temperature': 0.1,  # Low temperature for deterministic output
                'top_p': 0.95,
                'top_k': 40,
                'max_output_tokens': 8192,
            }
        )
    
    async def transpile_python(
        self,
        execution_slice: ExecutionSlice,
        contract: str
    ) -> TranspilationResult:
        """
        Transpile Python execution slice to Dafny.
        
        Args:
            execution_slice: Extracted execution slice with anchor and dependencies
            contract: Dafny contract (method signature with requires/ensures)
        
        Returns:
            TranspilationResult with generated Dafny code
        """
        # Build dependencies section
        dependencies_section = ""
        if execution_slice.dependencies:
            dependencies_section = "DEPENDENCIES:\n```python\n"
            dependencies_section += "\n\n".join(execution_slice.dependencies)
            dependencies_section += "\n```\n"
        
        # Build stubs section
        stubs_section = ""
        if execution_slice.external_stubs:
            stubs_section = "EXTERNAL FUNCTIONS (axiomatized):\n```dafny\n"
            stubs_section += "\n".join(execution_slice.external_stubs)
            stubs_section += "\n```\n"
        
        # Build full prompt
        prompt = TRANSPILER_PROMPT_TEMPLATE.format(
            language="python",
            contract=contract,
            execution_slice=execution_slice.anchor_code,
            dependencies_section=dependencies_section,
            stubs_section=stubs_section
        )
        
        try:
            # Generate Dafny code
            response = self.model.generate_content(prompt)
            dafny_code = response.text.strip()
            
            # Clean up response
            dafny_code = self._clean_dafny_output(dafny_code)
            
            return TranspilationResult(
                dafny_code=dafny_code,
                success=True,
                metadata={
                    "language": "python",
                    "model": "gemini-1.5-pro",
                    "prompt_tokens": len(prompt.split()),
                }
            )
            
        except Exception as e:
            return TranspilationResult(
                dafny_code="",
                success=False,
                error=str(e)
            )
    
    async def transpile_typescript(
        self,
        source_code: str,
        dependencies: str,
        contract: str
    ) -> TranspilationResult:
        """
        Transpile TypeScript code to Dafny.
        
        Args:
            source_code: TypeScript source code
            dependencies: Dependency code
            contract: Dafny contract
        
        Returns:
            TranspilationResult with generated Dafny code
        """
        dependencies_section = ""
        if dependencies:
            dependencies_section = f"DEPENDENCIES:\n```typescript\n{dependencies}\n```\n"
        
        prompt = TRANSPILER_PROMPT_TEMPLATE.format(
            language="typescript",
            contract=contract,
            execution_slice=source_code,
            dependencies_section=dependencies_section,
            stubs_section=""
        )
        
        try:
            response = self.model.generate_content(prompt)
            dafny_code = response.text.strip()
            dafny_code = self._clean_dafny_output(dafny_code)
            
            return TranspilationResult(
                dafny_code=dafny_code,
                success=True,
                metadata={
                    "language": "typescript",
                    "model": "gemini-1.5-pro"
                }
            )
            
        except Exception as e:
            return TranspilationResult(
                dafny_code="",
                success=False,
                error=str(e)
            )
    
    def _clean_dafny_output(self, output: str) -> str:
        """
        Clean up Gemini's output to extract pure Dafny code.
        
        Args:
            output: Raw output from Gemini
        
        Returns:
            Cleaned Dafny code
        """
        # Remove markdown code blocks if present
        if output.startswith("```dafny"):
            output = output[len("```dafny"):].strip()
        elif output.startswith("```"):
            output = output[3:].strip()
        
        if output.endswith("```"):
            output = output[:-3].strip()
        
        # Remove any explanatory text before 'method'
        if "method " in output:
            method_index = output.find("method ")
            output = output[method_index:]
        
        return output.strip()
    
    async def validate_transpilation(
        self,
        dafny_code: str,
        original_code: str,
        language: str
    ) -> Dict[str, Any]:
        """
        Use Gemini to validate that transpiled code preserves semantics.
        
        Args:
            dafny_code: Generated Dafny code
            original_code: Original source code
            language: Source language ("python" or "typescript")
        
        Returns:
            Dict with validation result
        """
        validation_prompt = f"""Compare the following {language} code with its Dafny translation.
Verify that the Dafny code preserves the exact logic and semantics.

ORIGINAL {language.upper()}:
```{language}
{original_code}
```

DAFNY TRANSLATION:
```dafny
{dafny_code}
```

Answer with ONLY "VALID" or "INVALID: <reason>".
"""
        
        try:
            response = self.model.generate_content(validation_prompt)
            result = response.text.strip()
            
            is_valid = result.startswith("VALID")
            reason = result[len("INVALID: "):].strip() if not is_valid else None
            
            return {
                "valid": is_valid,
                "reason": reason
            }
            
        except Exception as e:
            return {
                "valid": False,
                "reason": f"Validation error: {str(e)}"
            }
