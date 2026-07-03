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

I used AI throughout the project as a design and review partner. Early on it helped me brainstorm and test my class design, questioning whether the Owner preferences field was actually used and pointing out I needed a Task → Pet back-reference so the scheduler could trace a pooled task back to its pet. Most of my later use was refactoring and testing: I asked it to review my Scheduler for edge cases, which surfaced latent issues like the unknown-recurrence rollover, and I had it help expand my pytest suite to cover sorting, conflict detection, and budget-aware planning. The most helpful prompts were specific and verification-focused like "what core behaviors should I test," "does the UI actually use these Scheduler methods," because they pushed the AI to analyze what I'd built and expose gaps instead of just producing new code.



**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?


One moment I didn't accept a suggestion as-is was around the latent bugs the AI flagged—the zero-budget plan reading as "not generated" and the unknown-recurrence task rolling over without a due date. It offered to write characterization tests pinning that behavior, but I pushed back, since asserting a bug still exists is misleading; I'd rather fix the behavior or leave it documented than lock it in. I also rejected boilerplate it leaned on, like a hardcoded st.session_state value and a sys.path insert in the test file, when a cleaner approach fit better. I evaluated its suggestions mainly by running them, my 17-test pytest suite had to stay green, I ran python main.py to confirm the CLI output was actually correct, and I cross-checked claims against the real code—for example, when it called conflict_warning() "dead code," I grepped the project and found the CLI does use it, so I kept it.
---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

I tested the behaviors most central to the scenario: task completion, recurrence (daily tasks rolling over to the next day, weekly advancing seven days across a month boundary, and one-off tasks not rolling over), and the core scheduling logic in generate_plan like budget enforcement, priority ordering, tie-breaking by shorter duration, overlap exclusion, and skipping completed tasks. I also covered conflict detection from several angles (same-pet vs. cross-pet, exact-duplicate times, and the boundary case where adjacent tasks touch but don't overlap) and confirmed tasks sort chronologically. These tests were important because they target the parts a busy owner actually relies on that the schedule respects their time, surfaces the right priorities, and warns about clashes.



**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?


I'm fairly confident the scheduler works correctly for the cases it's meant to handle the 17-test suite covers the core scheduling, sorting, conflict, and recurrence logic and all pass, and running python main.py confirms the end to end output matches what I expect. My confidence is highest on the algorithmic core and lower on the display layer and edge inputs, which are less covered. If I had more time, I'd test explain_plan()'s output formatting and skipped task reporting directly, add filter_tasks() cases.
---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

I'm most satisfied with the Scheduler and how cleanly the algorithmic logic came together. Keeping all the scheduling logic in one class while the data classes stayed simple made each feature like  priority-based selection, chronological display, duration-aware conflict detection, and recurrence rollover easy to test in isolation. I'm especially happy with the conflict detection distinguishing a single pet being double-booked from the owner being needed by two pets at once.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

If I had another iteration, I'd fix the two rough edges the review surfaced like make explain_plan() distinguish an empty plan from an ungenerated one, and validate the recurring field so an unknown cadence can't spawn a copy with no due date. I'd also reconsider the greedy scheduling algorithm. It's fast and easy to explain, but I'd like to at least detect when it keeps a lower-priority task over a higher-priority one that didn't fit, and warn the user. Finally, I'd tighten the Streamlit layer—upgrade the plain-text plan output to a proper table like the task list already uses, and add a positive "no conflicts" confirmation so the UI feels as polished as the underlying logic.



**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

One important thing I learned is that AI is most valuable as a reviewer that tests my design, not as a source of code to accept blindly. The best results came when I asked it to analyze what I'd already built like "what should I test," "does the UI actually use these methods," because that surfaced real gaps like unused fields, missing back-references, and  edge-case bugs I wouldn't have caught on my own. But it was just as important to push back when a suggestion didn't fit, like refusing to lock in buggy behavior with tests. I learned that keeping a clear separation of concerns in the design made this collaboration work because the logic lived in small, testable pieces and I could verify every AI suggestion against a passing test case.