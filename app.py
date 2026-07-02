import streamlit as st

from pawpal_system import Owner, Pet, Task, Scheduler

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

# Map the UI's priority words to the integer scale Task expects.
PRIORITY_MAP = {"low": 1, "medium": 2, "high": 3}

# Persist a single Owner (and its Pet) in the session "vault" so they are NOT
# recreated empty on every rerun. The constructors run once per session.
if "owner" not in st.session_state:
    st.session_state.owner = Owner("Jordan", available_minutes=120)
if "pet" not in st.session_state:
    st.session_state.pet = Pet("Mochi", "dog", age=3)
    st.session_state.owner.add_pet(st.session_state.pet)

# Grab the persistent instances for the rest of the script to use.
owner = st.session_state.owner
pet = st.session_state.pet

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

st.subheader("Quick Demo Inputs (UI only)")
owner_name = st.text_input("Owner name", value=owner.name)
pet_name = st.text_input("Pet name", value=pet.name)
species = st.selectbox("Species", ["dog", "cat", "other"])

# Sync the current input values onto the persistent objects each rerun.
owner.name = owner_name
pet.name = pet_name
pet.species = species

st.markdown("### Tasks")
st.caption("Add a few tasks. In your final version, these should feed into your scheduler.")

col1, col2, col3 = st.columns(3)
with col1:
    task_title = st.text_input("Task title", value="Morning walk")
with col2:
    duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
with col3:
    priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)

if st.button("Add task"):
    # Pet.add_task() is the method that handles adding a task to the pet.
    pet.add_task(
        Task(
            name=task_title,
            duration=int(duration),
            priority=PRIORITY_MAP[priority],
        )
    )

# Read the current tasks back from the persistent pet to show the update.
tasks = pet.get_tasks()
if tasks:
    st.write("Current tasks:")
    st.table(
        [
            {
                "title": t.name,
                "duration_minutes": t.duration,
                "priority": t.priority_label(),
            }
            for t in tasks
        ]
    )
else:
    st.info("No tasks yet. Add one above.")

st.divider()

st.subheader("Build Schedule")
st.caption("This button should call your scheduling logic once you implement it.")

if st.button("Generate schedule"):
    if not pet.get_tasks():
        st.info("Add at least one task before generating a schedule.")
    else:
        # Build a scheduler from the persistent owner, run the algorithm,
        # and show the human-readable plan.
        scheduler = Scheduler(owner)
        scheduler.generate_plan()
        st.text(scheduler.explain_plan())
