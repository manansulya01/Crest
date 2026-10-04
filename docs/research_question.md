# Research question

Can an AI agent safely earn additional autonomous capabilities from
independently verified recoverability, and is the increase in Autonomous
Action Coverage (AAC) large enough to be practically useful while keeping
realized exposure within a hard bound?

Primary metric: `AAC(t)` — fraction of eligible action classes/instances the
agent may execute autonomously at time `t`.
Constraint: realized exposure <= `E_max`.
Key comparison: AAC(t) rise must not trade off the exposure bound.
