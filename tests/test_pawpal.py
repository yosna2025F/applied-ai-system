"""Tests for core PawPal+ behaviors."""

from datetime import date

import pytest

from pawpal_system import Owner, Pet, Scheduler, Task

#Calling mark_complete() flips the task's status to complete.
def test_task_completion():
    
    task = Task("Morning walk", duration=30, priority=3)
    assert task.complete is False  # starts incomplete

    task.mark_complete()

    assert task.complete is True

#Adding a task to a Pet increases that pet's task count.
def test_task_addition_increases_count():

    pet = Pet("Mochi", "dog", age=3)
    assert len(pet.get_tasks()) == 0  # starts with no tasks

    pet.add_task(Task("Breakfast", duration=10, priority=2))

    assert len(pet.get_tasks()) == 1

#Completing a recurring task spawns a fresh, incomplete copy for the next occurrence.
def test_recurring_task_rolls_over_on_complete():

    pet = Pet("Mochi", "dog", age=3)
    walk = Task("Walk", duration=30, priority=3,
                preferred_time="08:00", recurring="daily",
                due_date=date(2026, 7, 2))
    pet.add_task(walk)

    walk.mark_complete()

    tasks = pet.get_tasks()
    assert len(tasks) == 2  # original + spawned next occurrence
    next_walk = tasks[1]
    assert next_walk.complete is False           # the new one is pending
    assert next_walk.name == "Walk"              # same details carried over
    assert next_walk.recurring == "daily"
    assert next_walk.pet is pet                  # attached to the same pet
    assert next_walk.due_date == date(2026, 7, 3)  # daily -> today + 1 day

#A weekly task rolls over to 7 days later, crossing month boundaries correctly.
def test_weekly_task_advances_seven_days():

    pet = Pet("Luna", "cat", age=5)
    # 2026-07-29 + 7 days crosses into August -> exercises timedelta's accuracy.
    meds = Task("Meds", duration=5, priority=3,
                recurring="weekly", due_date=date(2026, 7, 29))
    pet.add_task(meds)

    meds.mark_complete()

    assert pet.get_tasks()[1].due_date == date(2026, 8, 5)

#Completing a one-off task does NOT spawn a copy.
def test_non_recurring_task_does_not_roll_over():

    pet = Pet("Mochi", "dog", age=3)
    bath = Task("Bath", duration=20, priority=2)  # recurring=None
    pet.add_task(bath)

    bath.mark_complete()

    assert len(pet.get_tasks()) == 1  # no new instance created

#classify_conflicts flags same-pet overlaps and cross-pet (owner) overlaps.
def test_classify_conflicts_same_and_cross_pet():

    owner = Owner("Jordan", available_minutes=120)
    rex = Pet("Rex", "dog", age=2)
    luna = Pet("Luna", "cat", age=5)
    owner.add_pet(rex)
    owner.add_pet(luna)

    # Same pet: Rex's walk (08:00-08:30) overlaps his feed (08:10-08:20).
    rex.add_task(Task("Walk", 30, priority=3, preferred_time="08:00"))
    rex.add_task(Task("Feed", 10, priority=2, preferred_time="08:10"))
    # Cross pet: Rex's groom (12:00-12:15) overlaps Luna's nap (12:00-12:20).
    rex.add_task(Task("Groom", 15, priority=2, preferred_time="12:00"))
    luna.add_task(Task("Nap", 20, priority=1, preferred_time="12:00"))

    conflicts = Scheduler(owner).classify_conflicts()

    same = [(a.name, b.name) for a, b, same_pet in conflicts if same_pet]
    cross = [(a.name, b.name) for a, b, same_pet in conflicts if not same_pet]

    assert same == [("Walk", "Feed")]     # Rex double-booked
    assert cross == [("Groom", "Nap")]    # owner needed by both pets

#conflict_warning returns None when clear, a message on overlap, and never crashes.
def test_conflict_warning_is_safe():

    owner = Owner("Jordan", available_minutes=120)
    rex = Pet("Rex", "dog", age=2)
    owner.add_pet(rex)

    # No tasks -> no warning.
    assert Scheduler(owner).conflict_warning() is None

    # Overlapping tasks -> a readable warning naming both tasks.
    rex.add_task(Task("Walk", 30, priority=3, preferred_time="08:00"))
    rex.add_task(Task("Feed", 10, priority=2, preferred_time="08:10"))
    msg = Scheduler(owner).conflict_warning()
    assert msg is not None
    assert "Walk" in msg and "Feed" in msg

    # A malformed preferred_time must NOT raise -- it's skipped, not fatal.
    rex.add_task(Task("Oops", 5, priority=1, preferred_time="8am"))
    Scheduler(owner).conflict_warning()  # would raise ValueError without _safe_overlaps


# --- generate_plan: the core scheduling logic -------------------------------

#Tasks whose cumulative duration exceeds the budget are dropped.
def test_generate_plan_enforces_time_budget():

    owner = Owner("Jordan", available_minutes=40)
    pet = Pet("Rex", "dog", age=2)
    owner.add_pet(pet)
    # Three 20-min tasks, all same priority -> only two fit in 40 min.
    pet.add_task(Task("A", 20, priority=2))
    pet.add_task(Task("B", 20, priority=2))
    pet.add_task(Task("C", 20, priority=2))

    plan = Scheduler(owner).generate_plan()

    assert len(plan) == 2
    assert sum(t.duration for t in plan) <= 40

#When time is scarce, higher priority is selected over lower.
def test_generate_plan_prefers_higher_priority():

    owner = Owner("Jordan", available_minutes=30)
    pet = Pet("Rex", "dog", age=2)
    owner.add_pet(pet)
    low = Task("Low", 30, priority=1)
    high = Task("High", 30, priority=3)
    pet.add_task(low)
    pet.add_task(high)

    plan = Scheduler(owner).generate_plan()

    assert plan == [high]  # only room for one; the high-priority task wins

#Equal priority is tie-broken by shorter duration first.
def test_generate_plan_tie_breaks_by_shorter_duration():

    owner = Owner("Jordan", available_minutes=30)
    pet = Pet("Rex", "dog", age=2)
    owner.add_pet(pet)
    long = Task("Long", 30, priority=2)
    short = Task("Short", 10, priority=2)
    pet.add_task(long)
    pet.add_task(short)

    plan = Scheduler(owner).generate_plan()

    assert plan[0] is short  # shorter of the equal-priority tasks selected first

#Overlapping timed tasks: only the first-placed (higher priority) is planned.
def test_generate_plan_excludes_overlapping_task():

    owner = Owner("Jordan", available_minutes=120)
    pet = Pet("Rex", "dog", age=2)
    owner.add_pet(pet)
    # Walk 08:00-08:30 (higher priority) overlaps Feed 08:10-08:20.
    walk = Task("Walk", 30, priority=3, preferred_time="08:00")
    feed = Task("Feed", 10, priority=2, preferred_time="08:10")
    pet.add_task(walk)
    pet.add_task(feed)

    plan = Scheduler(owner).generate_plan()

    assert walk in plan
    assert feed not in plan  # overlaps an already-placed higher-priority task

#Greedy fill: a small low-priority task can fill time a skipped big task left.
def test_generate_plan_is_greedy_not_optimal():

    owner = Owner("Jordan", available_minutes=30)
    pet = Pet("Rex", "dog", age=2)
    owner.add_pet(pet)
    # High priority but too big to fit -> skipped, not fatal.
    big = Task("Big", 40, priority=3)
    # Lower priority but fits -> fills the leftover time.
    small = Task("Small", 20, priority=1)
    pet.add_task(big)
    pet.add_task(small)

    plan = Scheduler(owner).generate_plan()

    assert big not in plan   # didn't fit, skipped
    assert small in plan     # greedily filled remaining time

#Completed tasks never appear in the plan.
def test_generate_plan_ignores_completed_tasks():

    owner = Owner("Jordan", available_minutes=120)
    pet = Pet("Rex", "dog", age=2)
    owner.add_pet(pet)
    done = Task("Done", 30, priority=3)
    pending = Task("Pending", 30, priority=2)
    pet.add_task(done)
    pet.add_task(pending)
    done.mark_complete()

    plan = Scheduler(owner).generate_plan()

    assert done not in plan
    assert pending in plan


# --- overlap boundary: [start, start + duration) is half-open ---------------

#Adjacent tasks that touch but don't overlap are NOT a conflict.
def test_adjacent_tasks_do_not_conflict():

    owner = Owner("Jordan", available_minutes=120)
    pet = Pet("Rex", "dog", age=2)
    owner.add_pet(pet)
    # Walk ends exactly at 08:30; Feed starts at 08:30 -> touch, don't overlap.
    pet.add_task(Task("Walk", 30, priority=3, preferred_time="08:00"))
    pet.add_task(Task("Feed", 10, priority=2, preferred_time="08:30"))

    assert Scheduler(owner).detect_conflicts() == []

#detect_conflicts() RAISES on an unparseable preferred_time 
def test_detect_conflicts_raises_on_malformed_time():

    owner = Owner("Jordan", available_minutes=120)
    pet = Pet("Rex", "dog", age=2)
    owner.add_pet(pet)
    pet.add_task(Task("Walk", 30, priority=3, preferred_time="08:00"))
    pet.add_task(Task("Oops", 5, priority=1, preferred_time="8am"))

    with pytest.raises(ValueError):
        Scheduler(owner).detect_conflicts()


# --- sorting correctness ----------------------------------------------------

#sort_by_time returns tasks in chronological order; untimed tasks land last.
def test_sort_by_time_is_chronological():

    owner = Owner("Jordan", available_minutes=120)
    pet = Pet("Rex", "dog", age=2)
    owner.add_pet(pet)
    # Added out of order, plus one untimed task.
    pet.add_task(Task("Noon", 10, priority=2, preferred_time="12:00"))
    pet.add_task(Task("Dawn", 10, priority=2, preferred_time="06:30"))
    pet.add_task(Task("Evening", 10, priority=2, preferred_time="18:15"))
    pet.add_task(Task("Whenever", 10, priority=2))  # no preferred_time

    ordered = Scheduler(owner).sort_by_time()

    names = [t.name for t in ordered]
    assert names == ["Dawn", "Noon", "Evening", "Whenever"]  # timed first, in order


# --- conflict detection: exact duplicate times ------------------------------

#Two tasks at the EXACT same preferred_time are flagged as a conflict.
def test_detect_conflicts_flags_duplicate_times():

    owner = Owner("Jordan", available_minutes=120)
    pet = Pet("Rex", "dog", age=2)
    owner.add_pet(pet)
    # Both start at 09:00 -> identical start times always overlap.
    walk = Task("Walk", 30, priority=3, preferred_time="09:00")
    feed = Task("Feed", 10, priority=2, preferred_time="09:00")
    pet.add_task(walk)
    pet.add_task(feed)

    conflicts = Scheduler(owner).detect_conflicts()

    assert (walk, feed) in conflicts
