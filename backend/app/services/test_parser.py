from app.services.task_parser import parse_task_text


test_cases = [
    # "1. Team meeting tomorrow at 2:30 PM",

    # "2. Submit the presentation on Friday at 5 PM",
    # "3. Call mom tonight at 9 PM",

    # "4. Doctor appointment on Monday at 11 AM",

    # "5. Gym every Tuesday and Thursday at 7 AM",

    # "6. Go for a walk tomorrow morning",

    # "7. Dinner with friends tomorrow evening",

    "8. Watch a movie tonight",

    "9. Visit the bank on Saturday"

    # "10. Grocery shopping this Sunday afternoon"
]


for i, text in enumerate(test_cases, start=1):
    print("\n" + "=" * 70)
    print(f"TEST {i}")
    print(f"INPUT: {text}")
    print("=" * 70)

    try:
        result = parse_task_text(text)

        for key, value in result.items():
            print(f"{key}: {value}")

    except Exception as e:
        print("ERROR:", e)