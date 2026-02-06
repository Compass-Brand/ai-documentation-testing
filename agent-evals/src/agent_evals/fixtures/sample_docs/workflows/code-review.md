# Code Review Workflow

A structured process for reviewing pull requests in the DataForge project.

## Before Reviewing

1. Pull the branch locally and run the test suite
2. Read the PR description and linked issue
3. Check the diff size -- request a split if over 400 lines changed

## Review Checklist

### Correctness

- [ ] Logic matches the described behavior
- [ ] Edge cases are handled (empty input, nulls, large data)
- [ ] Error messages are clear and actionable

### Code Quality

- [ ] Functions are under 30 lines where practical
- [ ] No duplicated logic that should be extracted
- [ ] Type hints present on public API functions
- [ ] Docstrings follow Google style format

### Testing

- [ ] New code has corresponding test cases
- [ ] Tests cover both happy path and error cases
- [ ] No flaky tests introduced (no `time.sleep`, no network calls)

### Performance

- [ ] No unnecessary database queries in loops
- [ ] Large collections use generators or streaming
- [ ] Batch operations used where appropriate

## Providing Feedback

Use conventional comment prefixes:

```
nit: minor style suggestion, non-blocking
suggestion: improvement idea, discuss
issue: must be addressed before merge
question: clarification needed
```

See [Contributing](../repo/CONTRIBUTING.md) for branch and PR conventions.
