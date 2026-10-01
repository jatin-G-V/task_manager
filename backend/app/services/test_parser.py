import json

from app.services.agent_tools import add_task


TEST_USER_ID = "4335d308-386c-4a6d-9cdc-2da38cb11c8f"


TEST_CASES = [
    # "Buy milk tomorrow after work.",

    # "Prepare the client presentation for Friday. I need to finish the slides and review the numbers before sending it.",

    # "I have a meeting with Amit tomorrow at 3 PM. It should take about 45 minutes.",

    # "Watch Interstellar tonight and relax for a while.",

    # "Read the new project documentation for 40 minutes tonight.",

    # "Fix the login bug before the client demo tomorrow. It may take a couple of hours.",

    # "Submit the final report Friday at 5 PM. Make sure all the numbers have been checked before submitting.",

    # "I have a meeting with the client Friday at 5 PM to discuss the new requirements.",

    # "Finish the presentation in the next 2 hours.",

    # "Call Amit in 2 hours to discuss the deployment issue.",

    # "Go to the gym every day.",

    # "Go to the gym every day until December 31.",

    # "Study every Monday at 7 PM for my upcoming exam.",

    # "Submit the weekly report every Friday by 5 PM.",

    # "Plan my Mumbai trip sometime next month. I need to check hotels, transport and places to visit.",

    "Finish the monthly expense report by the end of this month.",

    "Call the plumber tomorrow; it should only take around 10 minutes.",

    "Prepare the quarterly client presentation. It involves collecting the results, creating the slides and reviewing everything before the meeting.",

    "Buy groceries sometime this week, preferably before the weekend.",

    "Urgent: send the invoice to the client today before 9 PM.",

    "Hello, how are you?",

    "Mumbai trip.",

    "Play football with the team tomorrow evening.",

    "Pay the electricity bill by next Friday and keep the receipt after payment.",

    "Go to the gym every Monday until November 30 and spend around one hour there.",
]


for i, raw_text in enumerate(TEST_CASES, 1):
    print(f"\n{'=' * 70}")
    print(f"T{i:02d}")
    print(f"{'=' * 70}")
    print(f"Input: {raw_text}")

    try:
        result = add_task(
            TEST_USER_ID,
            {
                "raw_text": raw_text
            }
        )

        print("\nRESULT: CREATED")
        print(json.dumps(result, indent=2, default=str))

    except Exception as e:
        print("\nRESULT: FAILED")
        print(str(e))