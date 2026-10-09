"""Voice: get narration for a spec, three ways.

  elevenlabs  the ElevenLabs text-to-speech API (set the ELEVENLABS_API_KEY environment variable; your key is never stored)
  local       the operating system's own voice (Windows SAPI, macOS `say`, Linux `espeak-ng`/`espeak`): free, offline, plainer
  file        your own recording: a single audio file, aligned to the script automatically

Narration is generated one scene at a time and joined with a short gap. That gives exact scene timing (no guessing) and a
sidecar `<audio>.timing.json` with every scene's start and end plus estimated word times inside it. `render` uses the
sidecar automatically, so cuts, captions and word-synced animations land on the speech.

Spec:  "voice": {"provider": "elevenlabs", "voice_id": "...", "model": "eleven_multilingual_v2", "gap": 0.28}
       "voiceover": "assets/voice_<hash>.mp3"   (written for you by `motionspec voice spec.json --write`)
"""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

PROVIDERS = ("elevenlabs", "local", "file")
API = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128"


class VoiceError(RuntimeError):
    """Narration could not be produced; the message says what to do."""


def scene_lines(spec):
    """[(scene_index, text)] for every scene that has `say`."""
    return [(i, str(sc["say"]).strip()) for i, sc in enumerate(spec.get("scenes", [])) if str(sc.get("say", "")).strip()]


def fingerprint(provider, cfg, lines):
    raw = json.dumps([provider, cfg.get("voice_id"), cfg.get("model"), cfg.get("gap", 0.28), lines], sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


def _elevenlabs(text, cfg):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key: raise VoiceError("ELEVENLABS_API_KEY is not set. Create a key at elevenlabs.io (Profile, API keys) and set it in your environment, "
                                 "or use --provider local, or record your own voice and use --provider file.")
    if not cfg.get("voice_id"): raise VoiceError('voice.voice_id is required for ElevenLabs. Pick one in the ElevenLabs voice library and add it: "voice": {"voice_id": "..."}')
    body = json.dumps({"text": text, "model_id": cfg.get("model", "eleven_multilingual_v2")}).encode()
    req = urllib.request.Request(API.format(voice=cfg["voice_id"]), data=body, headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r: return r.read()
    except urllib.error.HTTPError as e:
        hint = {401: "the API key was rejected", 402: "the account is out of credits", 404: "that voice_id was not found for this account", 422: "the request was invalid"}.get(e.code, "")
        raise VoiceError(f"ElevenLabs returned HTTP {e.code}" + (f" ({hint})" if hint else "")) from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise VoiceError(f"could not reach ElevenLabs: {getattr(e, 'reason', e)}") from None


def _local(text, out_wav):
    system = platform.system()
    if system == "Windows":
        script = ("Add-Type -AssemblyName System.Speech; $v = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "$v.SetOutputToWaveFile($env:MS_OUT); $v.Speak($env:MS_TEXT); $v.Dispose()")
        cmd, env = ["powershell", "-NoProfile", "-NonInteractive", "-Command", script], {**os.environ, "MS_OUT": out_wav, "MS_TEXT": text}
    elif system == "Darwin":
        cmd, env = ["say", "-o", out_wav.replace(".wav", ".aiff"), text], os.environ
    else:
        exe = shutil.which("espeak-ng") or shutil.which("espeak")
        if not exe: raise VoiceError("no local voice found. Install espeak-ng (sudo apt install espeak-ng), or use --provider elevenlabs or file.")
        cmd, env = [exe, "-w", out_wav, text], os.environ
    try: subprocess.run(cmd, check=True, capture_output=True, timeout=120, env=env)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise VoiceError(f"the local voice failed ({type(e).__name__}); it may be blocked on this machine. Use --provider elevenlabs or file.") from None
    aiff = out_wav.replace(".wav", ".aiff")
    return aiff if system == "Darwin" else out_wav


def _duration(path):
    from .audio import probe_duration
    return probe_duration(path)


def _silence(path, seconds):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(seconds), "-q:a", "4", path], check=True)


def _words_in(text, t0, t1):
    import re
    ws = text.split(); wt = [len(re.sub(r"\W", "", w)) + 2.0 for w in ws]; tot = sum(wt) or 1.0; out, t = [], t0
    for w, k in zip(ws, wt):
        d = (t1 - t0) * k / tot; out.append({"word": w, "t0": round(t, 3), "t1": round(t + d, 3)}); t += d
    return out


def synthesize(spec, out_dir, provider=None, force=False, file=None):
    """Create narration for `spec`. Returns (audio_path, timing_dict). Cached by content, so unchanged text costs nothing."""
    cfg = dict(spec.get("voice") or {}); provider = provider or cfg.get("provider", "elevenlabs")
    if provider not in PROVIDERS: raise VoiceError(f"unknown voice provider '{provider}'. Choose from {PROVIDERS}.")
    lines = scene_lines(spec)
    if not lines: raise VoiceError('no scene has a "say" line. Write the narration in each scene\'s "say" first.')
    if provider == "file":
        src = file or cfg.get("file")
        if not src or not os.path.isfile(src): raise VoiceError('give your recording with --file path/to/recording.mp3 (or voice.file in the spec).')
        return src, None                                   # one recording: aligned from the audio itself at render time
    os.makedirs(out_dir, exist_ok=True); fp = fingerprint(provider, cfg, lines)
    out_audio = os.path.join(out_dir, f"voice_{fp}.mp3"); out_json = out_audio + ".timing.json"
    if os.path.exists(out_audio) and os.path.exists(out_json) and not force:
        return out_audio, json.load(open(out_json, encoding="utf-8"))
    gap = float(cfg.get("gap", 0.28)); tmp = tempfile.mkdtemp(prefix="motionspec_voice_"); parts, timing, t = [], [], 0.0
    gap_file = os.path.join(tmp, "gap.mp3"); _silence(gap_file, gap)
    for n, (i, text) in enumerate(lines):
        clip = os.path.join(tmp, f"s{n}.mp3")
        if provider == "elevenlabs": open(clip, "wb").write(_elevenlabs(text, cfg))
        else:
            raw = _local(text, os.path.join(tmp, f"s{n}.wav")); subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-ar", "44100", "-ac", "1", clip], check=True)
        d = _duration(clip); parts += [clip, gap_file]
        timing.append({"scene": i, "text": text, "t0": round(t, 3), "t1": round(t + d, 3), "words": _words_in(text, t, t + d)}); t += d + gap
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for p in parts[:-1]: f.write("file '" + p.replace("\\", "/") + "'\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-ar", "44100", "-q:a", "3", out_audio], check=True)
    data = {"provider": provider, "total": round(t - gap, 3), "scenes": timing}
    json.dump(data, open(out_json, "w", encoding="utf-8"), indent=1)
    return out_audio, data
