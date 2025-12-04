"""Compatibility shim that preserves the historic GUI entry point.

This file provides two simple variables `USE_MOCK_API` and
`USE_MOCK_ASSISTANT` that you can edit before running the script.
If either variable is True the script will instantiate `TodoApp`
with the corresponding flags instead of parsing command-line args.
"""
from dsl_todolist.gui import main, TodoApp

# Edit these flags before running to switch modes without CLI args.
# - Set `USE_MOCK_API = True` to use the in-memory mock API.
# - Set `USE_MOCK_ASSISTANT = True` to use the rule-based mock assistant.
USE_MOCK_API = False
USE_MOCK_ASSISTANT = False


if __name__ == "__main__":
    # If either flag is set, construct the app programmatically so
    # the user can toggle behavior by editing this file.
    if USE_MOCK_API or USE_MOCK_ASSISTANT:
        app = TodoApp(use_mock_api=USE_MOCK_API, use_mock_assistant=USE_MOCK_ASSISTANT)
        app.run()
    else:
        # Fall back to the normal main() which parses CLI args.
        main()
