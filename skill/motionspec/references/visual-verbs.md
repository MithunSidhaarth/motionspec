# Visual verbs: show the idea, do not list it

A viewer remembers one picture per sentence. Before choosing a scene, ask what the sentence *does* and pick the matching verb.

| The sentence says... | Verb (scene) | Why it works |
|---|---|---|
| "Most people think X. Actually Y." | `strike` (pen strikes X, Y slams in) | contrast is felt, not read |
| "N out of M..." / scale / rarity | `grid` (`style: fall` makes the misses drop away) | the proportion is visible at a glance |
| a number that should land | `stat` with `style: odometer` and `when: "<spoken word>"` | the digits roll, then punch on the beat |
| a process: A then B then C | `flow` (packets travel the line) | order and direction are the message |
| "Here is what you type / it says" | `code` (typewriter, keys) | you watch it happen |
| a product, a screen | `device` (browser or phone frame, slow push) | proof, not a claim |
| before vs after, us vs them | `compare` (the left side dims as the right lands) | one side visibly wins |
| a trend over time | `chart` (line draws, end dot pops) | motion shows direction |
| milestones, a plan | `timeline` | sequence along a line |
| the single idea to remember | `slam` (one word per beat) or `title` with `style: words` and `*emphasis*` | typography as impact |
| a caveat, a promise, a twist | `note` with `invert: true` (the palette flips for one scene) | contrast marks the moment |
| the ask | `endcard` with a `button` | one clear action |

Rules of thumb
- Never use the same scene type twice in a row. `analyze` reports variety.
- Use `bullets`/`steps` when the content truly is a list, and only then.
- A scene that finishes building should end soon: hold time over about 1.2 s with nothing changing reads as dead air.
- With narration, give each item the word it is about (`"when"` on a stat, item heads that repeat the spoken word) so it appears as it is said.
