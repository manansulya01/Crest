# Customer Interview Guide

## Target participants

- AI application developers (building LLM-powered features).
- Platform/infrastructure engineers (operating LLM workloads).
- Engineering leads (managing AI budgets and reliability).
- Teams with production LLM workloads and meaningful inference spend.

## Interview format

- 30-45 minutes.
- Semi-structured.
- Focus on past behavior, not hypothetical enthusiasm.
- Record with permission.

## 15 non-leading interview questions

1. Tell me about the last time an AI workflow in your system produced an unexpected result or cost. What happened?
2. How did you discover the problem? How long did it take to notice?
3. What was the financial or operational impact?
4. What did you do to prevent it from happening again?
5. How do you currently track which AI calls belong to which feature, user, or workflow?
6. When a model returns invalid or unexpected structured output, what happens in your system?
7. How do you verify that an AI response is correct before acting on it?
8. What existing tools do you use for LLM cost tracking, budgeting, or observability?
9. What do those tools handle well? What do they handle poorly?
10. What do you still handle manually that you wish were automated?
11. Have you ever had a situation where an invalid AI output was silently treated as successful? What happened?
12. How do you set and enforce spending limits on AI usage today?
13. What would need to be true for you to add a new piece of infrastructure to your AI stack?
14. What would make you replace an existing tool rather than add a new one?
15. If you could change one thing about how your team manages AI costs and reliability, what would it be?

## Questions to AVOID

- "Would you use CREST?"
- "Do you think CREST is useful?"
- "Would you pay for this idea?"
- "How much would you pay for CREST?"
- "Do you need budget enforcement?"
- "Would verification be valuable?"

These questions invite hypothetical enthusiasm rather than revealing actual behavior.

## Interview evidence template

### Interview context
- Date:
- Participant role:
- Company size / stage:
- Production LLM usage: (yes/no, scale)
- Current tools:
- Interviewer:

### Actual problem examples
1. Problem:
   - Scenario:
   - Discovery method:
   - Impact:
   - Frequency:
   - Current workaround:

### Existing alternatives
- Tools used:
- What works:
- What doesn't:

### Unmet need
- Description:
- Evidence strength: (direct observation / reported behavior / inferred)

### Direct quotes (with permission)
- Quote:
- Context:

### Confidence assessment
- Problem is real: (High/Medium/Low)
- Problem is frequent: (High/Medium/Low)
- Problem is severe: (High/Medium/Low)
- Existing solutions are inadequate: (High/Medium/Low)
- Participant would act on a solution: (High/Medium/Low)

### Follow-up evidence required
- What additional data would strengthen this finding?
- What would change the conclusion?
