"""Tests for core PawPal+ behaviors."""

from datetime import date

from pawpal_system import Pet, Task

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
