from datetime import time

import streamlit as st

from pawpal_system import Owner, Pet, Task, Scheduler

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# Map the UI's priority words to the integer scale Task expects.
PRIORITY_MAP = {"low": 1, "medium": 2, "high": 3}

# Persist the Owner in the session "vault" so it (and its pets/tasks) are NOT
# recreated empty on every rerun. The constructor runs once per session.
if "owner" not in st.session_state:
    st.session_state.owner = Owner("", available_minutes=120)

# Grab the persistent instance for the rest of the script to use.
owner = st.session_state.owner

st.title("🐾 PawPal+")

st.markdown(
    "PawPal+ helps a pet owner plan daily care tasks across their pets. "
    "Add your pets and their tasks, set the time you have available, then "
    "generate a prioritized daily schedule."
)

with st.expander("How the schedule works"):
    st.markdown(
        """
- Tasks are chosen by **priority** (high → low) and must fit your **time budget**.
- A task can have a **preferred time**; if two tasks' times **overlap** (based
  on their durations) they conflict, and only the higher-priority one keeps it.
- **Completed** tasks are left out of the plan automatically.
- The plan is shown **chronologically**, and anything that didn't fit is listed as skipped.
"""
    )

st.divider()

st.subheader("Owner")
ocol1, ocol2 = st.columns(2)
with ocol1:
    owner.name = st.text_input("Owner name", value=owner.name)
with ocol2:
    # The time budget is the core scheduling constraint (Owner.available_minutes).
    owner.available_minutes = st.number_input(
        "Time available today (minutes)",
        min_value=0,
        max_value=1440,
        value=owner.available_minutes,
        step=15,
    )

st.markdown("### Pets")
# A form so pressing Enter submits, and clear_on_submit empties the fields after.
with st.form("add_pet_form", clear_on_submit=True):
    pcol1, pcol2, pcol3 = st.columns(3)
    with pcol1:
        new_pet_name = st.text_input("Pet name", value="")
    with pcol2:
        new_pet_species = st.selectbox("Species", ["dog", "cat", "other"])
    with pcol3:
        new_pet_age = st.number_input("Age", min_value=0, max_value=30, value=3)
    add_pet_clicked = st.form_submit_button("Add pet")

if add_pet_clicked:
    # Owner.add_pet() is the method that handles adding a pet to the owner.
    if new_pet_name.strip():
        owner.add_pet(Pet(new_pet_name.strip(), new_pet_species, age=int(new_pet_age)))
    else:
        st.warning("Please enter a pet name.")

pets = owner.get_pets()
if pets:
    st.write("Current pets: " + ", ".join(p.name for p in pets))
    rcol1, rcol2 = st.columns([3, 1])
    with rcol1:
        remove_pet_index = st.selectbox(
            "Remove a pet?",
            range(len(pets)),
            format_func=lambda i: pets[i].name,
            key="remove_pet_select",
        )
    with rcol2:
        if st.button("Remove pet"):
            # Owner.remove_pet() detaches the pet (and its tasks along with it).
            owner.remove_pet(pets[remove_pet_index])
            st.rerun()
else:
    st.info("No pets yet. Add one above.")

st.markdown("### Tasks")
if not pets:
    st.caption("Add a pet first, then you can add tasks to it.")
else:
    # Choose which pet the task belongs to (by index, in case names repeat).
    pet_index = st.selectbox(
        "Add task to which pet?",
        range(len(pets)),
        format_func=lambda i: pets[i].name,
    )
    selected_pet = pets[pet_index]

    # A form so pressing Enter submits, and clear_on_submit empties the fields after.
    with st.form("add_task_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            task_title = st.text_input("Task title", value="")
        with col2:
            duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
        with col3:
            priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

        col4, col5 = st.columns(2)
        with col4:
            # The time picker is always shown but only applied when ticked
            # (a form can't reveal it conditionally before submit).
            use_time = st.checkbox("Set a preferred time?")
            picked = st.time_input("Preferred time", value=time(8, 0))
        with col5:
            recurring = st.selectbox("Repeats", ["none", "daily", "weekly"])

        add_task_clicked = st.form_submit_button("Add task")

    if add_task_clicked:
        # Pet.add_task() adds the task to the selected pet.
        if task_title.strip():
            selected_pet.add_task(
                Task(
                    name=task_title.strip(),
                    duration=int(duration),
                    priority=PRIORITY_MAP[priority],
                    preferred_time=picked.strftime("%H:%M") if use_time else None,
                    recurring=None if recurring == "none" else recurring,
                )
            )
        else:
            st.warning("Please enter a task title.")

    # Filter controls for the task list, powered by Scheduler.filter_tasks().
    has_any_tasks = any(p.get_tasks() for p in pets)
    if has_any_tasks:
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            pet_filter = st.selectbox(
                "Show tasks for", ["All pets"] + [p.name for p in pets], key="pet_filter"
            )
        with fcol2:
            status_filter = st.selectbox(
                "Status", ["All", "Pending", "Completed"], key="status_filter"
            )
        # Translate the UI choices into filter_tasks() arguments (None = no filter).
        complete_arg = None if status_filter == "All" else status_filter == "Completed"
        pet_arg = None if pet_filter == "All pets" else pet_filter
        filtered = Scheduler(owner).filter_tasks(complete=complete_arg, pet_name=pet_arg)
        # filter_tasks() returns Task objects; pair each with its pet for display/removal.
        all_tasks = [(t.pet, t) for t in filtered]
    else:
        all_tasks = []

    if all_tasks:
        st.write("Current tasks:")
        st.table(
            [
                {
                    "pet": p.name,
                    "title": t.name,
                    "duration_minutes": t.duration,
                    "priority": t.priority_label(),
                    "time": t.preferred_time or "—",
                    "repeats": t.recurring or "—",
                    "done": "✓" if t.complete else "",
                }
                for p, t in all_tasks
            ]
        )

        tcol1, tcol2 = st.columns([3, 1])
        with tcol1:
            remove_task_index = st.selectbox(
                "Remove a task?",
                range(len(all_tasks)),
                format_func=lambda i: f"{all_tasks[i][0].name} — {all_tasks[i][1].name}",
                key="remove_task_select",
            )
        with tcol2:
            if st.button("Remove task"):
                # Pet.remove_task() removes the task from its pet.
                task_pet, task = all_tasks[remove_task_index]
                task_pet.remove_task(task)
                st.rerun()

        # Let the user check off tasks that still need completing.
        pending = [i for i, (_, t) in enumerate(all_tasks) if not t.complete]
        if pending:
            ccol1, ccol2 = st.columns([3, 1])
            with ccol1:
                complete_index = st.selectbox(
                    "Mark a task complete?",
                    pending,
                    format_func=lambda i: f"{all_tasks[i][0].name} — {all_tasks[i][1].name}",
                    key="complete_task_select",
                )
            with ccol2:
                if st.button("Mark complete"):
                    # Task.mark_complete() flips the task's complete flag.
                    all_tasks[complete_index][1].mark_complete()
                    st.rerun()
    elif has_any_tasks:
        st.info("No tasks match the current filter.")
    else:
        st.info("No tasks yet. Add one above.")

st.divider()

st.subheader("Build Schedule")
st.caption("Runs the scheduler across all pets' tasks under the owner's time budget.")

if st.button("Generate schedule"):
    if not any(p.get_tasks() for p in owner.get_pets()):
        st.info("Add at least one task before generating a schedule.")
    else:
        # Build a scheduler from the persistent owner, run the algorithm,
        # and show the human-readable plan.
        scheduler = Scheduler(owner)

        # Warn about tasks that want the same time slot before showing the plan.
        conflicts = scheduler.detect_conflicts()
        if conflicts:
            st.warning("Time-slot conflicts (overlapping times):")
            for first, second in conflicts:
                st.write(
                    f"- {first.name} ({first.preferred_time}) overlaps "
                    f"{second.name} ({second.preferred_time})"
                )

        scheduler.generate_plan()
        st.text(scheduler.explain_plan())
