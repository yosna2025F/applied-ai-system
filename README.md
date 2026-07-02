# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:


    ========================================
    Today's Schedule
    ========================================
    Daily plan for Jordan (time budget: 120 min):
    1. Morning walk (Mochi) — 30 min, high priority at 08:00
    2. Breakfast (Mochi) — 10 min, high priority at 08:30
    3. Litter cleanup (Luna) — 10 min, medium priority at 09:00
    4. Medication (Luna) — 5 min, high priority at 12:00
    5. Evening walk (Mochi) — 25 min, medium priority at 18:00
    Total scheduled: 80/120 min.


## 🧪 Testing PawPal+

```bash
# Run the full test suite:
pytest

# Run with coverage:
pytest --cov
```

Sample test output:

```
# Paste your pytest output here
```

## 📐 Smarter Scheduling

All scheduling logic lives in `pawpal_system.py` (the `Scheduler` and `Task`
classes). Each feature and the method(s) that implement it:

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler.sort_tasks()`, `Scheduler.sort_by_time()` | Priority order for selection; clock order for display |
| Filtering | `Scheduler.filter_tasks()`, `Scheduler._collect_tasks()` | By pet name and/or completion status; plan skips completed tasks |
| Conflict detection | `Scheduler.detect_conflicts()`, `Scheduler.classify_conflicts()`, `Scheduler.conflict_warning()`, `Scheduler._overlaps()` | Duration-aware overlap; same-pet vs. cross-pet; crash-safe warning |
| Recurring tasks | `Task.mark_complete()`, `Task._next_instance()`, `Task._next_due_date()` | Completing a daily/weekly task spawns the next occurrence |
| Plan generation | `Scheduler.generate_plan()`, `Scheduler.explain_plan()` | Greedy, priority-first fill under a time budget |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
