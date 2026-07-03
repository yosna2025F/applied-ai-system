# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

My initial UML design used four classes

Owner — represents the pet owner and the constraints they bring to planning. It holds their name, available_minutes (their daily time budget), and preferences, plus a list of their pets. Its responsibility is managing pets (add_pet, remove_pet, get_pets).

Pet — represents a single animal being cared for (name, species, age). It keeps a back-reference to its owner and a list of its own tasks. Its responsibility is managing its care tasks (add_task, remove_task, get_tasks).

Task — represents a single care activity like a walk, feeding, or medication. It carries the details the scheduler needs: duration, priority, category, preferred_time, and whether it's recurring.

Scheduler — the "brain" of the system. It takes a list of tasks and a time budget and is responsible for all the algorithmic logic: sorting tasks by priority (sort_tasks), finding conflicts (detect_conflicts), building the daily plan (generate_plan), and explaining the reasoning behind it (explain_plan).

an Owner has many Pets, and each Pet has many Tasks. The Scheduler doesn't own any of these. all scheduling logic lives in Scheduler so the data classes stay simple and the logic can be tested on its own.

**b. Design changes**

- Did your design change during implementation?

yes

- If yes, describe at least one change and why you made it.

I added a pet back-reference to Task. Originally the relationship only went Pet → Task (a pet held a list of tasks), but the Scheduler works on a flat pooled list of tasks. Without a way to trace a task back to its pet, the plan couldn't say which pet a task belonged to. This mirrors the Pet → Owner back-reference I already had.

I added a done field to Task. My stub had a mark_done() method but no attribute for it to update, so I added done: bool = False to give the method actual state to change.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?


My scheduler considers time (the owner's daily minute budget) and priority (importance, as an integer scale), and it avoids double-booking a preferred time slot. I decided time and priority mattered most because they're the core of the scenario, a busy owner with limited time needs the most important tasks to fit. I deliberately dropped owner-level preferences: I found my code was storing them but never using them, so rather than keep an unused constraint, I scoped the design down to what actually drives the plan.


**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

My scheduler uses a greedy, priority-first algorithm rather than searching for the mathematically optimal set of tasks; this can occasionally keep a lower-priority task over a higher-priority one that didn't fit, but it's fast, predictable, easy to explain to the user, and more than sufficient for the small number of daily tasks a pet owner actually has.


---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.


import os
import sys

# Make the project root importable when running pytest from anywhere.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.session_state hard coded

- How did you evaluate or verify what the AI suggested?

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
