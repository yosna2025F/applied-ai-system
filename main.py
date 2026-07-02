"""PawPal+ CLI demo.

A small script that builds an owner with a couple of pets and some tasks,
then prints today's schedule to the terminal. Run with:

    python main.py
"""

from pawpal_system import Owner, Pet, Task, Scheduler

#Create a sample owner with two pets and several care tasks.
def build_demo() -> Owner:

    # Tight budget on purpose: the pending tasks total 85 min, so a 60-min
    # budget forces the scheduler to skip lower-priority tasks.
    owner = Owner("Jordan", available_minutes=60)

    # Two pets
    mochi = Pet("Mochi", "dog", age=3)
    luna = Pet("Luna", "cat", age=5)
    owner.add_pet(mochi)
    owner.add_pet(luna)

    # Tasks are added OUT OF TIME ORDER on purpose, so sort_by_time() has
    # something real to reorder. (Evening before morning, etc.)
    mochi.add_task(Task("Evening walk", 25, priority=2,
                        preferred_time="18:00", recurring="daily"))
    mochi.add_task(Task("Morning walk", 30, priority=3,
                        preferred_time="08:00", recurring="daily"))
    mochi.add_task(Task("Breakfast", 10, priority=3,
                        preferred_time="08:30"))
    mochi.add_task(Task("Fetch", 15, priority=1))  # no preferred time

    luna.add_task(Task("Medication", 5, priority=3,
                       preferred_time="12:00", recurring="daily"))
    luna.add_task(Task("Litter cleanup", 10, priority=2,
                       preferred_time="09:00"))

    # Pre-complete one task so the completion filter has something to show.
    for task in luna.get_tasks():
        if task.name == "Litter cleanup":
            task.mark_complete()

    return owner


def main() -> None:
    owner = build_demo()
    scheduler = Scheduler(owner)

    # 1. Sorting: tasks were added out of order — sort_by_time() puts them in
    #    chronological order (untimed tasks last).
    print("=" * 40)
    print("All pending tasks, sorted by time")
    print("=" * 40)
    for task in scheduler.sort_by_time():
        slot = task.preferred_time or "—"
        print(f"  {slot:>5}  {task.name} ({task.pet.name})")

    # 2. Filtering by pet name.
    print()
    print("=" * 40)
    print("Filter: Mochi's tasks only")
    print("=" * 40)
    for task in scheduler.filter_tasks(pet_name="Mochi"):
        print(f"  {task.name}")

    # 3. Filtering by completion status (looks across ALL tasks, including
    #    completed ones the scheduler otherwise skips).
    print()
    print("=" * 40)
    print("Filter: completed vs pending")
    print("=" * 40)
    completed = scheduler.filter_tasks(complete=True)
    pending = scheduler.filter_tasks(complete=False)
    print("  Completed:", ", ".join(t.name for t in completed) or "(none)")
    print("  Pending:  ", ", ".join(t.name for t in pending) or "(none)")

    # 4. The full plan (already prints chronologically via sort_by_time).
    print()
    print("=" * 40)
    print("Today's Schedule")
    print("=" * 40)
    scheduler.generate_plan()
    print(scheduler.explain_plan())


if __name__ == "__main__":
    main()
