# Spec reference

Generated from the scene registry (`motionspec scenes`). `*` = required.

Top-level keys: spec_version, id, kind (reel|ad|explainer|demo|general), format, theme, look (clean|soft|film|neon|cinema), motion (none|calm|lively), backdrop (orbs|grid|dots|none), transition (fade|cut|push|wipe|zoom), scenes, captions [{t0,t1,text}], captions_style (plain|karaoke), say_captions, voice {provider, voice_id, model, gap}, voiceover, music ("auto" default | "off" | path | {mood, db}), beat_sync, align, autotime, cues [{t, sound}], sfx_density (rich|light|off), punch, facts, approved_facts, policy, blur, post {bloom, halation, tone, grain, aberration}, fps, sfx.

Every scene also accepts: `camera` {zoom:[from,to], pan:[dx0,dy0,dx1,dy1], drift:0..1}, `transition`, `backdrop`, `invert` (palette flip), `say`, `bg`, `gradient`.

```

bars: Horizontal bars. items: {label, value, suffix?, decimals?, accent?}.
    source: str
    title: str
    items*: list
    note: str

bullets: List that builds item by item, each on the spoken word when narrated. Items are strings or {head, sub}.
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

flow: A process as nodes joined by arrows, with packets travelling through it. `nodes`: list of labels (each appears on its spoken word). Use for pipelines, workflows, 'then it does X'.
    title: str
    nodes*: list
    loop: bool
    caption: str

grid: Proportion grid: `total` dots, `hit` of them light up. Shows 'x of y' at a glance.
    source: str
    total*: int
    hit*: int
    title: str
    label_total: str
    label_hit: str
    cols: int
    style: str

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

stat: One big number that counts up (or rolls like an odometer: style odometer), with a title above and a caption below. `when`: a spoken word to start on.
    source: str
    value*: int/float
    prefix: str
    suffix: str
    decimals: int
    commas: bool
    title: str
    caption: str
    size: int/float
    style: str
    when: str

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

title: Big headline. `style`: lines (default) | words (each word stretches and springs in) | letters (kinetic). *asterisks* colour words with the accent; `underline` draws a line under it. With narration each word appears when it is spoken.
    lines*: list
    accent: int
    size: int/float
    kicker: str
    subtitle: str
    step: int/float
    style: str
    underline: bool

Common to all scenes: type, dur, bg, gradient, say, id, camera, transition, comment, backdrop, invert   (* = required)

```
