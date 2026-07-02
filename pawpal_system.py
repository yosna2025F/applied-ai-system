"""PawPal+ core system.

Implements the four classes from diagrams/uml.mmd:
  Owner  -> holds pets + planning constraints (time budget)
  Pet    -> holds its own care tasks (dataclass)
  Task   -> a single care activity (dataclass)
  Scheduler -> derives tasks from the owner and builds/explains a daily plan

Scheduling design decisions:
  * Tasks are ordered by priority (higher int = more important), tie-broken by
    shorter duration first so more tasks fit.
  * A "conflict" means two tasks want the same non-empty preferred_time
    slot. Time-budget limits are handled separately in generate_plan().
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Human-readable labels for the integer priority scale.
PRIORITY_LABELS = {1: "low", 2: "medium", 3: "high"}


# A pet owner and the time constraint they bring to planning.
class Owner:

    # Create an owner with a name and a daily time budget in minutes.
    def __init__(self, name: str, available_minutes: int) -> None:
        self.name = name
        self.available_minutes = available_minutes
        self.pets: list[Pet] = []

    # Attach a pet to this owner (and set the pet's back-reference).
    def add_pet(self, pet: "Pet") -> None:
        if pet not in self.pets:
            self.pets.append(pet)
        pet.owner = self

    # Detach a pet from this owner.
    def remove_pet(self, pet: "Pet") -> None:
        if pet in self.pets:
            self.pets.remove(pet)
            pet.owner = None

    # Return this owner's pets.
    def get_pets(self) -> list["Pet"]:
        return self.pets


# A single animal being cared for. Holds its own care tasks.
@dataclass
class Pet:

    name: str
    species: str
    age: int
    owner: Owner | None = None
    tasks: list["Task"] = field(default_factory=list)

    # Add a care task for this pet (and set the task's back-reference).
    def add_task(self, task: "Task") -> None:
        if task not in self.tasks:
            self.tasks.append(task)
        task.pet = self

    # Remove a care task from this pet.
    def remove_task(self, task: "Task") -> None:
        if task in self.tasks:
            self.tasks.remove(task)
            task.pet = None

    # Return this pet's tasks.
    def get_tasks(self) -> list["Task"]:
        return self.tasks


# A single care activity (walk, feeding, meds, grooming, ...).
@dataclass
class Task:

    name: str
    duration: int
    priority: int  # higher int = more important (1=low, 2=med, 3=high)
    preferred_time: str | None = None
    recurring: str | None = None
    complete: bool = False  # completion state that mark_complete() flips
    pet: "Pet | None" = None  # back-reference to the pet this task belongs to

    # Mark this task as completed for the day.
    def mark_complete(self) -> None:
        self.complete = True

    # Return True if this task repeats (daily/weekly/etc.).
    def is_recurring(self) -> bool:
        return bool(self.recurring)

    # Return the recurrence cadence if recurring, else None.
    def next_occurrence(self) -> str | None:
        return self.recurring if self.is_recurring() else None

    # Human-readable priority (falls back to the raw number).
    def priority_label(self) -> str:
        return PRIORITY_LABELS.get(self.priority, str(self.priority))


# Builds and explains a daily plan from tasks under a time budget.
class Scheduler:

    # Build a scheduler for an owner, deriving its task list from the owner's pets.
    def __init__(self, owner: Owner) -> None:
        # Take the Owner so the scheduler can read the time budget; the task
        # list is DERIVED from the owner's pets so there's a single source of
        # truth.
        self.owner = owner
        self.time_budget = owner.available_minutes
        self.tasks = self._collect_tasks()
        self.plan: list[Task] = []

    # Flatten every task from every one of the owner's pets.
    def _collect_tasks(self) -> list[Task]:
        return [task for pet in self.owner.get_pets() for task in pet.get_tasks()]

    # Order tasks by priority (high first), tie-broken by shorter duration.
    def sort_tasks(self) -> list[Task]:
        return sorted(self.tasks, key=lambda t: (-t.priority, t.duration))

    # Return pairs of tasks that want the same non-empty preferred_time slot.
    def detect_conflicts(self) -> list[tuple[Task, Task]]:
        conflicts: list[tuple[Task, Task]] = []
        scheduled = [t for t in self.tasks if t.preferred_time]
        for i, first in enumerate(scheduled):
            for second in scheduled[i + 1:]:
                if first.preferred_time == second.preferred_time:
                    conflicts.append((first, second))
        return conflicts

    # Greedily choose tasks by priority that fit the budget and don't double-book a slot.
    def generate_plan(self) -> list[Task]:
        plan: list[Task] = []
        used_minutes = 0
        used_slots: set[str] = set()

        for task in self.sort_tasks():
            if used_minutes + task.duration > self.time_budget:
                continue  # would exceed the owner's available time
            if task.preferred_time and task.preferred_time in used_slots:
                continue  # slot already taken by a higher-priority task
            plan.append(task)
            used_minutes += task.duration
            if task.preferred_time:
                used_slots.add(task.preferred_time)

        self.plan = plan
        return plan

    # Return a human-readable explanation of the current plan.
    def explain_plan(self) -> str:
        if not self.plan:
            return "No plan generated yet. Call generate_plan() first."

        lines = [
            f"Daily plan for {self.owner.name} "
            f"(time budget: {self.time_budget} min):",
        ]
        # Display chronologically by preferred_time (untimed tasks last),
        # even though tasks are SELECTED by priority in generate_plan().
        ordered = sorted(
            self.plan,
            key=lambda t: (t.preferred_time is None, t.preferred_time or ""),
        )
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
                f"Skipped (no time left or slot conflict): {names}."
            )
        return "\n".join(lines)
