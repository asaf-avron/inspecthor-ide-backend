"""
Drift Detection and Repair Service

Detects and repairs drift between registry.yaml and actual component locations.
Drift occurs when:
1. Components are moved/renamed (path drift)
2. Components are deleted (missing components)
3. Component content is modified directly without harmonization (corruption)

Uses UUID-based tracking to maintain identity across moves.
"""

import os
import logging
import json
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime

from api.brain.registry import RegistryManager
from api.brain.proof_ledger import ProofLedger

logger = logging.getLogger(__name__)


@dataclass
class DriftIssue:
    """Represents a detected drift issue"""
    issue_type: str  # 'moved', 'missing', 'corrupted', 'orphaned'
    component_uuid: str
    component_name: str
    expected_path: Optional[str]
    actual_path: Optional[str]
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    repairable: bool


@dataclass
class DriftReport:
    """Report of all drift issues found in a repository"""
    repo_path: str
    scan_timestamp: str
    total_issues: int
    issues_by_type: Dict[str, int]
    issues: List[DriftIssue]
    health_score: float  # 0-100, 100 = no drift


@dataclass
class RepairResult:
    """Result of a drift repair operation"""
    success: bool
    component_uuid: str
    old_path: Optional[str]
    new_path: Optional[str]
    action_taken: str
    message: str


class DriftDetector:
    """Service for detecting and repairing component drift"""

    def __init__(self, repo_path: str):
        """
        Initialize drift detector for a repository

        Args:
            repo_path: Path to the repository root
        """
        self.repo_path = repo_path
        self.registry_manager = RegistryManager(repo_path)
        self.proof_ledger = ProofLedger(repo_path)

    def scan_for_drift(self) -> DriftReport:
        """
        Scan entire repository for drift issues

        Returns:
            DriftReport with all detected issues
        """
        logger.info(f"Starting drift scan for {self.repo_path}")
        start_time = datetime.now()
        issues = []

        # Check if registry exists
        if not self.registry_manager.exists():
            logger.error(f"Registry not found at {self.repo_path}")
            return DriftReport(
                repo_path=self.repo_path,
                scan_timestamp=start_time.isoformat(),
                total_issues=1,
                issues_by_type={'critical': 1},
                issues=[DriftIssue(
                    issue_type='missing',
                    component_uuid='N/A',
                    component_name='registry.yaml',
                    expected_path=os.path.join(self.repo_path, '.inspecthor', 'registry.yaml'),
                    actual_path=None,
                    severity='critical',
                    description='Registry file not found - Brain not initialized',
                    repairable=False
                )],
                health_score=0.0
            )

        # Get all components from registry
        registry_components = self.registry_manager.get_all_components()

        # Check 1: Missing components (in registry but file doesn't exist)
        issues.extend(self._check_missing_components(registry_components))

        # Check 2: Moved components (UUID exists but at different path)
        issues.extend(self._check_moved_components(registry_components))

        # Check 3: Corrupted components (hash mismatch with ledger)
        issues.extend(self._check_corrupted_components(registry_components))

        # Check 4: Orphaned components (exist but not in registry)
        issues.extend(self._check_orphaned_components(registry_components))

        # Calculate health score
        health_score = self._calculate_health_score(issues)

        # Count issues by type
        issues_by_type: Dict[str, int] = {}
        for issue in issues:
            issues_by_type[issue.severity] = issues_by_type.get(issue.severity, 0) + 1

        logger.info(f"Drift scan complete: {len(issues)} issues found, health score: {health_score}")

        return DriftReport(
            repo_path=self.repo_path,
            scan_timestamp=start_time.isoformat(),
            total_issues=len(issues),
            issues_by_type=issues_by_type,
            issues=issues,
            health_score=health_score
        )

    def _check_missing_components(self, registry_components: Dict) -> List[DriftIssue]:
        """Check for components in registry that don't exist on disk and cannot be found elsewhere"""
        issues = []

        for component_uuid, component_entry in registry_components.items():
            component_path = component_entry.path
            component_name = component_entry.name

            if not component_path:
                continue

            full_path = os.path.join(self.repo_path, component_path)

            if not os.path.exists(full_path):
                # Try to find component by UUID before flagging as missing
                actual_path = self._scan_for_uuid(component_uuid)

                if not actual_path:
                    # Component truly missing - not found anywhere
                    logger.warning(f"Missing component: {component_uuid} at {component_path}")
                    issues.append(DriftIssue(
                        issue_type='missing',
                        component_uuid=component_uuid,
                        component_name=component_name,
                        expected_path=component_path,
                        actual_path=None,
                        severity='high',
                        description=f'Component {component_name} not found at expected path',
                        repairable=True  # Can try to find it
                    ))

        return issues

    def _check_moved_components(self, registry_components: Dict) -> List[DriftIssue]:
        """Check for components that have moved to a different location"""
        issues = []

        for component_uuid, component_entry in registry_components.items():
            component_path = component_entry.path
            component_name = component_entry.name

            if not component_path:
                continue

            full_path = os.path.join(self.repo_path, component_path)

            # If file doesn't exist at expected path, try to find it
            if not os.path.exists(full_path):
                # Try to find component by UUID
                actual_path = self._scan_for_uuid(component_uuid)

                if actual_path:
                    logger.warning(f"Moved component: {component_uuid} from {component_path} to {actual_path}")
                    issues.append(DriftIssue(
                        issue_type='moved',
                        component_uuid=component_uuid,
                        component_name=component_name,
                        expected_path=component_path,
                        actual_path=actual_path,
                        severity='medium',
                        description=f'Component {component_name} moved from {component_path} to {actual_path}',
                        repairable=True
                    ))

        return issues

    def _check_corrupted_components(self, registry_components: Dict) -> List[DriftIssue]:
        """Check for components with hash mismatches (direct edits)"""
        issues = []

        for component_uuid, component_entry in registry_components.items():
            component_path = component_entry.path
            component_name = component_entry.name

            if not component_path:
                continue

            full_path = os.path.join(self.repo_path, component_path)

            if not os.path.exists(full_path):
                continue  # Already handled by missing/moved checks

            # Check if component has a Dafny file
            dafny_path = self._find_dafny_file(full_path)
            if not dafny_path:
                continue

            # Read Dafny content
            try:
                with open(dafny_path, 'r', encoding='utf-8') as f:
                    dafny_content = f.read()

                # Check if there's a ledger entry
                latest_entry = self.proof_ledger.get_latest_entry(component_uuid)

                if latest_entry:
                    # Only check corruption if we have a baseline to compare against
                    current_hash = self.proof_ledger._compute_hash(dafny_content)

                    if current_hash != latest_entry.hash:
                        logger.warning(f"Corrupted component: {component_uuid} at {component_path}")
                        issues.append(DriftIssue(
                            issue_type='corrupted',
                            component_uuid=component_uuid,
                            component_name=component_name,
                            expected_path=component_path,
                            actual_path=component_path,
                            severity='critical',
                            description=f'Component {component_name} has been modified directly (hash mismatch)',
                            repairable=False  # Requires manual review
                        ))

            except Exception as e:
                logger.error(f"Failed to check corruption for {component_uuid}: {e}")

        return issues

    def _check_orphaned_components(self, registry_components: Dict) -> List[DriftIssue]:
        """Check for components on disk that aren't in the registry"""
        issues = []

        # Find all .inspecthor_meta files in the repo
        meta_files = self._find_meta_files()

        # Get all UUIDs in registry
        registry_uuids = set(registry_components.keys())

        # Check each meta file
        for meta_path in meta_files:
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)

                component_uuid = meta.get('component_uuid')
                component_name = meta.get('name', 'Unknown')

                if component_uuid and component_uuid not in registry_uuids:
                    # Get relative path
                    rel_path = os.path.relpath(os.path.dirname(meta_path), self.repo_path)

                    logger.warning(f"Orphaned component: {component_uuid} at {rel_path}")
                    issues.append(DriftIssue(
                        issue_type='orphaned',
                        component_uuid=component_uuid,
                        component_name=component_name,
                        expected_path=None,
                        actual_path=rel_path,
                        severity='low',
                        description=f'Component {component_name} exists but not registered',
                        repairable=True  # Can add to registry
                    ))

            except Exception as e:
                logger.error(f"Failed to read meta file {meta_path}: {e}")

        return issues

    def _scan_for_uuid(self, component_uuid: str) -> Optional[str]:
        """
        Scan repository for a component with the given UUID

        Args:
            component_uuid: UUID to search for

        Returns:
            Relative path to component directory, or None if not found
        """
        meta_files = self._find_meta_files()

        for meta_path in meta_files:
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)

                if meta.get('component_uuid') == component_uuid:
                    # Return relative path to component directory
                    component_dir = os.path.dirname(meta_path)
                    return os.path.relpath(component_dir, self.repo_path)

            except Exception as e:
                logger.error(f"Failed to read meta file {meta_path}: {e}")

        return None

    def _find_meta_files(self) -> List[str]:
        """Find all .inspecthor_meta files in the repository"""
        meta_files = []

        for root, dirs, files in os.walk(self.repo_path):
            # Skip .inspecthor directory itself
            if '.inspecthor' in root:
                continue

            if '.inspecthor_meta' in files:
                meta_files.append(os.path.join(root, '.inspecthor_meta'))

        return meta_files

    def _find_dafny_file(self, component_path: str) -> Optional[str]:
        """Find the Dafny file in a component directory"""
        if os.path.isfile(component_path):
            component_path = os.path.dirname(component_path)

        full_path = os.path.join(self.repo_path, component_path)

        if not os.path.isdir(full_path):
            return None

        # Look for core.dfy
        dafny_path = os.path.join(full_path, 'core.dfy')
        if os.path.exists(dafny_path):
            return dafny_path

        # Look for any .dfy file
        for file in os.listdir(full_path):
            if file.endswith('.dfy'):
                return os.path.join(full_path, file)

        return None

    def _calculate_health_score(self, issues: List[DriftIssue]) -> float:
        """
        Calculate repository health score (0-100)

        Args:
            issues: List of detected issues

        Returns:
            Health score (100 = perfect, 0 = critical issues)
        """
        if not issues:
            return 100.0

        # Weight issues by severity
        severity_weights = {
            'low': 5,
            'medium': 15,
            'high': 30,
            'critical': 50
        }

        total_penalty = 0
        for issue in issues:
            total_penalty += severity_weights.get(issue.severity, 10)

        # Cap at 100 penalty
        total_penalty = min(total_penalty, 100)

        return max(0.0, 100.0 - total_penalty)

    def repair_moved_component(self, component_uuid: str) -> RepairResult:
        """
        Repair a moved component by updating the registry

        Args:
            component_uuid: UUID of the component to repair

        Returns:
            RepairResult with details of the repair
        """
        logger.info(f"Attempting to repair moved component: {component_uuid}")

        # Find component in registry
        component_entry = self.registry_manager.get_component(component_uuid)

        if not component_entry:
            return RepairResult(
                success=False,
                component_uuid=component_uuid,
                old_path=None,
                new_path=None,
                action_taken='none',
                message='Component not found in registry'
            )

        old_path = component_entry.path

        # Scan for new location
        new_path = self._scan_for_uuid(component_uuid)

        if not new_path:
            return RepairResult(
                success=False,
                component_uuid=component_uuid,
                old_path=old_path,
                new_path=None,
                action_taken='none',
                message='Component not found in repository'
            )

        # Update registry
        try:
            self.registry_manager.update_component_path(component_uuid, new_path)

            logger.info(f"Repaired component {component_uuid}: {old_path} -> {new_path}")

            return RepairResult(
                success=True,
                component_uuid=component_uuid,
                old_path=old_path,
                new_path=new_path,
                action_taken='updated_registry',
                message=f'Updated registry: {old_path} -> {new_path}'
            )

        except Exception as e:
            return RepairResult(
                success=False,
                component_uuid=component_uuid,
                old_path=old_path,
                new_path=new_path,
                action_taken='none',
                message=f'Failed to update registry: {str(e)}'
            )

    def repair_orphaned_component(self, component_uuid: str) -> RepairResult:
        """
        Repair an orphaned component by adding it to the registry

        Args:
            component_uuid: UUID of the orphaned component

        Returns:
            RepairResult with details of the repair
        """
        logger.info(f"Attempting to repair orphaned component: {component_uuid}")

        # Find component location
        component_path = self._scan_for_uuid(component_uuid)

        if not component_path:
            return RepairResult(
                success=False,
                component_uuid=component_uuid,
                old_path=None,
                new_path=None,
                action_taken='none',
                message='Component not found in repository'
            )

        # Read component metadata
        meta_path = os.path.join(self.repo_path, component_path, '.inspecthor_meta')
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            component_name = meta.get('name', 'Unknown')

            # Add to registry
            self.registry_manager.add_component(
                component_uuid=component_uuid,
                path=component_path,
                name=component_name
            )

            logger.info(f"Repaired orphaned component {component_uuid} at {component_path}")

            return RepairResult(
                success=True,
                component_uuid=component_uuid,
                old_path=None,
                new_path=component_path,
                action_taken='added_to_registry',
                message=f'Added component to registry at {component_path}'
            )

        except Exception as e:
            return RepairResult(
                success=False,
                component_uuid=component_uuid,
                old_path=None,
                new_path=component_path,
                action_taken='none',
                message=f'Failed to add to registry: {str(e)}'
            )

    def auto_repair_all(self) -> List[RepairResult]:
        """
        Automatically repair all repairable drift issues

        Returns:
            List of RepairResult for each repair attempt
        """
        logger.info("Starting auto-repair for all repairable issues")

        # Scan for drift
        report = self.scan_for_drift()

        results = []

        # Repair each repairable issue
        for issue in report.issues:
            if not issue.repairable:
                continue

            if issue.issue_type == 'moved':
                result = self.repair_moved_component(issue.component_uuid)
                results.append(result)

            elif issue.issue_type == 'orphaned':
                result = self.repair_orphaned_component(issue.component_uuid)
                results.append(result)

            elif issue.issue_type == 'missing':
                # Try to find and repair
                result = self.repair_moved_component(issue.component_uuid)
                results.append(result)

        logger.info(f"Auto-repair complete: {len(results)} repairs attempted")

        return results
