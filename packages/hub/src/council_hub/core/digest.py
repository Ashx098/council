"""Digest generation service."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from council_hub.config import settings, MILESTONE_SUBTYPES
from council_hub.db.repo import Database, SessionRepo, EventRepo, ArtifactRepo, Event
from council_hub.storage.artifacts import ArtifactStore
from council_hub.utils.text import (
    truncate_lines, extract_error_windows, truncate_to_budget,
    parse_diff_summary, format_hunk_for_digest
)


@dataclass
class MilestoneInfo:
    """Milestone event info."""
    event_id: int
    subtype: str
    ts: str


@dataclass
class DigestResult:
    """Digest generation result."""
    digest_text: str
    milestones: List[Dict[str, Any]]
    next_cursor: int
    has_more: bool


class DigestService:
    """Service for generating bounded digests."""
    
    def __init__(self, db: Optional[Database] = None,
                 store: Optional[ArtifactStore] = None):
        self.db = db or Database()
        self.sessions = SessionRepo(self.db)
        self.events = EventRepo(self.db)
        self.artifacts = ArtifactRepo(self.db)
        self.store = store or ArtifactStore()
    
    def generate_digest(self, session_id: str, 
                       after: int = 0) -> DigestResult:
        """Generate bounded digest for session.
        
        Args:
            session_id: Session identifier
            after: Cursor - only include events after this event_id
            
        Returns:
            DigestResult with bounded text and metadata
        """
        # Get events after cursor
        events = self.events.list_after(
            session_id, after, limit=settings.digest_max_events
        )
        
        if not events:
            return DigestResult(
                digest_text="(No new events)",
                milestones=[],
                next_cursor=after,
                has_more=False
            )
        
        # Extract milestones
        milestones = self._extract_milestones(events)
        
        # Build digest parts
        parts = []
        parts.append(f"## Session: {session_id}\n")
        
        # Group events by type for summary
        event_counts = {}
        for e in events:
            event_counts[e.type] = event_counts.get(e.type, 0) + 1
        
        summary_parts = [f"{count} {etype}" 
                        for etype, count in event_counts.items()]
        parts.append(f"Events: {', '.join(summary_parts)}\n")
        parts.append("")
        
        # Process each event
        for event in events:
            event_text = self._format_event(event)
            if event_text:
                parts.append(event_text)
                parts.append("")
        
        # Apply budget
        digest_text = truncate_to_budget(parts, settings.digest_max_chars)
        
        # Determine cursor state
        last_event_id = events[-1].event_id
        has_more = len(events) >= settings.digest_max_events
        
        return DigestResult(
            digest_text=digest_text,
            milestones=[m.__dict__ for m in milestones],
            next_cursor=last_event_id,
            has_more=has_more
        )
    
    def generate_context_pack(self, session_id: str) -> Dict[str, Any]:
        """Generate context pack for executor briefing.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Context pack dict
        """
        # Get session
        session = self.sessions.get(session_id)
        
        # Get pinned decisions (last 5 decision events)
        decisions = []
        all_events = self.events.list_after(session_id, after=0, limit=1000)
        for e in reversed(all_events):
            if e.type == "decision":
                decisions.append(e)
                if len(decisions) >= 5:
                    break
        
        # Get current task (latest task_brief)
        current_task = None
        for e in reversed(all_events):
            if e.type == "task_brief":
                current_task = e
                break
        
        # Get last patch
        last_patch = None
        for e in reversed(all_events):
            if e.type == "patch":
                last_patch = e
                break
        
        # Get last test status
        last_test = None
        for e in reversed(all_events):
            if e.type == "test_result":
                last_test = e
                break
        
        # Generate mini digest (last 10 events)
        recent_events = all_events[-10:] if len(all_events) > 10 else all_events
        recent_parts = [self._format_event(e) for e in recent_events 
                       if self._format_event(e)]
        recent_digest = truncate_to_budget(recent_parts, 2000)
        
        return {
            "session_id": session_id,
            "repo_root": session.repo_root if session else None,
            "title": session.title if session else None,
            "pinned_decisions": [d.to_dict() for d in reversed(decisions)],
            "current_task": current_task.to_dict() if current_task else None,
            "last_patch": last_patch.to_dict() if last_patch else None,
            "last_test_status": last_test.to_dict() if last_test else None,
            "recent_digest": recent_digest,
        }
    
    def _extract_milestones(self, events: List[Event]) -> List[MilestoneInfo]:
        """Extract milestone events from list."""
        milestones = []
        
        for event in events:
            if event.type == "milestone":
                subtype = event.meta.get("subtype", "unknown")
                if subtype in MILESTONE_SUBTYPES:
                    milestones.append(MilestoneInfo(
                        event_id=event.event_id,
                        subtype=subtype,
                        ts=event.ts
                    ))
            
            # Also extract run_report as implicit milestone
            elif event.type == "run_report":
                status = event.meta.get("status", "completed")
                subtype = "executor_finished" if status == "success" else "executor_failed"
                milestones.append(MilestoneInfo(
                    event_id=event.event_id,
                    subtype=subtype,
                    ts=event.ts
                ))
        
        return milestones
    
    def _format_event(self, event: Event) -> Optional[str]:
        """Format a single event for digest.
        
        Args:
            event: Event to format
            
        Returns:
            Formatted text or None if skipped
        """
        if event.type == "patch":
            return self._format_patch_event(event)
        elif event.type == "test_result":
            return self._format_test_event(event)
        elif event.type == "tool_run":
            return self._format_tool_event(event)
        elif event.type == "run_report":
            return self._format_run_report(event)
        elif event.type == "message":
            return f"[{event.source}] {event.body[:200]}"
        elif event.type == "task_brief":
            return f"**Task:** {event.body[:300]}"
        elif event.type == "question":
            return f"**Q:** {event.body[:300]}"
        elif event.type == "decision":
            return f"**Decision:** {event.body[:300]}"
        else:
            return f"[{event.type}] {event.body[:200]}"
    
    def _format_patch_event(self, event: Event) -> str:
        """Format patch event with bounded diff view."""
        meta = event.meta or {}
        files = meta.get("files_changed", [])
        added = meta.get("lines_added", 0)
        removed = meta.get("lines_removed", 0)
        artifact_id = meta.get("artifact_id")
        
        lines = [f"**Patch:** {event.body}"]
        lines.append(f"Files: {', '.join(files[:settings.patch_max_files_in_digest])}")
        if len(files) > settings.patch_max_files_in_digest:
            lines.append(f"... and {len(files) - settings.patch_max_files_in_digest} more files")
        lines.append(f"Lines: +{added}/-{removed}")
        
        # Try to include truncated hunks if artifact available
        if artifact_id:
            try:
                content = self.store.retrieve(event.session_id, artifact_id)
                if content:
                    diff_text = content.decode("utf-8", errors="replace")
                    summary = parse_diff_summary(diff_text)
                    
                    # Add top hunks per file
                    files_with_hunks = {}
                    for hunk in summary.hunks:
                        if hunk.file_path not in files_with_hunks:
                            files_with_hunks[hunk.file_path] = []
                        if len(files_with_hunks[hunk.file_path]) < settings.patch_max_hunks_per_file:
                            files_with_hunks[hunk.file_path].append(hunk)
                    
                    for file_path, hunks in files_with_hunks.items():
                        lines.append(f"\n--- {file_path} ---")
                        for hunk in hunks:
                            lines.append(format_hunk_for_digest(hunk))
            except Exception:
                pass  # Skip artifact content on error
        
        return "\n".join(lines)
    
    def _format_test_event(self, event: Event) -> str:
        """Format test result with error windows."""
        meta = event.meta or {}
        command = meta.get("command", "unknown")
        exit_code = meta.get("exit_code", -1)
        passed = meta.get("passed", 0)
        failed = meta.get("failed", 0)
        skipped = meta.get("skipped", 0)
        artifact_id = meta.get("artifact_id")
        
        status = "PASS" if exit_code == 0 else "FAIL"
        lines = [
            f"**Tests:** {status}",
            f"Command: {command}",
            f"Passed: {passed}, Failed: {failed}, Skipped: {skipped}",
        ]
        
        # Extract error windows if failing
        if failed > 0 and artifact_id:
            try:
                content = self.store.retrieve(event.session_id, artifact_id)
                if content:
                    log_text = content.decode("utf-8", errors="replace")
                    # Truncate log first
                    truncated = truncate_lines(
                        log_text, 
                        settings.log_max_lines,
                        settings.log_tail_lines
                    )
                    # Extract error windows
                    windows = extract_error_windows(truncated)
                    if windows:
                        lines.append("\n**Errors:**")
                        for i, window in enumerate(windows[:3]):  # Max 3 windows
                            lines.append(f"\n--- Error {i+1} ---")
                            lines.append(window)
            except Exception:
                pass
        
        return "\n".join(lines)
    
    def _format_tool_event(self, event: Event) -> str:
        """Format tool run event."""
        meta = event.meta or {}
        command = meta.get("command", "unknown")
        exit_code = meta.get("exit_code", -1)
        status = "OK" if exit_code == 0 else "FAILED"
        
        return f"**Tool:** {command} ({status})\n{event.body[:200]}"
    
    def _format_run_report(self, event: Event) -> str:
        """Format run report event."""
        meta = event.meta or {}
        status = meta.get("status", "unknown")
        questions = meta.get("questions", [])
        
        lines = [
            f"**Run Report:** {status}",
            event.body[:500],
        ]
        
        if questions:
            lines.append("\n**Questions:**")
            for q in questions[:5]:
                lines.append(f"- {q[:200]}")
        
        return "\n".join(lines)
