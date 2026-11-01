# branching_tree_pipeline

Step fixtures for the branching-tree pattern, not a runnable example: there is no
`pipeline.json` here. `steps/test_steps.py` holds a root step and two terminal branches
(`RootStep`, `AlwaysBranchStep`, `ConditionalBranchStep`) for assembling a pipeline in code
where one step fans out to an unconditional branch and a conditional one.
