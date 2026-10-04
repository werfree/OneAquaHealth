#!/usr/bin/env bash
# =============================================================================
# assemble.sh — OneAquaHealth demo video assembly (template)
# -----------------------------------------------------------------------------
# Concatenates the title card, the screen recordings, the diagram/overlay clips,
# the end card, and the narration audio, then burns in narration.srt.
#
# EDIT ONLY THE "INPUTS" BLOCK BELOW. Everything after it is generic.
#
# Requires: ffmpeg (with libx264 + subtitles/fontconfig). SVG->PNG rendering
# requires rsvg-convert (librsvg) OR inkscape OR ImageMagick `convert`.
#
# NOTE: ffmpeg was NOT installed on the authoring machine, so this script is a
# verified-lint template, not an executed render. Run `bash video/assemble.sh`
# on a machine with ffmpeg. The duration guard below hard-caps the output at 5:00.
# =============================================================================
set -euo pipefail

# ------------------------------- CONFIG --------------------------------------
FPS="${FPS:-30}"
WIDTH="${WIDTH:-1920}"
HEIGHT="${HEIGHT:-1080}"
MAX_SECONDS="${MAX_SECONDS:-300}"          # hard ceiling 5:00
VIDEO_NAME="${VIDEO_NAME:-oneaquahealth-demo}"   # output basename
SRT="${SRT:-video/narration.srt}"
AUDIO="${AUDIO:-video/narration.wav}"      # narration audio (produced separately)
WORK="${WORK:-video/_build}"

# ------------------------------- INPUTS --------------------------------------
# Set each path to the operator's recorded clip. Leave "" to skip that segment.
# Order here IS the playback order. Use your scene recordings from shot-list.md.
TITLE_CARD="video/scene-cards/00-title.svg"      # still -> rendered to a clip
CLIP_SCENE1="video/clips/01-scope-mode.mp4"      # live dashboard recording
CLIP_SCENE2="video/clips/02-context.mp4"         # live dashboard recording
CLIP_SCENE3="video/clips/03-evidence.mp4"        # live dashboard recording
OVERLAY_BOUNDARY="video/scene-cards/04-boundary.svg"   # lower-third still
CLIP_SCENE5="video/clips/05-studio-fallback.mp4" # terminal fallback recording
CLIP_SCENE6="video/clips/06-analyses.mp4"        # charts / profile recording
CLIP_SCENE7="video/clips/07-offset.mp4"          # offset + caveat recording
CLIP_SCENE8="video/clips/08-ingestion.mp4"       # terminal pipeline recording
CLIP_SCENE9A="video/diagrams/convergence.svg"    # convergence still
CLIP_SCENE9B="video/clips/09-return-live.mp4"    # live return recording
END_CARD="video/scene-cards/09-end.svg"          # still -> clip

# How long each still card is held on screen (seconds).
DUR_TITLE="${DUR_TITLE:-10}"
DUR_BOUNDARY="${DUR_BOUNDARY:-10}"
DUR_CONVERGENCE="${DUR_CONVERGENCE:-12}"
DUR_END="${DUR_END:-10}"

# ------------------------------- HELPERS -------------------------------------
log() { printf '\033[1;34m[assemble]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[assemble]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m[assemble] %s\033[0m\n' "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || die "missing required tool: $1"; }

# duration in seconds (0 if unavailable). Uses ffmpeg only — ffprobe may be
# absent even when ffmpeg is present (as on the authoring machine).
duration_of() {
  if command -v ffprobe >/dev/null 2>&1; then
    ffprobe -v error -show_entries format=duration -of csv=p=0 "$1" 2>/dev/null || echo 0
  else
    ffmpeg -i "$1" 2>&1 | awk -F'[ :]' '/Duration:/ {print $4*3600 + $5*60 + $6; exit}' || echo 0
  fi
}

# Render an SVG still to a full-frame H.264 clip of given duration.
# Usage: svg_to_clip <in.svg> <out.mp4> <seconds> [out_w] [out_h]
svg_to_clip() {
  local svg="$1" out="$2" secs="$3" w="${4:-$WIDTH}" h="${5:-$HEIGHT}"
  [[ -f "$svg" ]] || die "missing asset: $svg"
  local png="$WORK/$(basename "${svg%.svg}").png"
  mkdir -p "$WORK"

  if command -v rsvg-convert >/dev/null 2>&1; then
    rsvg-convert -w "$w" -h "$h" -o "$png" "$svg"
  elif command -v inkscape >/dev/null 2>&1; then
    inkscape "$svg" --export-type=png --export-filename="$png" -w "$w" -h "$h" >/dev/null 2>&1
  elif command -v convert >/dev/null 2>&1; then
    convert -background none -density 192 "$svg" -resize "${w}x${h}!" "$png"
  else
    die "no SVG renderer found (install librsvg / inkscape / imagemagick)"
  fi

  ffmpeg -y -loglevel error -loop 1 -framerate "$FPS" -i "$png" \
    -t "$secs" -r "$FPS" \
    -vf "scale=${w}:${h}:force_original_aspect_ratio=decrease,pad=${w}:${h}:(ow-iw)/2:(oh-ih)/2:color=0xF7F5F0,format=yuv420p" \
    -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p "$out"
  log "rendered $svg -> $out (${secs}s)"
}

# Normalise any input clip to a common WxH/FPS/SAR so concat is seamless.
# Usage: normalise <in> <out>
normalise() {
  local in="$1" out="$2"
  [[ -f "$in" ]] || die "missing clip: $in"
  ffmpeg -y -loglevel error -i "$in" \
    -vf "scale=${WIDTH}:${HEIGHT}:force_original_aspect_ratio=decrease,pad=${WIDTH}:${HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0xF7F5F0,setsar=1,fps=${FPS},format=yuv420p" \
    -an -c:v libx264 -preset medium -crf 18 "$out"
  log "normalised $in -> $out"
}

# ------------------------------- ENVIRONMENT ---------------------------------
need ffmpeg
mkdir -p "$WORK" video/clips

(( MAX_SECONDS > 300 )) && MAX_SECONDS=300   # never allow a >5:00 ceiling

# ------------------------------- BUILD SEGMENTS ------------------------------
segments=()
add_segment() {  # add_segment <path> <label>
  [[ -n "${1:-}" && -f "$1" ]] || { warn "skip (absent): $1"; return; }
  segments+=("$1")
}

# 1) still cards -> clips
svg_to_clip "$TITLE_CARD"      "$WORK/00-title.mp4"      "$DUR_TITLE"
svg_to_clip "$OVERLAY_BOUNDARY" "$WORK/04-boundary.mp4"  "$DUR_BOUNDARY"
svg_to_clip "$CLIP_SCENE9A"    "$WORK/09-convergence.mp4" "$DUR_CONVERGENCE"
svg_to_clip "$END_CARD"        "$WORK/09-end.mp4"        "$DUR_END"

# 2) normalise live recordings
for pair in \
  "CLIP_SCENE1:$WORK/01.mp4" \
  "CLIP_SCENE2:$WORK/02.mp4" \
  "CLIP_SCENE3:$WORK/03.mp4" \
  "CLIP_SCENE5:$WORK/05.mp4" \
  "CLIP_SCENE6:$WORK/06.mp4" \
  "CLIP_SCENE7:$WORK/07.mp4" \
  "CLIP_SCENE8:$WORK/08.mp4" \
  "CLIP_SCENE9B:$WORK/09b.mp4" ; do
  src_var="${pair%%:*}"; dst="${pair#*:}"
  src="${!src_var}"
  if [[ -n "$src" && -f "$src" ]]; then normalise "$src" "$dst"; fi
done

# 3) assemble in order
add_segment "$WORK/00-title.mp4"      "scene0"
add_segment "$WORK/01.mp4"            "scene1"
add_segment "$WORK/02.mp4"            "scene2"
add_segment "$WORK/03.mp4"            "scene3"
add_segment "$WORK/04-boundary.mp4"   "scene4"
add_segment "$WORK/05.mp4"            "scene5"
add_segment "$WORK/06.mp4"            "scene6"
add_segment "$WORK/07.mp4"            "scene7"
add_segment "$WORK/08.mp4"            "scene8"
add_segment "$WORK/09-convergence.mp4" "scene9a"
add_segment "$WORK/09b.mp4"           "scene9b"
add_segment "$WORK/09-end.mp4"        "scene9c"

[[ ${#segments[@]} -gt 0 ]] || die "no segments to assemble (fill in the INPUTS block)"

# concat list
list="$WORK/concat.txt"
: > "$list"
for s in "${segments[@]}"; do printf "file '%s'\n" "$(cd "$(dirname "$s")" && pwd)/$(basename "$s")" >> "$list"; done

log "concatenating ${#segments[@]} segments"
ffmpeg -y -loglevel error -f concat -safe 0 -i "$list" -c copy "$WORK/video-track.mp4"

# ------------------------------- AUDIO + SUBTITLES ---------------------------
[[ -f "$AUDIO" ]] && [[ -f "$SRT" ]] || warn "audio or SRT missing — will produce a silent, subtitle-free cut"

# ------------------------------- FINAL MUX + GUARD ---------------------------
OUT="video/${VIDEO_NAME}.mp4"
vlen="$(duration_of "$WORK/video-track.mp4")"
log "video track duration: ${vlen}s"

ffmpeg_args=(-y -loglevel error -i "$WORK/video-track.mp4")

if [[ -f "$AUDIO" ]]; then
  ffmpeg_args+=(-i "$AUDIO")
fi

vf="subtitles=${SRT}:force_style='FontName=Inter,FontSize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,BorderStyle=3,Outline=2,Shadow=0,MarginV=48'"
ffmpeg_args+=(-vf "$vf")

if [[ -f "$AUDIO" ]]; then
  # -shortest trims to the shorter of A/V; -t enforces the hard ceiling.
  ffmpeg_args+=(-map 0:v:0 -map 1:a:0 -shortest -t "$MAX_SECONDS" \
    -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
    -c:a aac -b:a 192k -movflags +faststart "$OUT")
else
  ffmpeg_args+=(-t "$MAX_SECONDS" \
    -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p \
    -movflags +faststart "$OUT")
fi

log "muxing final cut -> $OUT"
ffmpeg "${ffmpeg_args[@]}"

# ------------------------------- DURATION GUARD ------------------------------
final="$(duration_of "$OUT")"
log "final duration: ${final}s (ceiling ${MAX_SECONDS}s)"
if awk "BEGIN{exit !($final > $MAX_SECONDS)}"; then
  die "output exceeds ${MAX_SECONDS}s — trim a segment and re-run"
fi
if awk "BEGIN{exit !($final < 180)}"; then
  warn "output is under 3:00 — the brief asks for 3:00–5:00; add narration/holds"
fi

log "done: $OUT"
log "check:  ffmpeg -i $OUT 2>&1 | grep Duration"
