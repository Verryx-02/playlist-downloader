"""
Progress bar handling for spot-downloader using Rich library.

This module provides a styled progress bar similar to spotDL's,
with custom colors and formatting.
"""

from typing import Optional

from rich import get_console
from rich.console import JustifyMethod, OverflowMethod
from rich.highlighter import Highlighter
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    Task,
    TaskID,
)
from rich.style import StyleType
from rich.text import Text
from rich.theme import Theme


# Custom theme matching spotDL's colors
PROGRESS_THEME = Theme({
    "bar.back": "grey23",
    "bar.complete": "rgb(165,66,129)",  # Magenta/purple
    "bar.finished": "rgb(114,156,31)",  # Green when done
    "bar.pulse": "rgb(165,66,129)",
    "progress.percentage": "white",
})


class SizedTextColumn(ProgressColumn):
    """
    Custom sized text column based on the Rich library.
    
    Allows text to be truncated with ellipsis if it exceeds
    the specified width.
    """

    def __init__(
        self,
        text_format: str,
        style: StyleType = "none",
        justify: JustifyMethod = "left",
        markup: bool = True,
        highlighter: Optional[Highlighter] = None,
        overflow: Optional[OverflowMethod] = None,
        width: int = 20,
    ) -> None:
        """
        Initialize the sized text column.
        
        Args:
            text_format: Format string for the text.
            style: Style to apply.
            justify: Text justification.
            markup: Whether to parse markup.
            highlighter: Optional highlighter.
            overflow: Overflow handling method.
            width: Maximum width of the column.
        """
        self.text_format = text_format
        self.justify: JustifyMethod = justify
        self.style = style
        self.markup = markup
        self.highlighter = highlighter
        self.overflow: Optional[OverflowMethod] = overflow
        self.width = width
        super().__init__()

    def render(self, task: Task) -> Text:
        """Render the column."""
        _text = self.text_format.format(task=task)
        if self.markup:
            text = Text.from_markup(_text, style=self.style, justify=self.justify)
        else:
            text = Text(_text, style=self.style, justify=self.justify)
        if self.highlighter:
            self.highlighter.highlight(text)

        text.truncate(max_width=self.width, overflow=self.overflow, pad=True)
        return text


class MatchingProgressBar:
    """
    Progress bar for YouTube matching phase.
    
    Displays:
    - Description (e.g., "Matching")
    - Status message (matched/failed/close matches counts)
    - Progress bar with spotDL-style colors
    - Percentage
    """
    
    def __init__(self, total: int, description: str = "Matching"):
        """
        Initialize the progress bar.
        
        Args:
            total: Total number of items to process.
            description: Description to show on the left.
        """
        self.total = total
        self.description = description
        self.matched = 0
        self.failed = 0
        self.close_matches = 0
        self.completed = 0
        
        self.console = get_console()
        self.console.push_theme(PROGRESS_THEME)
        
        self.progress = Progress(
            SizedTextColumn(
                "[white]{task.description}",
                overflow="ellipsis",
                width=15,
            ),
            SizedTextColumn(
                "{task.fields[status]}",
                width=35,
                style="white",
            ),
            BarColumn(bar_width=40, finished_style="green"),
            "[progress.percentage]{task.percentage:>3.0f}%",
            console=self.console,
            transient=False,
            refresh_per_second=10,
        )
        
        self.task_id: Optional[TaskID] = None
        self._started = False
    
    def __enter__(self) -> "MatchingProgressBar":
        """Start the progress bar."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop the progress bar."""
        self.stop()
    
    def start(self) -> None:
        """Start the progress bar (can be called manually)."""
        if not self._started:
            self.progress.start()
            self.task_id = self.progress.add_task(
                description=self.description,
                total=self.total,
                status=self._get_status_text(),
            )
            self._started = True
    
    def stop(self) -> None:
        """Stop the progress bar."""
        if self._started:
            self.progress.stop()
            self._started = False
    
    def _get_status_text(self) -> str:
        """Get the status text showing matched/failed/close matches counts."""
        parts = [
            f"[green]✓ {self.matched}[/green]",
            f"[red]✗ {self.failed}[/red]",
        ]
        if self.close_matches > 0:
            parts.append(f"[yellow]⚠ {self.close_matches}[/yellow]")
        return "  ".join(parts)
    
    def update(self, matched: bool, has_close_matches: bool = False) -> None:
        """
        Update the progress bar with a completed item.
        
        Args:
            matched: Whether the item was successfully matched.
            has_close_matches: Whether the match has close alternatives.
        """
        self.completed += 1
        if matched:
            self.matched += 1
            if has_close_matches:
                self.close_matches += 1
        else:
            self.failed += 1
        
        if self.task_id is not None:
            self.progress.update(
                self.task_id,
                completed=self.completed,
                status=self._get_status_text(),
            )
    
    def log(self, message: str) -> None:
        """
        Print a log message above the progress bar.
        
        Args:
            message: The message to print.
        """
        self.progress.console.print(message, highlight=False)