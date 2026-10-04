#!/usr/bin/env python
"""Assemble the OneAquaHealth demo video from the produced assets.

Inputs (all already produced by this folder's scripts):
  * video/_build/wavs/scene-NN.wav      per-scene narration (tts.py)
  * video/scene-cards/*.svg             title / boundary / end cards
  * video/diagrams/*.svg                two-streams / convergence
  * video/_build/panels/*.png           real-data panels (panels.py)
  * video/_capture/*.png                real live-UI captures

Output:
  * video/oneaquahealth-demo.mp4        captioned, narrated, 3-5 min
  * video/narration.srt                 retimed to the finished video

Nothing writes to the FHIR server. ffmpeg + rsvg-convert only.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
V = REPO / "video"
BUILD = V / "_build"
STILLS = BUILD / "stills"
CLIPS = BUILD / "clips"
WAVS = BUILD / "wavs"
STILLS.mkdir(parents=True, exist_ok=True)
CLIPS.mkdir(parents=True, exist_ok=True)

W, H, FPS = 1920, 1080, 30
MAX_SECONDS = 300.0
OUT = V / "oneaquahealth-demo.mp4"
SRT = V / "narration.srt"
NARR = V / "narration.md"


def sh(cmd: list[str], quiet: bool = True) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"cmd failed: {' '.join(cmd)}\n{r.stderr[-2000:]}")
    if not quiet and r.stderr:
        print(r.stderr[-500:])


def dur(path: Path) -> float:
    out = subprocess.run(["ffmpeg", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def rsvg(svg: Path, out: Path, w: int = W, h: int = H) -> None:
    sh(["rsvg-convert", "-w", str(w), "-h", str(h), "-o", str(out), str(svg)])


# --------------------------------------------------------------------------- #
# 1. render SVG stills to PNG
def render_stills() -> dict[str, Path]:
    stills: dict[str, Path] = {}

    def add(key: str, src: Path, w: int = W, h: int = H) -> None:
        dst = STILLS / f"{key}.png"
        rsvg(src, dst, w, h)
        stills[key] = dst

    add("title", V / "scene-cards" / "00-title.svg")
    add("boundary", V / "scene-cards" / "04-boundary.svg")
    add("end", V / "scene-cards" / "09-end.svg")
    add("two-streams", V / "diagrams" / "two-streams.svg")
    add("convergence", V / "diagrams" / "convergence.svg")

    # data panels: always re-render from the freshly generated SVGs
    for key, svg_name in [
        ("p-endpoints", "s05-endpoints"),
        ("p-trend", "s06a-trend"),
        ("p-profile", "s06b-profile"),
        ("p-offset", "s07-offset"),
        ("p-ingest", "s08-ingest"),
    ]:
        src = BUILD / "panels" / f"{svg_name}.svg"
        dst = STILLS / f"{key}.png"
        rsvg(src, dst)
        stills[key] = dst

    # live captures are already PNGs
    for key, p in [
        ("s01-overview", V / "_capture" / "s01-overview.png"),
        ("s02-context", V / "_capture" / "s02-context.png"),
        ("s03-evidence", V / "_capture" / "s03-evidence.png"),
        ("s03b-drawer", V / "_capture" / "s03b-evidence-drawer.png"),
        ("g02-stages", V / "_capture" / "g02-stages.png"),
    ]:
        if p.exists():
            stills[key] = p
        else:
            print("WARN missing still:", p)
    return stills


# --------------------------------------------------------------------------- #
# shot plan: scene -> [(still_key, weight, effect)]
#   effect: "hold" = static (readable UI/charts); "zoom" = slow push-in
PLAN: dict[int, list[tuple[str, float, str]]] = {
    0: [("title", 1.0, "zoom")],
    1: [("s01-overview", 1.0, "hold")],
    2: [("s02-context", 0.60, "hold"), ("two-streams", 0.40, "zoom")],
    3: [("s03b-drawer", 1.0, "hold")],
    4: [("boundary", 1.0, "hold")],
    5: [("p-endpoints", 1.0, "hold")],
    6: [("p-trend", 0.55, "hold"), ("p-profile", 0.45, "hold")],
    7: [("p-offset", 1.0, "hold")],
    8: [("p-ingest", 1.0, "hold")],
    9: [("convergence", 0.30, "zoom"), ("s01-overview", 0.36, "hold"), ("end", 0.34, "zoom")],
}


def make_clip(png: Path, out: Path, seconds: float, effect: str) -> None:
    if effect == "zoom":
        rate = 0.10 / max(seconds * FPS, 1)
        vf = (
            f"scale={int(W*1.25)}:{int(H*1.25)},"
            f"zoompan=z='min(1.0+on*{rate:.6f},1.10)':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},"
            f"format=yuv420p"
        )
    else:
        vf = f"scale={W}:{H},setsar=1,fps={FPS},format=yuv420p"
    sh([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-framerate", str(FPS), "-i", str(png),
        "-t", f"{seconds:.3f}", "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
        str(out),
    ])


# --------------------------------------------------------------------------- #
# retime narration.srt to the finished video's real scene boundaries
def retime_srt(scene_spans: list[tuple[int, float, float]]) -> None:
    md = NARR.read_text(encoding="utf-8")
    headers = list(re.finditer(r"^## Scene (\d+) — .*? · (\d+:\d+)–(\d+:\d+)\s*$", md, re.M))
    bodies: dict[int, str] = {}
    for i, m in enumerate(headers):
        stop = headers[i + 1].start() if i + 1 < len(headers) else len(md)
        body = md[m.end():stop].split("### Word count")[0]
        spoken = " ".join(
            ln.strip().strip("*") for ln in body.splitlines()
            if ln.strip().startswith("**") and ln.strip().endswith("**")
        )
        bodies[int(m.group(1))] = re.sub(r"\s+", " ", spoken).strip()

    LIM = 72

    def split_long(p: str) -> list[str]:
        if len(p) <= LIM:
            return [p]
        pieces = re.split(r"(?<=[;:,—])\s+", p)
        out, cur = [], ""
        for s in pieces:
            if not cur:
                cur = s
            elif len(cur) + 1 + len(s) <= LIM:
                cur += " " + s
            else:
                out.append(cur); cur = s
        if cur:
            out.append(cur)
        final = []
        for x in out:
            if len(x) <= LIM:
                final.append(x)
            else:
                w, c = x.split(), ""
                for tok in w:
                    if not c:
                        c = tok
                    elif len(c) + 1 + len(tok) <= LIM:
                        c += " " + tok
                    else:
                        final.append(c); c = tok
                if c:
                    final.append(c)
        return final

    def clauses(text: str) -> list[str]:
        parts = re.split(r"(?<=[.?!])\s+", text)
        out: list[str] = []
        for p in parts:
            out.extend(split_long(p))
        merged: list[str] = []
        for p in out:
            if merged and len(merged[-1]) < 24 and len(merged[-1]) + 1 + len(p) <= LIM:
                merged[-1] += " " + p
            else:
                merged.append(p)
        final: list[str] = []
        for m in merged:
            final.extend(split_long(m) if len(m) > LIM else [m])
        return final

    def wrap2(s: str) -> list[str]:
        words, lines, cur = s.split(), [], ""
        for w in words:
            if len(cur) + (1 if cur else 0) + len(w) <= 42:
                cur = (cur + " " + w).strip()
            else:
                lines.append(cur); cur = w
        if cur:
            lines.append(cur)
        return lines

    def ts(t: float) -> str:
        t = max(0.0, t); h = int(t // 3600); m = int((t % 3600) // 60); s = t % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")

    cues: list[tuple[float, float, str]] = []
    for no, a, b in scene_spans:
        spoken = bodies.get(no, "")
        if not spoken:
            continue
        cl = clauses(spoken)
        total = sum(len(c) for c in cl) or 1
        t = a
        for c in cl:
            d = (b - a) * (len(c) / total)
            cues.append((t, t + d, c)); t += d

    # fidelity check
    norm = lambda s: re.findall(r"[a-z0-9']+", re.sub(r"\s+", " ", s).lower())
    assert norm(" ".join(c[2] for c in cues)) == norm(" ".join(bodies.values())), "SRT fidelity fail"

    out = []
    for i, (s, e, txt) in enumerate(cues, 1):
        lines = wrap2(txt)
        assert len(lines) <= 2 and all(len(l) <= 42 for l in lines), f"bad wrap cue {i}: {lines}"
        out.append(f"{i}\n{ts(s)} --> {ts(max(s, e-0.04))}\n" + "\n".join(lines) + "\n")
    SRT.write_text("\n".join(out), encoding="utf-8")
    print(f"retimed {SRT.name}: {len(cues)} cues, ends {ts(cues[-1][1])}")


# --------------------------------------------------------------------------- #
def main() -> int:
    stills = render_stills()

    wavs = sorted(WAVS.glob("scene-*.wav"))
    if len(wavs) != 10:
        raise SystemExit(f"expected 10 scene wavs, found {len(wavs)}")

    # scene spans from the real narration durations
    spans: list[tuple[int, float, float]] = []
    t = 0.0
    for w in wavs:
        no = int(re.search(r"scene-(\d+)", w.name).group(1))
        d = dur(w)
        spans.append((no, t, t + d)); t += d
    print("scene spans:", [(n, round(a, 1), round(b, 1)) for n, a, b in spans])
    print(f"total narration: {t:.2f}s ({t/60:.2f} min)")
    if t > MAX_SECONDS:
        raise SystemExit("narration exceeds 5:00 ceiling")

    retime_srt(spans)

    # build clips
    video_parts: list[Path] = []
    for no, a, b in spans:
        shots = PLAN[no]
        wsum = sum(s[1] for s in shots)
        for idx, (key, weight, effect) in enumerate(shots):
            png = stills[key]
            seconds = (b - a) * (weight / wsum)
            clip = CLIPS / f"scene-{no:02d}-{idx}.mp4"
            make_clip(png, clip, seconds, effect)
            video_parts.append(clip)
    print(f"built {len(video_parts)} clips")

    # concat video
    vlist = CLIPS / "video.txt"
    vlist.write_text("".join(f"file '{p}'\n" for p in video_parts), encoding="utf-8")
    vtrack = CLIPS / "video-track.mp4"
    sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", str(vlist), "-c", "copy", str(vtrack)])

    # concat narration audio
    alist = WAVS / "audio.txt"
    alist.write_text("".join(f"file '{w}'\n" for w in wavs), encoding="utf-8")
    atrack = BUILD / "narration.wav"
    sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", str(alist), "-c", "copy", str(atrack)])
    print(f"narration track: {dur(atrack):.2f}s ({atrack})")

    # mux video + audio + burned-in subtitles
    srt_for_filter = (BUILD / "captions.srt").resolve()
    srt_for_filter.write_text(SRT.read_text(encoding="utf-8"), encoding="utf-8")
    vf = (
        f"subtitles='{srt_for_filter}':"
        "force_style='PlayResX=1920,PlayResY=1080,"
        "FontName=Liberation Sans,FontSize=38,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&HC0000000,BorderStyle=3,"
        "Outline=2,Shadow=0,MarginV=16,Alignment=2'"
    )
    sh(["ffmpeg", "-y", "-loglevel", "error",
        "-i", str(vtrack), "-i", str(atrack),
        "-vf", vf,
        "-map", "0:v:0", "-map", "1:a:0", "-shortest", "-t", f"{MAX_SECONDS:.0f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(OUT)])

    d = dur(OUT)
    print(f"FINAL: {OUT}  duration {d:.2f}s ({d/60:.3f} min)")
    if not (180 <= d <= MAX_SECONDS):
        raise SystemExit(f"duration {d:.1f}s outside 3:00-5:00 window")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
