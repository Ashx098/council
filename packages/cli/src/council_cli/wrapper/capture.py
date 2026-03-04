"""Output capture and batching."""

import time
from dataclasses import dataclass, field
from threading import Lock, Thread
from typing import Callable, List, Optional
from queue import Queue, Empty

from council_cli.utils.text import truncate


@dataclass
class OutputBatch:
    """Batch of captured output."""
    stream: str  # "stdout" or "stderr"
    text: str
    line_count: int


class OutputCapture:
    """Capture and batch subprocess output.
    
    Reads from a stream continuously and batches output
    based on time or line count thresholds.
    """
    
    def __init__(self, 
                 stream_name: str,
                 batch_callback: Callable[[OutputBatch], None],
                 batch_interval: float = 2.0,
                 batch_lines: int = 50,
                 max_batch_size: int = 8000):
        self.stream_name = stream_name
        self.batch_callback = batch_callback
        self.batch_interval = batch_interval
        self.batch_lines = batch_lines
        self.max_batch_size = max_batch_size
        
        self._queue: Queue = Queue()
        self._buffer: List[str] = []
        self._buffer_size: int = 0
        self._last_flush: float = time.time()
        self._lock = Lock()
        self._running = False
        self._thread: Optional[Thread] = None
    
    def add_line(self, line: str):
        """Add a line to the capture buffer."""
        self._queue.put(line)
    
    def start(self):
        """Start the capture thread."""
        self._running = True
        self._thread = Thread(target=self._process_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the capture thread and flush remaining."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        self._flush()
    
    def _process_loop(self):
        """Main processing loop."""
        while self._running:
            try:
                line = self._queue.get(timeout=0.1)
                self._add_to_buffer(line)
            except Empty:
                # Check for time-based flush
                self._check_time_flush()
    
    def _add_to_buffer(self, line: str):
        """Add line to buffer and check thresholds."""
        with self._lock:
            self._buffer.append(line)
            self._buffer_size += len(line)
            
            # Check line count threshold
            if len(self._buffer) >= self.batch_lines:
                self._flush_locked()
                return
            
            # Check size threshold
            if self._buffer_size >= self.max_batch_size:
                self._flush_locked()
                return
            
            # Check time threshold
            self._check_time_flush_locked()
    
    def _check_time_flush(self):
        """Check if time-based flush needed (thread-safe)."""
        with self._lock:
            self._check_time_flush_locked()
    
    def _check_time_flush_locked(self):
        """Check if time-based flush needed (lock held)."""
        if self._buffer and time.time() - self._last_flush >= self.batch_interval:
            self._flush_locked()
    
    def _flush(self):
        """Flush buffer (thread-safe)."""
        with self._lock:
            self._flush_locked()
    
    def _flush_locked(self):
        """Flush buffer (lock held)."""
        if not self._buffer:
            return
        
        text = '\n'.join(self._buffer)
        
        # Truncate if needed
        if len(text) > self.max_batch_size:
            text = truncate(text, self.max_batch_size)
        
        batch = OutputBatch(
            stream=self.stream_name,
            text=text,
            line_count=len(self._buffer)
        )
        
        self._buffer = []
        self._buffer_size = 0
        self._last_flush = time.time()
        
        self.batch_callback(batch)


def split_text_for_events(text: str, max_size: int = 8000) -> List[str]:
    """Split text into chunks suitable for events.
    
    Args:
        text: Text to split
        max_size: Maximum size per chunk
        
    Returns:
        List of text chunks
    """
    if len(text) <= max_size:
        return [text]
    
    chunks = []
    remaining = text
    
    while remaining:
        if len(remaining) <= max_size:
            chunks.append(remaining)
            break
        
        # Try to break at newline
        break_point = max_size
        newline_pos = remaining.rfind('\n', 0, max_size)
        if newline_pos > max_size // 2:
            break_point = newline_pos + 1
        
        chunks.append(remaining[:break_point])
        remaining = remaining[break_point:]
    
    return chunks
