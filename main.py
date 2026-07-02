"""PawPal+ CLI demo.

A small script that builds an owner with a couple of pets and some tasks,
then prints today's schedule to the terminal. Run with:

    python main.py
"""

from pawpal_system import Owner, Pet, Task, Scheduler


def build_demo() -> Owner:
    """Create a sample owner with two pets and several care tasks."""
    owner = Owner("Jordan", available_minutes=120)

    # Two pets
    mochi = Pet("Mochi", "dog", age=3)
    luna = Pet("Luna", "cat", age=5)
    owner.add_pet(mochi)
    owner.add_pet(luna)

    # Tasks for Mochi (the dog) — different preferred times
    mochi.add_task(Task("Morning walk", 30, priority=3,
                        preferred_time="08:00", recurring="daily"))
    mochi.add_task(Task("Breakfast", 10, priority=3,
                        preferred_time="08:30"))
    mochi.add_task(Task("Evening walk", 25, priority=2,
                        preferred_time="18:00", recurring="daily"))

    # Tasks for Luna (the cat) — different preferred times
    luna.add_task(Task("Litter cleanup", 10, priority=2,
                       preferred_time="09:00"))
    luna.add_task(Task("Medication", 5, priority=3,
                      preferred_time="12:00", recurring="daily"))

    return owner


def main() -> None:
    owner = build_demo()
    scheduler = Scheduler(owner)
    scheduler.generate_plan()

    print("=" * 40)
    print("Today's Schedule")
    print("=" * 40)
    print(scheduler.explain_plan())


if __name__ == "__main__":
    main()
