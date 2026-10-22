
import json
import os

from app.services import task_service
from app.services.agent_tools import add_tasks, _pending


# Use a dedicated Supabase test user's auth.users UUID.
# You can override this through PIPELINE_TEST_USER_ID.
TEST_USER_ID = os.getenv(
    "PIPELINE_TEST_USER_ID",
    "4335d308-386c-4a6d-9cdc-2da38cb11c8f",
)

# Set KEEP_PIPELINE_TEST_TASKS=1 if you intentionally want to
# retain successfully created test tasks in Supabase.
KEEP_TEST_TASKS = os.getenv("KEEP_PIPELINE_TEST_TASKS", "0") == "1"


TEST_CASES = [
    "Finish the monthly expense report by the end of this month.",
    "Call the plumber tomorrow; it should only take around 10 minutes.",
    (
        "Prepare the quarterly client presentation. It involves "
        "collecting the results, creating the slides and reviewing "
        "everything before the meeting."
    ),
    "Buy groceries sometime this week, preferably before the weekend.",
    "Urgent: send the invoice to the client today before 9 PM.",
    "Hello, how are you?",
    "Mumbai trip.",
    "Play football with the team tomorrow evening.",
    "Pay the electricity bill by next Friday and keep the receipt after payment.",
    "Go to the gym every Monday until November 30 and spend around one hour there.",
]


def main():
    created_ids = []

    print("=" * 75)
    print("END-TO-END TASK PIPELINE TEST")
    print("=" * 75)
    print("Pipeline: Groq parser -> add_tasks -> dedupe/clash checks -> Supabase")
    print(f"Test user: {TEST_USER_ID}")
    print(f"Test cases: {len(TEST_CASES)}")

    try:
        for index, raw_text in enumerate(TEST_CASES, 1):
            print(f"\n{'=' * 75}")
            print(f"T{index:02d}")
            print(f"{'=' * 75}")
            print(f"Input: {raw_text}")

            try:
                # Execute the real task-creation pipeline.
                result = add_tasks(
                    TEST_USER_ID,
                    {"items": [raw_text]},
                )

                # Track only records created by THIS invocation.
                for task in result.get("created", []):
                    task_id = task.get("id")
                    if task_id:
                        created_ids.append(task_id)

                print(f"\nSTATUS: {result.get('status')}")
                print("REPLY:")
                print(result.get("reply", ""))
                print("\nRESULT:")
                print(json.dumps(result, indent=2, default=str))

            except Exception as exc:
                print("\nRESULT: FAILED")
                print(f"{type(exc).__name__}: {exc}")

    finally:
        # Pending decisions are in-memory state, not database records.
        # This script should be run against a dedicated test user.
        _pending.pop(TEST_USER_ID, None)

        if KEEP_TEST_TASKS:
            print(
                "\nCleanup skipped because KEEP_PIPELINE_TEST_TASKS=1."
            )
        elif created_ids:
            try:
                deleted = task_service.delete_tasks(
                    TEST_USER_ID,
                    created_ids,
                )
                print(
                    f"\nCleanup: requested deletion of "
                    f"{len(created_ids)} test-created task(s); "
                    f"database returned {len(deleted or [])} deleted row(s)."
                )
            except Exception as exc:
                print(
                    "\nCLEANUP FAILED. Check Supabase for test-created "
                    f"task IDs: {created_ids}"
                )
                print(f"{type(exc).__name__}: {exc}")
        else:
            print("\nCleanup: no tasks were created by this run.")

    print("\nPipeline test run finished.")


if __name__ == "__main__":
    main()
