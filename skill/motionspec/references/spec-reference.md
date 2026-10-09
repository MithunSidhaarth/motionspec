# Spec reference

Generated from the scene registry (`motionspec scenes`). `*` = required.

Top-level keys: spec_version, id, kind (reel|ad|explainer|demo|general), format, theme, look (clean|soft|film|neon), motion (none|calm|lively), backdrop (orbs|grid|dots|none), transition (fade|cut|push|wipe|zoom), scenes, captions [{t0,t1,text}], captions_style (plain|karaoke), voiceover, music ("auto" default | "off" | path | {mood, db}), align, autotime, cues [{t, sound}], facts, approved_facts, policy, blur, post {bloom, grain, aberration}, fps, sfx.

Every scene also accepts: `camera` {zoom:[from,to], pan:[dx0,dy0,dx1,dy1], drift:0..1}, `transition`, `backdrop`, `say`, `bg`, `gradient`.

```

bars: Horizontal bars. items: {label, value, suffix?, decimals?, accent?}.
    source: str
    title: str
    items*: list
    note: str

bullets: List that builds item by item. Items are strings or {head, sub}.
    title: str
    items*: list
    numbered: bool

chart: Animated line chart. series: [{label, values, accent?}], labels = x-axis labels.
    source: str
    title: str
    series*: list
    labels: list
    note: str
    zero: bool
    suffix: str

clip: Video clip (screen recording, b-roll), muted. Plays from `start`; `loop` repeats. Sound comes from the voiceover.
    src*: str
    start: int/float
    caption: str
    loop: bool
    fit: str

code: Typewriter code or terminal block. `lines`, characters/second `cps`, `highlight` line numbers (1-based).
    title: str
    lines*: list
    cps: int/float
    highlight: list

compare: Two cards side by side (stacked on tall formats): before/after, us/them. left/right: {title, items[]}.
    source: str
    title: str
    left*: dict
    right*: dict

device: Screenshot inside a browser window (`kind`: browser, default on wide) or phone (`kind`: phone, default on tall) frame, with a slow push-in.
    src*: str
    kind: str
    url: str
    caption: str
    zoom: int/float
    pan: list

endcard: End card: theme logo, brand name, tagline, optional pulsing button, url. Text defaults come from the theme.
    brand: str
    tagline: str
    url: str
    button: str
    ask: str
    loop: bool

grid: Proportion grid: `total` dots, `hit` of them light up. Shows 'x of y' at a glance.
    source: str
    total*: int
    hit*: int
    title: str
    label_total: str
    label_hit: str
    cols: int

image: Screenshot or photo with a slow zoom (Ken Burns). `pan` [x0,y0,x1,y1] in 0..1 moves the crop; `fit`: card (default) | full.
    src*: str
    caption: str
    zoom: int/float
    zoom_dur: int/float
    pan: list
    fit: str

note: Boxed callout for a caveat, definition or key line. `kicker`, `text`, `small`.
    kicker: str
    text*: str
    small: str

quote: Pull quote with attribution.
    text*: str
    who: str
    role: str

section: Chapter card: big number, title, optional subtitle.
    number: int/str
    title*: str
    subtitle: str

slam: Full-frame word slams, one per beat, on an inverted (accent) field. `words`: [str], `hold` seconds per word.
    words*: list
    invert: bool
    size: int/float
    hold: int/float

stat: One big number that counts up, with a title above and a caption below.
    source: str
    value*: int/float
    prefix: str
    suffix: str
    decimals: int
    commas: bool
    title: str
    caption: str
    size: int/float

steps: Numbered process. Same as bullets with numbers; `steps` are strings or {head, sub}.
    title: str
    steps*: list

strike: Myth vs fact: the wrong claim gets a pen strike drawn through it, then the correct line slams in below.
    wrong*: str
    right*: str
    kicker: str

timeline: Milestones along a line. events: {when, what}. Horizontal on wide formats, vertical on tall.
    source: str
    title: str
    events*: list

title: Big headline. `style`: lines (default) | words (each word springs in) | letters (kinetic). Use *asterisks* to colour a word with the accent.
    lines*: list
    accent: int
    size: int/float
    kicker: str
    subtitle: str
    step: int/float
    style: str

Common to all scenes: type, dur, bg, gradient, say, id, camera, transition, comment, backdrop   (* = required)

```
