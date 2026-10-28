"""
Component Refinement Service

Enforces the architectural principle that blueprints must have at least 4
verifiable components to maintain proper separation of concerns.

Component Categories:
- StateContainer: Data structures and invariants
- TransitionLogic: State machines and workflows
- AccessControl: Authentication and authorization
- DataValidator: Input validation and business rules

This prevents monolithic specifications and encourages good architecture.
"""

import logging
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import Gemini, but make it optional
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
except ImportError:
    GEMINI_AVAILABLE = False
    GEMINI_API_KEY = ""


class ComponentCategory(str, Enum):
    """Component categories for architectural classification"""
    STATE_CONTAINER = "StateContainer"
    TRANSITION_LOGIC = "TransitionLogic"
    ACCESS_CONTROL = "AccessControl"
    DATA_VALIDATOR = "DataValidator"
    GENERAL = "General"


@dataclass
class ComponentSuggestion:
    """Suggested component split"""
    suggested_name: str
    category: ComponentCategory
    description: str
    estimated_size: int  # Lines of spec
    key_requirements: List[str]


@dataclass
class ComplexityReport:
    """Report on blueprint complexity and quality"""
    total_lines: int
    component_count: int
    meets_minimum: bool  # >= 4 components
    complexity_score: float  # 0-100, higher = more complex
    size_distribution: Dict[str, int]  # component_name -> line_count
    recommendations: List[str]
    component_suggestions: List[ComponentSuggestion]


class RefinementService:
    """Service for analyzing and refining blueprint complexity"""

    MINIMUM_COMPONENTS = 4
    MAX_COMPONENT_SIZE = 200  # lines of spec
    IDEAL_COMPONENT_SIZE = 100

    def __init__(self):
        """Initialize refinement service"""
        self.model_name = "gemini-1.5-flash"

    def analyze_complexity(
        self,
        spec_content: str,
        component_count: int,
        component_sizes: Optional[Dict[str, int]] = None
    ) -> ComplexityReport:
        """
        Analyze blueprint complexity

        Args:
            spec_content: Main specification content
            component_count: Number of components
            component_sizes: Optional dict of component_name -> line_count

        Returns:
            ComplexityReport with analysis and recommendations
        """
        total_lines = len(spec_content.split('\n'))

        # Calculate complexity score (0-100)
        # Factors: total size, component count, size distribution
        complexity_score = self._calculate_complexity_score(
            total_lines,
            component_count,
            component_sizes
        )

        # Check if meets minimum
        meets_minimum = component_count >= self.MINIMUM_COMPONENTS

        # Generate recommendations
        recommendations = self._generate_recommendations(
            total_lines,
            component_count,
            component_sizes,
            spec_content
        )

        # Generate component suggestions if needed
        component_suggestions = []
        if not meets_minimum:
            component_suggestions = self._suggest_component_splits(
                spec_content,
                component_count
            )

        return ComplexityReport(
            total_lines=total_lines,
            component_count=component_count,
            meets_minimum=meets_minimum,
            complexity_score=complexity_score,
            size_distribution=component_sizes or {},
            recommendations=recommendations,
            component_suggestions=component_suggestions
        )

    def enforce_metric(
        self,
        spec_content: str,
        component_count: int
    ) -> Tuple[bool, Optional[str], List[ComponentSuggestion]]:
        """
        Enforce minimum component count metric

        Args:
            spec_content: Specification content
            component_count: Current component count

        Returns:
            Tuple of (passes_metric, error_message, suggestions)
        """
        if component_count >= self.MINIMUM_COMPONENTS:
            return True, None, []

        error_message = (
            f"Blueprint has {component_count} component(s). "
            f"Minimum required: {self.MINIMUM_COMPONENTS}. "
            f"Please refine the specification to include more verifiable components."
        )

        suggestions = self._suggest_component_splits(spec_content, component_count)

        return False, error_message, suggestions

    def categorize_component(
        self,
        component_name: str,
        spec_content: str
    ) -> ComponentCategory:
        """
        Categorize a component based on its spec

        Args:
            component_name: Name of the component
            spec_content: Component specification content

        Returns:
            ComponentCategory
        """
        # Use heuristics and optionally AI to categorize
        spec_lower = spec_content.lower()
        name_lower = component_name.lower()

        # StateContainer indicators
        if any(keyword in spec_lower or keyword in name_lower for keyword in [
            'data', 'state', 'model', 'entity', 'structure', 'storage',
            'invariant', 'schema', 'database'
        ]):
            return ComponentCategory.STATE_CONTAINER

        # AccessControl indicators
        if any(keyword in spec_lower or keyword in name_lower for keyword in [
            'auth', 'permission', 'access', 'security', 'login', 'session',
            'credential', 'role', 'user'
        ]):
            return ComponentCategory.ACCESS_CONTROL

        # DataValidator indicators
        if any(keyword in spec_lower or keyword in name_lower for keyword in [
            'validat', 'sanitiz', 'check', 'verify', 'input', 'constraint',
            'rule', 'format'
        ]):
            return ComponentCategory.DATA_VALIDATOR

        # TransitionLogic indicators
        if any(keyword in spec_lower or keyword in name_lower for keyword in [
            'workflow', 'process', 'transition', 'logic', 'business',
            'operation', 'action', 'handler', 'flow'
        ]):
            return ComponentCategory.TRANSITION_LOGIC

        return ComponentCategory.GENERAL

    def auto_refine_spec(
        self,
        spec_content: str,
        target_components: int = MINIMUM_COMPONENTS
    ) -> Tuple[bool, List[Dict], Optional[str]]:
        """
        Automatically suggest refined spec with more components

        Args:
            spec_content: Original specification
            target_components: Target number of components

        Returns:
            Tuple of (success, refined_components, error_message)
        """
        if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
            return False, [], "Gemini AI not available for auto-refinement"

        try:
            model = genai.GenerativeModel(self.model_name)

            prompt = f"""Analyze this specification and decompose it into {target_components} separate verifiable components.

SPECIFICATION:
---
{spec_content}
---

REQUIREMENTS:
1. Create exactly {target_components} components
2. Each component should be independently verifiable
3. Categorize each as: StateContainer, TransitionLogic, AccessControl, or DataValidator
4. Ensure proper separation of concerns
5. Each component should be 50-150 lines of spec

COMPONENT CATEGORIES:
- StateContainer: Data structures, invariants, schemas
- TransitionLogic: Workflows, business logic, state transitions
- AccessControl: Authentication, authorization, permissions
- DataValidator: Input validation, constraints, business rules

Return a JSON array with this format:
[
  {{
    "name": "ComponentName",
    "category": "StateContainer|TransitionLogic|AccessControl|DataValidator",
    "description": "Brief description",
    "requirements": [
      "Requirement 1",
      "Requirement 2"
    ]
  }}
]

Return ONLY the JSON array, no explanations.
"""

            response = model.generate_content(prompt)
            result_text = response.text.strip()

            # Clean markdown code fences
            result_text = result_text.replace("```json", "").replace("```", "").strip()

            # Parse JSON
            import json
            components = json.loads(result_text)

            logger.info(f"Auto-refined spec into {len(components)} components")

            return True, components, None

        except Exception as e:
            error = f"Failed to auto-refine spec: {str(e)}"
            logger.error(error)
            return False, [], error

    def _calculate_complexity_score(
        self,
        total_lines: int,
        component_count: int,
        component_sizes: Optional[Dict[str, int]]
    ) -> float:
        """
        Calculate complexity score (0-100)

        Factors:
        - Total size (larger = more complex)
        - Component count (more = better distribution)
        - Size distribution (balanced = better)
        """
        # Base score from size
        size_score = min(100, (total_lines / 1000) * 100)

        # Component count score (penalty for too few)
        if component_count < 4:
            count_penalty = (4 - component_count) * 15
        else:
            count_penalty = 0

        # Distribution score (penalty for unbalanced sizes)
        distribution_penalty: float = 0
        if component_sizes and len(component_sizes) > 1:
            sizes = list(component_sizes.values())
            avg_size = sum(sizes) / len(sizes)
            variance = sum((s - avg_size) ** 2 for s in sizes) / len(sizes)
            distribution_penalty = min(20, variance / 100)

        # Final score
        complexity = size_score + count_penalty + distribution_penalty
        return min(100, max(0, complexity))

    def _generate_recommendations(
        self,
        total_lines: int,
        component_count: int,
        component_sizes: Optional[Dict[str, int]],
        spec_content: str
    ) -> List[str]:
        """Generate recommendations for improving the blueprint"""
        recommendations = []

        # Component count recommendations
        if component_count < self.MINIMUM_COMPONENTS:
            recommendations.append(
                f"⚠️ Blueprint has {component_count} component(s). "
                f"Recommended minimum: {self.MINIMUM_COMPONENTS}. "
                f"Consider splitting into more focused components."
            )
        elif component_count >= 10:
            recommendations.append(
                f"ℹ️ Blueprint has {component_count} components. "
                f"Consider if some can be merged for simplicity."
            )

        # Size recommendations
        if component_sizes:
            for comp_name, size in component_sizes.items():
                if size > self.MAX_COMPONENT_SIZE:
                    recommendations.append(
                        f"⚠️ Component '{comp_name}' is {size} lines. "
                        f"Consider splitting (max recommended: {self.MAX_COMPONENT_SIZE})."
                    )

        # Overall size
        if total_lines > 1000:
            recommendations.append(
                f"ℹ️ Total spec is {total_lines} lines. "
                f"Consider breaking into multiple blueprints."
            )

        # If no issues
        if not recommendations:
            recommendations.append(
                "✓ Blueprint structure looks good. "
                f"{component_count} well-sized components."
            )

        return recommendations

    def _suggest_component_splits(
        self,
        spec_content: str,
        current_count: int
    ) -> List[ComponentSuggestion]:
        """
        Suggest how to split the spec into more components

        Uses AI if available, otherwise provides generic suggestions
        """
        needed_components = self.MINIMUM_COMPONENTS - current_count

        if not GEMINI_AVAILABLE or not GEMINI_API_KEY:
            # Provide generic suggestions
            return self._generic_component_suggestions(needed_components)

        try:
            model = genai.GenerativeModel(self.model_name)

            prompt = f"""Analyze this specification and suggest {needed_components} additional component(s) to split it into.

SPECIFICATION:
---
{spec_content}
---

Current components: {current_count}
Need to add: {needed_components}

For each suggested component, provide:
1. Suggested name
2. Category (StateContainer, TransitionLogic, AccessControl, or DataValidator)
3. Description
4. Key requirements it should handle

Return as JSON:
[
  {{
    "name": "ComponentName",
    "category": "StateContainer",
    "description": "What this component handles",
    "key_requirements": ["req1", "req2"]
  }}
]

Return ONLY the JSON array.
"""

            response = model.generate_content(prompt)
            result_text = response.text.strip()

            # Clean markdown
            result_text = result_text.replace("```json", "").replace("```", "").strip()

            # Parse JSON
            import json
            suggestions_data = json.loads(result_text)

            suggestions = []
            for item in suggestions_data:
                suggestions.append(ComponentSuggestion(
                    suggested_name=item.get('name', 'Component'),
                    category=ComponentCategory(item.get('category', 'General')),
                    description=item.get('description', ''),
                    estimated_size=100,  # Default estimate
                    key_requirements=item.get('key_requirements', [])
                ))

            return suggestions

        except Exception as e:
            logger.error(f"Failed to generate AI suggestions: {e}")
            return self._generic_component_suggestions(needed_components)

    def _generic_component_suggestions(
        self,
        count: int
    ) -> List[ComponentSuggestion]:
        """Generic component suggestions when AI is unavailable"""
        generic_suggestions = [
            ComponentSuggestion(
                suggested_name="AuthenticationComponent",
                category=ComponentCategory.ACCESS_CONTROL,
                description="Handle user authentication and session management",
                estimated_size=80,
                key_requirements=[
                    "User login/logout",
                    "Session validation",
                    "Password policies"
                ]
            ),
            ComponentSuggestion(
                suggested_name="DataValidationComponent",
                category=ComponentCategory.DATA_VALIDATOR,
                description="Validate and sanitize all inputs",
                estimated_size=70,
                key_requirements=[
                    "Input validation rules",
                    "Data type checking",
                    "Constraint enforcement"
                ]
            ),
            ComponentSuggestion(
                suggested_name="StateManagementComponent",
                category=ComponentCategory.STATE_CONTAINER,
                description="Manage application state and data structures",
                estimated_size=100,
                key_requirements=[
                    "Data models",
                    "State invariants",
                    "Storage interfaces"
                ]
            ),
            ComponentSuggestion(
                suggested_name="BusinessLogicComponent",
                category=ComponentCategory.TRANSITION_LOGIC,
                description="Core business logic and workflows",
                estimated_size=120,
                key_requirements=[
                    "Business rules",
                    "Workflow processing",
                    "State transitions"
                ]
            )
        ]

        return generic_suggestions[:count]
