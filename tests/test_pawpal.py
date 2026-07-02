"""Tests for core PawPal+ behaviors."""

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
