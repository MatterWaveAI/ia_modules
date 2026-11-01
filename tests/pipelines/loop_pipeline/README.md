# Iterative Content Generation Pipeline (loops)

A loop in the flow graph: a draft is reviewed, and a rejected draft goes back for another
revision until it is approved or `max_revisions` is reached.

```
topic, max_revisions
   ↓
draft_content      → draft, revision_count
   ↓
review_content     → approved, feedback, quality_score
   ├─ approved == false → draft_content     (revise; revision_count + 1)
   └─ approved == true  → publish_content   → published_url, final_draft
```

The two paths out of `review_content` are `expression` conditions on
`review_content.approved`. The runner's loop detector sees the cycle and the
loop executor caps iterations; the steps themselves stop asking for revisions once
`revision_count` reaches `max_revisions`.

## Run it

```bash
echo '{"topic": "vector databases", "max_revisions": 3}' > input.json
ia-modules run tests/pipelines/loop_pipeline/pipeline.json --working-dir . --input input.json
```

Both parameters are required: `topic` (string) and `max_revisions` (integer).

No model is involved: the steps simulate drafting and reviewing, with the review
improving its score each revision, so the example runs anywhere.

## Output

`draft` and `revision_count` from the last revision, `approved`, `feedback` and
`quality_score` from the final review, and `published_url` and `final_draft` from
publishing. `ia-modules validate` warns that the flow contains a cycle; for this
pipeline that is the point.
