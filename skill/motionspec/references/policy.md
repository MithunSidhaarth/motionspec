# Policy files

`policy.json` turns a project's content rules into checks (`motionspec lint spec.json --policy policy.json`, or `"policy": "policy.json"` in the spec):

```json
{
  "banned": ["guaranteed", "best in the world"],
  "required_any": ["illustrative", "source:"],
  "facts_file": "facts.json",
  "numbers_free_below": 10,
  "kinds": {"reel": [15, 45], "ad": [6, 30]},
  "max_caption_words": 9,
  "hook_max_seconds": 3.5,
  "require_last": "endcard"
}
```

Banned phrases are whole-word and case-insensitive across every on-screen string and caption. With `facts_file`, every number on screen must appear in the facts the spec cites (`"facts": ["id1"]`). Extend the rules per project; never loosen them to get one video through.
