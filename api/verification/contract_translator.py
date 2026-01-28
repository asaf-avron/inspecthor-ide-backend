"""
Contract translator: Dafny → icontract translation helper.
Converts Dafny pre/postconditions to Python icontract decorators.
"""

import re
from typing import List, Tuple, Optional


def dafny_to_icontract_require(dafny_precondition: str) -> str:
    """
    Translate Dafny precondition to icontract.require decorator.
    
    Args:
        dafny_precondition: Dafny precondition string (e.g., "ValidState(state)")
    
    Returns:
        Python lambda expression string for icontract.require
    
    Example:
        Input: "ValidState(state)"
        Output: "lambda state: state.validate()"
    """
    # Simple translation patterns
    # TODO: Implement full Dafny expression parser
    
    # Pattern: ValidState(state) -> state.validate()
    if "ValidState" in dafny_precondition:
        state_var = re.search(r"ValidState\((\w+)\)", dafny_precondition)
        if state_var:
            return f"lambda {state_var.group(1)}: {state_var.group(1)}.validate()"
    
    # Pattern: x != None -> x is not None
    dafny_precondition = re.sub(r"(\w+)\s*!=\s*None", r"\1 is not None", dafny_precondition)
    dafny_precondition = re.sub(r"(\w+)\s*==\s*None", r"\1 is None", dafny_precondition)
    
    # Pattern: |x| > 0 -> len(x) > 0
    dafny_precondition = re.sub(r"\|(\w+)\|\s*>\s*0", r"len(\1) > 0", dafny_precondition)
    
    # Return as lambda (assume single expression)
    # Extract variables from expression
    vars_match = re.findall(r'\b([a-z_][a-z0-9_]*)\b', dafny_precondition.lower())
    vars_set = set(vars_match) - {'and', 'or', 'not', 'in', 'is', 'len'}
    
    if vars_set:
        vars_str = ", ".join(sorted(vars_set))
        return f"lambda {vars_str}: {dafny_precondition}"
    
    return f"lambda: {dafny_precondition}"


def dafny_to_icontract_ensure(dafny_postcondition: str) -> str:
    """
    Translate Dafny postcondition to icontract.ensure decorator.
    
    Args:
        dafny_postcondition: Dafny postcondition string
    
    Returns:
        Python lambda expression string for icontract.ensure
    
    Example:
        Input: "ValidState(result)"
        Output: "lambda result, OLD: result.validate()"
    """
    # Simple translation patterns
    # TODO: Implement full Dafny expression parser
    
    # Pattern: ValidState(result) -> result.validate()
    if "ValidState" in dafny_postcondition:
        state_var = re.search(r"ValidState\((\w+)\)", dafny_postcondition)
        if state_var:
            return f"lambda {state_var.group(1)}, OLD: {state_var.group(1)}.validate()"
    
    # Pattern: result.Success? -> result.success (for Result types)
    dafny_postcondition = re.sub(r"(\w+)\.Success\?", r"\1.success", dafny_postcondition)
    
    # Pattern: x != None -> x is not None
    dafny_postcondition = re.sub(r"(\w+)\s*!=\s*None", r"\1 is not None", dafny_postcondition)
    
    # Extract variables
    vars_match = re.findall(r'\b([a-z_][a-z0-9_]*)\b', dafny_postcondition.lower())
    vars_set = set(vars_match) - {'and', 'or', 'not', 'in', 'is', 'len', 'old', 'implies'}
    
    # Add OLD for postconditions
    vars_list = sorted(vars_set)
    if 'result' in vars_list:
        vars_list.remove('result')
        vars_list.insert(0, 'result')
    vars_list.append('OLD')
    
    vars_str = ", ".join(vars_list)
    return f"lambda {vars_str}: {dafny_postcondition}"


def extract_contracts_from_dafny(dafny_code: str, function_name: str) -> Tuple[List[str], List[str]]:
    """
    Extract preconditions and postconditions from Dafny function.
    
    Args:
        dafny_code: Dafny source code
        function_name: Name of function to extract contracts from
    
    Returns:
        Tuple of (preconditions, postconditions) lists
    """
    preconditions = []
    postconditions = []
    
    lines = dafny_code.split('\n')
    in_function = False
    in_requires = False
    in_ensures = False
    
    for line in lines:
        if f"function {function_name}" in line:
            in_function = True
            continue
        
        if not in_function:
            continue
        
        if '{' in line:
            break
        
        if "requires" in line:
            in_requires = True
            in_ensures = False
            # Extract condition after "requires"
            cond = line.split("requires", 1)[1].strip()
            if cond:
                preconditions.append(cond)
            continue
        
        if "ensures" in line:
            in_ensures = True
            in_requires = False
            # Extract condition after "ensures"
            cond = line.split("ensures", 1)[1].strip()
            if cond:
                postconditions.append(cond)
            continue
        
        if in_requires:
            preconditions.append(line.strip())
        elif in_ensures:
            postconditions.append(line.strip())
    
    return preconditions, postconditions


def generate_icontract_decorators(dafny_code: str, function_name: str) -> str:
    """
    Generate icontract decorators from Dafny function.
    
    Args:
        dafny_code: Dafny source code
        function_name: Name of function
    
    Returns:
        Python decorator code string
    """
    preconditions, postconditions = extract_contracts_from_dafny(dafny_code, function_name)
    
    decorators = []
    
    for precond in preconditions:
        if precond.strip():
            lambda_expr = dafny_to_icontract_require(precond.strip())
            decorators.append(f"@icontract.require({lambda_expr})")
    
    for postcond in postconditions:
        if postcond.strip():
            lambda_expr = dafny_to_icontract_ensure(postcond.strip())
            decorators.append(f"@icontract.ensure({lambda_expr})")
    
    return "\n".join(decorators)
