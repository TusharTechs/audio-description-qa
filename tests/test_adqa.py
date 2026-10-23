import json
import os
import subprocess
import sys
import numpy as np

from adqa import check, check_bundle, worth_checking, describe_for_prompt
from adqa.audio_events import SR, attack_ms, settle, shape_of
from adqa.stability import classify, compare


EXAMPLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "examples")


def test_preflight_valid_bundle():
    valid_dir = os.path.join(EXAMPLES_DIR, "valid-bundle")
    res = check_bundle(valid_dir)
    assert res["passed"] is True
    assert res["cues"] == 4
    assert res["failures"] == []
    assert res["notes"] == []


def test_preflight_broken_bundle_catches_all_faults():
    broken_dir = os.path.join(EXAMPLES_DIR, "broken-bundle")
    gaps_path = os.path.join(broken_dir, "gaps.json")
    fails, notes = check(broken_dir, gaps_path=gaps_path)
    joined_fails = "\n".join(fails)
    joined_notes = "\n".join(notes)

    # 1. Truncated end hole with usable gap room
    assert "with no description at the end" in joined_fails
    # 2. Missing audio file
    assert "has no audio file (desc-99.*)" in joined_fails
    # 3. Dialogue overlap
    assert "talks over dialogue" in joined_fails
    # 4. Camera language
    assert "uses camera language" in joined_fails
    # 5. Repeated indefinite noun phrase introduction
    assert 'introduces "A woman" again' in joined_notes
    # 6. Repeated sign-language wrapper
    assert "sign-language wrapper" in joined_notes


def test_preflight_cli_exit_codes():
    valid_dir = os.path.join(EXAMPLES_DIR, "valid-bundle")
    broken_dir = os.path.join(EXAMPLES_DIR, "broken-bundle")

    ok = subprocess.run(
        [sys.executable, "-m", "adqa.preflight", valid_dir],
        capture_output=True,
        text=True,
    )
    assert ok.returncode == 0
    assert "passed" in ok.stdout

    bad = subprocess.run(
        [sys.executable, "-m", "adqa.preflight", broken_dir,
         "--gaps", os.path.join(broken_dir, "gaps.json")],
        capture_output=True,
        text=True,
    )
    assert bad.returncode == 1
    assert "FAIL" in bad.stdout


def test_audio_events_hit_vs_swell_and_gain_invariance():
    # Build a 4-second synthetic signal with a quiet floor (-40 dBFS)
    rng = np.random.default_rng(42)
    dur_s = 4.0
    t = np.linspace(0, dur_s, int(SR * dur_s), endpoint=False)
    floor = 10 ** (-40.0 / 20.0) * rng.standard_normal(t.size)

    # 1. Sharp percussive hit at t=1.0s (instant attack, 80ms exponential decay)
    hit = floor.copy()
    idx = t >= 1.0
    env_hit = np.exp(-(t[idx] - 1.0) / 0.08)
    hit[idx] += 0.5 * env_hit * np.sin(2 * np.pi * 220 * (t[idx] - 1.0))

    a_ms, _ab1, _ab2, verdict = shape_of(hit, 1.0, -40.0)
    assert a_ms is not None and a_ms < 30.0
    assert verdict is True

    # Uniform -6 dB attenuation must produce the exact same attack & verdict
    atten = 10 ** (-6.0 / 20.0)
    a_ms_q, _q1, _q2, verdict_q = shape_of(hit * atten, 1.0, -46.0)
    assert a_ms_q == a_ms
    assert verdict_q is True

    # 2. Slow musical swell peaking around t=1.15s (250ms linear ramp, sustained tail)
    swell = floor.copy()
    ramp = np.clip((t - 0.85) / 0.28, 0.0, 1.0)
    swell += 0.5 * ramp * np.sin(2 * np.pi * 220 * t)
    a_swell, _s1, _s2, verdict_swell = shape_of(swell, 1.15, -40.0)
    assert a_swell is not None and a_swell > 120.0
    assert verdict_swell is False


def test_worth_checking_and_describe_for_prompt():
    onsets = [
        {"t": 2.0, "rise_db": 9.5, "transient": True},
        {"t": 4.0, "rise_db": 14.0, "transient": False},   # swell -> ignored
        {"t": 6.5, "rise_db": 12.2, "transient": True},
        {"t": 8.0, "rise_db": 11.0, "transient": False, "unsure": True},
    ]
    top = worth_checking(onsets, 2)
    assert [o["t"] for o in top] == [2.0, 6.5]

    info = {
        "window": [0.0, 10.0],
        "onsets": onsets,
        "level_db": -22.0,
        "character": "2 distinct sound event(s)",
    }
    prompt_note = describe_for_prompt(
        info,
        dialogue="",
        checked=[{"t": 6.5, "visible_cause": False, "what": "metallic clang"}],
    )
    assert "NOTHING VISIBLE" in prompt_note
    assert "6.5s" in prompt_note


def test_stability_compare():
    ref = [
        {"t": 10.00, "transient": True},
        {"t": 25.40, "transient": False},
    ]
    got = [
        {"t": 10.02, "transient": True},
        {"t": 25.41, "transient": True},   # flipped swell -> hit
    ]
    flips, gone, extra, matched = compare(ref, got)
    assert matched == 2
    assert gone == 0
    assert extra == 0
    assert flips == [(25.4, "swell", "hit")]
