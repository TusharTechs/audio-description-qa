# audio-description-qa

Quality checks for **machine-written audio description** — the spoken track
that describes what is happening on screen for blind and low vision viewers.

Generating description with a model is the easy part. Knowing whether what
came out is safe to put in front of someone who cannot check it against the
picture is the hard part, and that is what these four tools are for.

Every check here exists because a blind reviewer found the fault it now
catches. None of them were found by testing locally.

---

## Why this exists

If you generate audio description automatically, you will produce these four
failures. They are not hypothetical:

**A stretch of film with nothing said.** A limit intended to cap how many
descriptions were written instead truncated the timeline, so a three-minute
clip went silent after two. On a feature film it would have described the
first minute and said nothing for the remaining thirteen. A blind reviewer
found it in ten minutes; local testing never would have, because the test
clip was short enough to fit under the limit.

**Description spoken over the dialogue.** Or, more subtly, beginning a
seventh of a second after a line ends. The same reviewer needed three
viewings to notice the narrator say "hunter", because another voice started
before he had taken it in.

**A person who is not there.** A high shot looking down through rafters was
described as "someone watches her sleep". Nobody was watching. The system had
turned a camera position into a character, and a blind listener cannot check
an invented watcher against the picture — it becomes a fact they carry for
the rest of the film.

**An analysis that was never measuring what you thought.** Attenuating a film
by 3 dB changed five of its onset classifications, always in the same
direction. The cause was not the classifier: the audio loader was reading
16-bit and clipping every file, flattening the peaks the rule measured.

---

## The tools

### `preflight` — check a described bundle before anyone hears it

```bash
python -m adqa.preflight BUNDLE_DIR --gaps gaps.json
```

Non-zero exit if anything fails, so it can gate a deploy. It reports:

- a stretch longer than 45 s with nothing said — **judged against the
  speakable room actually inside it**, so a film that narrates continuously is
  not blamed for leaving nowhere to speak
- a cue whose audio file is missing, which plays as silence and is
  indistinguishable from nothing having happened
- description that overlaps dialogue, or crowds it on either side
- camera language: "from above", "past us", "we see". `off screen` and
  `out of shot` are deliberately **not** flagged, because naming the unseen
  source of a sound is the correct thing to say
- the same person introduced indefinitely twice

### `stability` — does the same film get the same answers twice?

```bash
python -m adqa.stability MEDIA --gaps gaps.json
```

Runs your audio analysis over the same media three ways — 3 dB down, 9 dB
down, and re-encoded — and reports what moved. Anything that flips under a
change the analysis is supposed to be blind to was not being decided by the
sound.

Only attenuates. Boosting is not a usable invariance test on material
mastered to full scale: the boost clips somewhere in the chain, and a clipped
signal is a different sound.

It also reports **which way** instability breaks, which matters more than how
often. A wrong label is a description that is slightly off. A missed sound is
silence, and silence is indistinguishable from nothing having happened.

### `shape_test` / `shape_score` — is the distinction audible at all?

```bash
python -m adqa.shape_test MEDIA --out testdir
python -m adqa.shape_score testdir --arrived 1,4,7 --built 2,3,5
```

Builds a blind listening test from any film. Clips are cut only where no
sound of the opposite class falls inside them, level-matched with a single
static gain so loudness cannot give the answer away, shuffled, with the key
written separately.

Three design decisions worth stealing:

- **It asks people to sort, not to detect.** A first version asked "did
  something arrive in this clip?" and got yes for all nine, because a primed
  listener hearing the loudest thing in a four-second window always says yes.
- **Some clips are played twice**, far apart, so the listener's own
  consistency is measured. A machine that changes its mind on 1% of calls is
  only unreliable if a person changes theirs less often, and nobody knows that
  number unless you measure it.
- **Clips the analysis could not call are included and not scored.** They get
  a free-text box asking what the listener would want said there, because
  hit-or-swell was never the question for those.

### `audio_events` — what did the viewer already hear?

```bash
python -m adqa.audio_events MEDIA --start 0 --end 6
```

Distinguishes a **hit** — something arrived — from a **swell**, the score
getting louder. Description should spend its words on what the soundtrack did
not already explain, and "the music got loud" is not an event.

The rule came from a blind reviewer and is worth reading even if you do not
use the code: *"a swell and a hit are different shapes, not different sizes.
Measure how fast the level got there rather than how far it got."* And then,
when that was not enough: measure the fall against **the level before the
onset**, not against the peak, because a hit does not decay into silence — it
decays into whatever is underneath it.

---

## Install

Python 3.10+, `numpy`, and `ffmpeg` on the path.

```bash
git clone https://github.com/TusharTechs/audio-description-qa
cd audio-description-qa
pip install -e .
```

## The bundle format

`preflight` reads a `timeline.json` describing what will be spoken and when.
See [`examples/timeline.example.json`](examples/timeline.example.json):

```json
{
  "media": "content.mp4",
  "cues": [
    { "t": 9.98, "text": "Inside a tent", "duration": 0.993, "pcm": "desc-01.pcm" }
  ]
}
```

`t` is when the line starts in seconds, `duration` how long the spoken audio
runs, `pcm` the audio file beside it (`.mp3` and `.wav` are also accepted).
The optional `--gaps` file supplies `speech_runs`, the intervals where the
film's own dialogue occurs, which is what the collision and coverage checks
are measured against.

## Where this came from

Extracted from [Sightline](https://github.com/TusharTechs/sightline), which
generates audio description for content that has none and speaks it on a Fire
TV, and released separately in September 2026 during the Build, Ship, Shape:
Amazon Developer Hackathon 2026. Nothing here is specific to that project or to
any device. It applies to any pipeline that writes description automatically.

[Three minutes of the parent project working](https://youtu.be/vqJsFDnj7ko), if
you want to see what these checks are protecting.

**On the checks themselves.** The descriptions in the parent project are
written by a vision language model. These checks exist because a model will
produce a line that reads perfectly and is false, and the person who most needs
the description is the one person who cannot catch it. Two blind reviewers
found the faults; the checks are what stops them coming back.

## Portability

Pure Python, 3.10 or newer, with no platform specific calls. Runs on macOS,
Linux and Windows. `audio_events` and `stability` shell out to `ffmpeg`, which
needs to be on your `PATH`; the other tools need only the standard library and
`numpy`.

## Licence

MIT. See [LICENSE](LICENSE).
