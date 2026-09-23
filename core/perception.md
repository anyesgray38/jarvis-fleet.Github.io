# Perception

AEGIS treats the computer as an observable environment.

Inputs may include:
- screen state
- application state
- terminal output
- filesystem state
- repository state
- browser state
- logs
- APIs
- test results

Interactive loop:
PERCEIVE → MODEL STATE → ACT → OBSERVE → UPDATE STATE.

Do not rely on stale coordinates, stale assumptions, or a fixed sequence when the environment can change.
