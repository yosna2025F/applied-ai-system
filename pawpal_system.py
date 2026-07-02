"""PawPal+ core system.

Class stubs generated from diagrams/uml.mmd. No scheduling logic yet —
method bodies are placeholders to be filled in incrementally (workflow step 4).

Pet and Task are dataclasses (mostly data holders); Owner and Scheduler are
plain classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class Owner:
    """A pet owner and the constraints they bring to planning (time, preferences)."""

    def __init__(
        self,
        name: str,
        available_minutes: int,
        preferences: dict | None = None,
    ) -> None:
        self.name = name
        self.available_minutes = available_minutes
        self.preferences = preferences or {}
        self.pets: list[Pet] = []

    def add_pet(self, pet: "Pet") -> None:
        """Attach a pet to this owner (and set the pet's back-reference)."""
        ...

    def remove_pet(self, pet: "Pet") -> None:
        """Detach a pet from this owner."""
        ...

    def get_pets(self) -> list["Pet"]:
        """Return this owner's pets."""
        ...


@dataclass
class Pet:
    """A single animal being cared for. Holds its own care tasks."""

    name: str
    species: str
    age: int
    owner: Owner | None = None
    tasks: list["Task"] = field(default_factory=list)

    def add_task(self, task: "Task") -> None:
        """Add a care task for this pet."""
        ...

    def remove_task(self, task: "Task") -> None:
        """Remove a care task from this pet."""
        ...

    def get_tasks(self) -> list["Task"]:
        """Return this pet's tasks."""
        ...


@dataclass
class Task:
    """A single care activity (walk, feeding, meds, grooming, ...)."""

    name: str
    duration: int
    priority: int  # higher int = more important (e.g. 1=low, 2=med, 3=high)
    category: str = ""
    preferred_time: str | None = None
    recurring: str | None = None
    done: bool = False  # (#3) completion state that mark_done() flips
    pet: "Pet | None" = None  # (#1) back-reference to the pet this task belongs to

    def mark_done(self) -> None:
        """Mark this task as completed for the day."""
        ...

    def is_recurring(self) -> bool:
        """Return True if this task repeats (daily/weekly/etc.)."""
        ...

    def next_occurrence(self) -> str | None:
        """Return when this task should next happen, if recurring."""
        ...


class Scheduler:
    """Builds and explains a daily plan from tasks under a time budget."""

    def __init__(self, tasks: list[Task], owner: Owner) -> None:
        # (#2) take the Owner so the scheduler can read BOTH the time budget
        # and the owner's preferences (an explicit constraint in the brief).
        self.tasks = tasks
        self.owner = owner
        self.time_budget = owner.available_minutes
        self.preferences = owner.preferences
        self.plan: list[Task] = []

    def sort_tasks(self) -> list[Task]:
        """Order tasks by priority (and tie-breakers like duration)."""
        ...

    def detect_conflicts(self) -> list[tuple[Task, Task]]:
        """Find tasks that overlap or push the plan over the time budget."""
        ...

    def generate_plan(self) -> list[Task]:
        """Choose and order tasks that fit the time budget; store in self.plan."""
        ...

    def explain_plan(self) -> str:
        """Return a human-readable explanation of why the plan was chosen."""
        ...
