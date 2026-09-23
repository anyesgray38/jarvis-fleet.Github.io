# Execution

Execution is closed-loop, not blind automation.

Before action:
- verify target
- verify scope
- choose minimal effective action

After action:
- inspect result
- compare against expectation
- continue, retry, or recover

For commands, preserve useful output and exit status.
For GUI actions, verify visible/application state.
For repository changes, inspect diff/status and run relevant tests.
