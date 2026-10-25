# Simple HITL Getting Started Pipeline

A minimal 3-step pipeline demonstrating Human-in-the-Loop functionality.

## Pipeline Flow

```
Step 1: Prepare Data
    ↓
Step 2: Human Review (HITL - Pipeline Pauses Here)
    ↓
Step 3: Finalize
```

## Steps

1. **Prepare Data** - Creates sample data for review
2. **Human Review** - Pauses execution and waits for human approval/rejection
3. **Finalize** - Completes the pipeline based on human decision

## Testing

When executed:
1. Pipeline runs Step 1 automatically
2. Pipeline pauses at Step 2 and shows a review form
3. Human approves or rejects via the UI
4. Pipeline resumes and runs Step 3

## Expected Input

```json
{
  "initial_data": "any value"
}
```

## HITL UI Fields

The human review step presents:
- **Decision**: Radio buttons (Approve/Reject)
- **Comments**: Optional text field for feedback

## Example Usage

Navigate to the Pipeline Editor, load "Simple HITL Getting Started", and click Run.
A yellow banner will appear when the pipeline pauses for human input.
