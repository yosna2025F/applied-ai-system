"""PawPal+ core system.

Implements the four classes from diagrams/uml.mmd:
  Owner  -> holds pets + planning constraints (time budget)
  Pet    -> holds its own care tasks (dataclass)
  Task   -> a single care activity (dataclass)
  Scheduler -> derives tasks from the owner and builds/explains a daily plan

Scheduling design decisions:
  * Tasks are ordered by priority (higher int = more important), tie-broken by
    shorter duration first so more tasks fit.
  * A "conflict" means two timed tasks OVERLAP: each task occupies the interval
    [preferred_time, preferred_time + duration), so an 08:00 30-min task
    conflicts with an 08:15 task even though the strings differ. Time-budget
    limits are handled separately in generate_plan().
  * Only tasks that are still incomplete are planned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

# How far ahead the next occurrence of a recurring task falls, by frequency.
RECURRENCE_STEP = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),  # weeks=1 is exactly 7 days
}

# Human-readable labels for the integer priority scale.
PRIORITY_LABELS = {1: "low", 2: "medium", 3: "high"}


def _to_minutes(hhmm: str) -> int:
    """Convert an "HH:MM" clock string into minutes since midnight."""
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


class Owner:
    """A pet owner and the time constraint they bring to planning."""

    def __init__(self, name: str, available_minutes: int) -> None:
        """Create an owner with a name and a daily time budget in minutes."""
        self.name = name
        self.available_minutes = available_minutes
        self.pets: list[Pet] = []

    def add_pet(self, pet: "Pet") -> None:
        """Attach a pet to this owner (and set the pet's back-reference)."""
        if pet not in self.pets:
            self.pets.append(pet)
        pet.owner = self

    def remove_pet(self, pet: "Pet") -> None:
        """Detach a pet from this owner."""
        if pet in self.pets:
            self.pets.remove(pet)
            pet.owner = None

    def get_pets(self) -> list["Pet"]:
        """Return this owner's pets."""
        return self.pets


@dataclass
class Pet:
    """A single animal being cared for. Holds its own care tasks."""

    name: str
    species: str
    age: int
    owner: Owner | None = None
    tasks: list["Task"] = field(default_factory=list)

    def add_task(self, task: "Task") -> None:
        """Add a care task for this pet (and set the task's back-reference)."""
        if task not in self.tasks:
            self.tasks.append(task)
        task.pet = self

    def remove_task(self, task: "Task") -> None:
        """Remove a care task from this pet."""
        if task in self.tasks:
            self.tasks.remove(task)
            task.pet = None

    def get_tasks(self) -> list["Task"]:
        """Return this pet's tasks."""
        return self.tasks


@dataclass
class Task:
    """A single care activity (walk, feeding, meds, grooming, ...)."""

    name: str
    duration: int
    priority: int  # higher int = more important (1=low, 2=med, 3=high)
    preferred_time: str | None = None
    recurring: str | None = None
    due_date: date | None = None  # the day this occurrence is due
    complete: bool = False  # completion state that mark_complete() flips
    pet: "Pet | None" = None  # back-reference to the pet this task belongs to

    def mark_complete(self) -> None:
        """Mark this task done, rolling recurring tasks over to their next date.

        Completing a one-off task simply flips its ``complete`` flag. Completing
        a recurring task additionally spawns a fresh, incomplete copy for the
        next occurrence (same pet, time, and cadence) via ``_next_instance``.
        """
        self.complete = True
        if self.is_recurring() and self.pet is not None:
            self.pet.add_task(self._next_instance())

    def _next_instance(self) -> "Task":
        """Return a fresh, incomplete copy of this task for its next occurrence.

        Everything user-facing carries over; ``complete`` resets to False and
        ``due_date`` is advanced to the next occurrence by ``_next_due_date``.
        """
        return Task(
            name=self.name,
            duration=self.duration,
            priority=self.priority,
            preferred_time=self.preferred_time,
            recurring=self.recurring,
            due_date=self._next_due_date(),
        )

    def _next_due_date(self) -> date | None:
        """Compute the next occurrence's due date from this task's frequency.

        Advances the current ``due_date`` by the recurrence step (daily -> +1
        day, weekly -> +7 days) using ``timedelta``, which handles month/year
        rollover correctly. Falls back to today when no ``due_date`` is set, so
        a fresh daily task rolls over to tomorrow. Returns None for one-off
        tasks (nothing to schedule next).
        """
        step = RECURRENCE_STEP.get(self.recurring)
        if step is None:
            return None  # non-recurring: no next date
        base = self.due_date or date.today()
        return base + step

    def is_recurring(self) -> bool:
        """Return True if this task repeats (daily/weekly/etc.)."""
        return bool(self.recurring)

    def next_occurrence(self) -> str | None:
        """Return the recurrence cadence if recurring, else None."""
        return self.recurring if self.is_recurring() else None

    def priority_label(self) -> str:
        """Return the human-readable priority (falls back to the raw number)."""
        return PRIORITY_LABELS.get(self.priority, str(self.priority))


class Scheduler:
    """Builds and explains a daily plan from tasks under a time budget."""

    def __init__(self, owner: Owner) -> None:
        """Build a scheduler for an owner, deriving its tasks from the pets.

        Takes the Owner so the scheduler can read the time budget; the task
        list is DERIVED from the owner's pets so there's a single source of
        truth.
        """
        self.owner = owner
        self.time_budget = owner.available_minutes
        self.tasks = self._collect_tasks()
        self.plan: list[Task] = []

    def _collect_tasks(self) -> list[Task]:
        """Flatten every INCOMPLETE task from every one of the owner's pets.

        This is the scheduler's single source of truth; already-completed tasks
        are dropped here so they never appear in conflicts or the plan.
        """
        return [
            task
            for pet in self.owner.get_pets()
            for task in pet.get_tasks()
            if not task.complete  # already-done tasks don't need planning
        ]

    def sort_tasks(self) -> list[Task]:
        """Order tasks by priority (high first), tie-broken by shorter duration.

        This is the *selection* order used by ``generate_plan`` to decide which
        tasks win when time is scarce -- not the order they're displayed in.
        """
        return sorted(self.tasks, key=lambda t: (-t.priority, t.duration))

    def filter_tasks(
        self, complete: bool | None = None, pet_name: str | None = None
    ) -> list[Task]:
        """Return the owner's tasks filtered by completion status and/or pet.

        Each argument left as None means "don't filter on that field", and the
        two filters combine (AND). Sourced from ALL tasks (not ``self.tasks``,
        which already drops completed ones) so ``complete=True`` can find them.
        """
        tasks = [task for pet in self.owner.get_pets() for task in pet.get_tasks()]
        if complete is not None:
            tasks = [t for t in tasks if t.complete is complete]
        if pet_name is not None:
            tasks = [t for t in tasks if t.pet and t.pet.name == pet_name]
        return tasks

    def sort_by_time(self, tasks: list[Task] | None = None) -> list[Task]:
        """Order tasks chronologically by preferred_time; untimed tasks last.

        Sorts ``self.tasks`` by default, or a supplied list. "HH:MM" strings are
        zero-padded, so a plain string sort is already chronological; the
        leading ``is None`` in the key pushes untimed tasks to the end (False
        sorts before True). This is *display* order, not selection order.
        """
        items = self.tasks if tasks is None else tasks
        return sorted(items, key=lambda t: (t.preferred_time is None, t.preferred_time or ""))

    @staticmethod
    def _overlaps(a: Task, b: Task) -> bool:
        """True if two timed tasks' [start, start+duration) intervals overlap.

        Duration-aware: an 08:00 30-min task overlaps an 08:15 task even though
        their start strings differ. Assumes both tasks have a valid
        preferred_time (raises on bad data; see ``_safe_overlaps``).
        """
        a_start = _to_minutes(a.preferred_time)
        b_start = _to_minutes(b.preferred_time)
        return a_start < b_start + b.duration and b_start < a_start + a.duration

    def detect_conflicts(self) -> list[tuple[Task, Task]]:
        """Return every pair of timed tasks whose intervals overlap.

        Pairwise scan (O(n^2)) over timed tasks -- fine for the handful of tasks
        a pet owner has. Raises if any task has an unparseable time.
        """
        conflicts: list[tuple[Task, Task]] = []
        scheduled = [t for t in self.tasks if t.preferred_time]
        for i, first in enumerate(scheduled):
            for second in scheduled[i + 1:]:
                if self._overlaps(first, second):
                    conflicts.append((first, second))
        return conflicts

    def classify_conflicts(self) -> list[tuple[Task, Task, bool]]:
        """Like ``detect_conflicts``, but tag each pair with a same-pet flag.

        The bool is True when both tasks belong to the SAME pet (that pet is
        double-booked) and False for DIFFERENT pets (the single owner is
        double-booked and can't do both at once). Pet identity is compared by
        object, so two different pets sharing a name still count as cross-pet.
        """
        classified: list[tuple[Task, Task, bool]] = []
        for first, second in self.detect_conflicts():
            same_pet = first.pet is not None and first.pet is second.pet
            classified.append((first, second, same_pet))
        return classified

    def _safe_overlaps(self, a: Task, b: Task) -> bool:
        """Overlap check that returns False instead of raising on bad time data.

        Wraps ``_overlaps`` so an unparseable preferred_time is treated as
        "can't tell" rather than crashing the caller.
        """
        try:
            return self._overlaps(a, b)
        except (ValueError, AttributeError):
            return False  # unparseable time -> treat as "can't tell", not a crash

    def conflict_warning(self) -> str | None:
        """Return a single human-readable conflict warning, or None if clear.

        A lightweight, display-ready alternative to ``classify_conflicts``:
        unlike ``detect_conflicts`` it NEVER raises -- tasks with an unparseable
        preferred_time are skipped (via ``_safe_overlaps``) instead of crashing
        -- so the string can be shown straight to a user. Each conflict becomes
        one line noting whether a pet is double-booked or two pets clash.
        """
        conflicts: list[tuple[Task, Task, bool]] = []
        scheduled = [t for t in self.tasks if t.preferred_time]
        for i, first in enumerate(scheduled):
            for second in scheduled[i + 1:]:
                if self._safe_overlaps(first, second):
                    same_pet = first.pet is not None and first.pet is second.pet
                    conflicts.append((first, second, same_pet))

        if not conflicts:
            return None  # nothing to warn about

        lines = ["⚠️  Schedule conflicts found:"]
        for first, second, same_pet in conflicts:
            first_pet = first.pet.name if first.pet else "?"
            second_pet = second.pet.name if second.pet else "?"
            who = (
                f"{first_pet} is double-booked"
                if same_pet
                else f"{first_pet} and {second_pet} both need you"
            )
            lines.append(
                f"  - {first.name} ({first.preferred_time}) and "
                f"{second.name} ({second.preferred_time}) -- {who}"
            )
        return "\n".join(lines)

    def generate_plan(self) -> list[Task]:
        """Build the day's plan greedily: highest priority first, what fits.

        Walks tasks in ``sort_tasks`` order and commits each one that (a) stays
        within the time budget and (b) doesn't overlap an already-placed timed
        task. Skips (never breaks) on a bad fit, so a smaller later task can
        still fill leftover time -- this is greedy, not globally optimal, and
        can keep a lower-priority task over a higher-priority one that didn't
        fit. Stores and returns the plan.
        """
        plan: list[Task] = []
        used_minutes = 0

        for task in self.sort_tasks():
            if used_minutes + task.duration > self.time_budget:
                continue  # would exceed the owner's available time
            if task.preferred_time and any(
                self._overlaps(task, p) for p in plan if p.preferred_time
            ):
                continue  # would overlap a higher-priority task already placed
            plan.append(task)
            used_minutes += task.duration

        self.plan = plan
        return plan

    def explain_plan(self) -> str:
        """Return a human-readable summary of the current plan.

        Lists the planned tasks in chronological (display) order via
        ``sort_by_time``, reports total scheduled minutes against the budget,
        and names any tasks that were skipped for time or overlap. Returns a
        prompt to run ``generate_plan`` first if no plan exists yet.
        """
        if not self.plan:
            return "No plan generated yet. Call generate_plan() first."

        lines = [
            f"Daily plan for {self.owner.name} "
            f"(time budget: {self.time_budget} min):",
        ]
        # Display chronologically by preferred_time (untimed tasks last),
        # even though tasks are SELECTED by priority in generate_plan().
        ordered = self.sort_by_time(self.plan)
        used = 0
        for i, task in enumerate(ordered, start=1):
            used += task.duration
            pet_name = task.pet.name if task.pet else "?"
            slot = f" at {task.preferred_time}" if task.preferred_time else ""
            lines.append(
                f"  {i}. {task.name} ({pet_name}) — {task.duration} min, "
                f"{task.priority_label()} priority{slot}"
            )
        lines.append(f"Total scheduled: {used}/{self.time_budget} min.")

        skipped = [t for t in self.tasks if t not in self.plan]
        if skipped:
            names = ", ".join(t.name for t in skipped)
            lines.append(
                f"Skipped (no time left or time overlap): {names}."
            )
        return "\n".join(lines)
