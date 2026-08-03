#!/usr/bin/env bash
# qa/endurance/2026-08-03-drift-screen/status-check-8080.sh
#
# Standing status check for the 24 h 20m drift-screen run armed 2026-08-03
# 17:13:26Z. Adapted from qa/endurance/status-check.sh, which was written for the
# multi-day 8080-vs-8081-vs-WSJT-X run and is kept intact for that case.
#
# Three changes from the parent script, each for a reason:
#
#  1. 8081 dropped entirely — only the 8080 / FT-991A instance is under test.
#
#  2. WAV and cycle-archive lookups are SCOPED to the live "cycle-audio/" dir.
#     The parent used `find <capture> -iname "*.wav" -path "*cycle-audio*"` over
#     the whole tree. This run preserved the previous session's data in
#     _pre-run-20260803/, which contains its own cycle-audio/ — so the parent
#     would have counted 89 stale WAVs alongside the live ones. Same for
#     cycle-archive.csv, where `find | head -1` picked the right file only by
#     traversal order. Both are now addressed by exact path.
#
#  3. The WSJT-X reference leg is pinned to the FT-991A INSTANCE's own data dir
#     (see WSJTX_DIR below), and is checked for STALENESS before being used as a
#     denominator. Four WSJT-X data directories exist on this machine and three
#     of them are frozen corpora; the parent script's default pointed at one of
#     them. A reference that is running but not decoding — or simply the wrong
#     directory — would otherwise produce a flattering "vs WSJTX" ratio against
#     a dead denominator. If the last decode is older than the freshness window,
#     the comparison cells read STALE and no ratio is printed.
#
#     The gate earned its keep immediately: on first run it correctly refused to
#     divide by the default instance's 25-hour-old corpus. That was a wrong-path
#     error on my part, not a run failure, but the failure it prevented was real.
#
# Elapsed wall-clock is shown against the 14.0 h ROW 1 VOID threshold from
# qa/endurance/2026-08-03-drift-screen/drift_screen.py. NOTE: wall clock is NOT
# the decisive epoch — ROW 1 tests the longest *uninterrupted* epoch, which only
# drift_screen.py can compute. This line is an early-warning indicator, not a
# verdict, and no verdict is issued by this script.
#
# Usage:   bash qa/endurance/2026-08-03-drift-screen/status-check-8080.sh
# Overrides:
#   CAPTURE_8080_DIR=... WSJTX_DIR=... RUN_START=2026-08-03T17:13:26Z bash ...
#
# Deliberately NOT `set -e` — a monitoring script must survive a missing file or
# an empty log and still print what it can.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PARENT_DIR="$(dirname "$REPO_ROOT")"

CAPTURE_8080_DIR="${CAPTURE_8080_DIR:-$PARENT_DIR/OpenWSFZ-8080-capture}"

# The reference leg is the WSJT-X instance fed by the FT-991A — the SAME radio as
# the 8080 chain, per the antenna-split arrangement. This is a multi-instance
# WSJT-X setup (--rig-name), so each instance has its OWN data directory. Naming
# the exact one matters more than it looks:
#
#   WSJT-X                  <- default instance, frozen since 2026-08-02 15:52Z
#   WSJT-X - FT991A         <- THE REFERENCE LEG. Live.
#   WSJT-X - FT991A-Copy    <- decoy, frozen since 2026-08-02 22:07Z
#   WSJT-X - SDRUno         <- the other radio, frozen since 2026-08-02 21:36Z
#
# Three of the four are stale corpora that would silently become a wrong
# denominator. Do NOT glob "WSJT-X - FT991A*" — it matches the -Copy decoy too.
# Set this by exact path, and let the staleness gate below catch a mistake.
WSJTX_DIR="${WSJTX_DIR:-/c/Users/Frank/AppData/Local/WSJT-X - FT991A}"
RUN_START="${RUN_START:-2026-08-03T17:13:26Z}"

# Freshness window for the WSJT-X reference leg, in seconds. 30 min = the same
# window as the Decodes/30min column, so a reference that cannot populate that
# column is by definition too stale to be its denominator.
WSJTX_FRESH_SECS="${WSJTX_FRESH_SECS:-1800}"

# ROW 1 VOID threshold from drift_screen.py, in hours.
VOID_THRESHOLD_HOURS=14.0

# Live archive paths — scoped, not searched (see header note 2).
CYCLE_AUDIO_DIR="$CAPTURE_8080_DIR/cycle-audio"
CYCLE_CSV="$CYCLE_AUDIO_DIR/cycle-archive.csv"

NOW_EPOCH=$(date -u +%s)
echo "=== Status check (8080 drift-screen run): $(date -u +"%Y-%m-%dT%H:%M:%SZ") ==="

# --- Elapsed wall clock since the run was armed -----------------------------
START_EPOCH=$(date -u --date="$RUN_START" +%s 2>/dev/null)
if [ -n "$START_EPOCH" ]; then
    ELAPSED=$((NOW_EPOCH - START_EPOCH))
    printf "Armed %s | elapsed %dh %02dm (wall clock; ROW 1 VOID if longest uninterrupted epoch < %sh)\n" \
        "$RUN_START" $((ELAPSED / 3600)) $(((ELAPSED % 3600) / 60)) "$VOID_THRESHOLD_HOURS"
fi

# --- Resolve the current log: latest by filename-embedded startup timestamp,
#     NOT by mtime (mtime races on a same-second fresh start).
LOG_8080="$(ls "$CAPTURE_8080_DIR"/logs/openswfz-*.log 2>/dev/null | sort | tail -1)"

# --- Current band, from the most recent archived cycle's dial_mhz.
mhz_to_band() {
    case "$1" in
        1.8*|1.9*)      echo "160m ($1)" ;;
        3.5*|3.7*|3.8*) echo "80m ($1)" ;;
        7.0*|7.1*)      echo "40m ($1)" ;;
        10.1*)          echo "30m ($1)" ;;
        14.0*)          echo "20m ($1)" ;;
        18.1*)          echo "17m ($1)" ;;
        21.0*)          echo "15m ($1)" ;;
        24.9*)          echo "12m ($1)" ;;
        28.0*)          echo "10m ($1)" ;;
        "")             echo "?" ;;
        *)              echo "$1" ;;
    esac
}
BAND_8080="$(mhz_to_band "$(tail -1 "$CYCLE_CSV" 2>/dev/null | awk -F',' '{print $5}')")"
BAND_WSJTX="$(mhz_to_band "$(tail -1 "$WSJTX_DIR/ALL.TXT" 2>/dev/null | awk '{print $2}')")"

# --- Counts. WAVs scoped to the live cycle-audio dir only.
WAV_8080=$(find "$CYCLE_AUDIO_DIR" -iname "*.wav" 2>/dev/null | wc -l | tr -d ' ')
WAV_WSJTX=$(find "$WSJTX_DIR/save" -iname "*.wav" 2>/dev/null | wc -l | tr -d ' ')

TXT_8080="$CAPTURE_8080_DIR/ALL.TXT"
TXT_WSJTX="$WSJTX_DIR/ALL.TXT"
line_count() { local n; n=$(wc -l < "$1" 2>/dev/null | tr -d ' '); echo "${n:-0}"; }
LINES_8080=$(line_count "$TXT_8080")
LINES_WSJTX=$(line_count "$TXT_WSJTX")

# --- WSJT-X staleness gate. Age of its newest decode line, from the file's own
#     leading YYMMDD_HHMMSS field — not mtime, which a mere file touch would reset.
WSJTX_LAST_TS="$(tail -1 "$TXT_WSJTX" 2>/dev/null | awk '{print $1}')"
WSJTX_STALE=1
WSJTX_AGE_TXT="no decodes on file"
if [[ "$WSJTX_LAST_TS" =~ ^([0-9]{6})_([0-9]{6})$ ]]; then
    d="${BASH_REMATCH[1]}"; t="${BASH_REMATCH[2]}"
    iso="20${d:0:2}-${d:2:2}-${d:4:2}T${t:0:2}:${t:2:2}:${t:4:2}Z"
    last_epoch=$(date -u --date="$iso" +%s 2>/dev/null)
    if [ -n "$last_epoch" ]; then
        age=$((NOW_EPOCH - last_epoch))
        WSJTX_AGE_TXT="$(printf "%dh %02dm ago (last decode %s)" $((age / 3600)) $(((age % 3600) / 60)) "$iso")"
        [ "$age" -le "$WSJTX_FRESH_SECS" ] && WSJTX_STALE=0
    fi
fi

pct() { awk -v a="$1" -v b="$2" 'BEGIN { if (b+0==0) print "n/a"; else printf "%.1f%%", (a/b*100) }'; }

# --- Decodes in the last 30 minutes (leading YYMMDD_HHMMSS field of ALL.TXT).
T30=$(date -u --date="-30 minutes" +%y%m%d_%H%M%S)
d30() { local n; n=$(awk -v t="$T30" '$1 >= t' "$1" 2>/dev/null | wc -l | tr -d ' '); echo "${n:-0}"; }
D30_8080=$(d30 "$TXT_8080")
D30_WSJTX=$(d30 "$TXT_WSJTX")

if [ "$WSJTX_STALE" -eq 1 ]; then
    CELL_VS="n/a"
    CELL_D30="$D30_8080"
    CELL_WSJTX_TXT="$LINES_WSJTX (STALE)"
    CELL_WSJTX_D30="STALE"
else
    CELL_VS="$(pct "$LINES_8080" "$LINES_WSJTX")"
    CELL_D30="$D30_8080 ($(pct "$D30_8080" "$D30_WSJTX"))"
    CELL_WSJTX_TXT="$LINES_WSJTX"
    CELL_WSJTX_D30="$D30_WSJTX"
fi

# --- 0-dec/20: zeros among the last 20 "decode(s) found" lines in the current log.
ZERO_8080="n/a"
if [ -n "$LOG_8080" ]; then
    ZERO_8080=$(grep -oP "\d+(?= decode\(s\) found)" "$LOG_8080" 2>/dev/null | tail -20 | grep -c "^0$")
fi

# --- Box-drawing table renderer (unchanged from the parent script).
render_table() {
    local -a rows=("$@")
    local -a widths=()
    local row cell i n

    IFS='|' read -ra _first <<< "${rows[0]}"
    n=${#_first[@]}
    for ((i = 0; i < n; i++)); do widths[i]=0; done

    for row in "${rows[@]}"; do
        IFS='|' read -ra cells <<< "$row"
        for ((i = 0; i < n; i++)); do
            cell="${cells[i]}"
            (( ${#cell} > widths[i] )) && widths[i]=${#cell}
        done
    done

    local top="┌" mid="├" bot="└" seg
    for ((i = 0; i < n; i++)); do
        seg=$(printf '─%.0s' $(seq 1 $((widths[i] + 2))))
        top+="$seg"; mid+="$seg"; bot+="$seg"
        if (( i < n - 1 )); then top+="┬"; mid+="┼"; bot+="┴"; else top+="┐"; mid+="┤"; bot+="┘"; fi
    done

    print_row() {
        IFS='|' read -ra cells <<< "$1"
        local line="│" j
        for ((j = 0; j < n; j++)); do
            printf -v padded " %-*s " "${widths[j]}" "${cells[j]}"
            line+="${padded}│"
        done
        echo "$line"
    }

    echo "$top"
    print_row "${rows[0]}"
    echo "$mid"
    for ((i = 1; i < ${#rows[@]}; i++)); do print_row "${rows[i]}"; done
    echo "$bot"
}

echo
render_table \
    "Source|Band|WAVs|ALL.TXT|vs WSJTX|Decodes/30min|0-dec/20" \
    "WSJT-X|$BAND_WSJTX|$WAV_WSJTX|$CELL_WSJTX_TXT|-|$CELL_WSJTX_D30|-" \
    "8080|$BAND_8080|$WAV_8080|$LINES_8080|$CELL_VS|$CELL_D30|$ZERO_8080/20"

# --- Archiving liveness: age of the newest live WAV.
NEWEST_WAV="$(ls -t "$CYCLE_AUDIO_DIR"/*.wav 2>/dev/null | head -1)"
if [ -n "$NEWEST_WAV" ]; then
    wav_age=$((NOW_EPOCH - $(stat -c %Y "$NEWEST_WAV" 2>/dev/null || echo "$NOW_EPOCH")))
    echo
    echo "Newest archived WAV: ${wav_age}s ago ($(basename "$NEWEST_WAV"))"
fi

# --- Silent checks: only surface if nonzero.
ERR_8080=$(grep -c "\[ERR\]\|\[FTL\]" "$LOG_8080" 2>/dev/null); ERR_8080=${ERR_8080:-0}
# Restart counting is scoped to restarts AT OR AFTER the run start. The log is
# append-only across sessions, so an unscoped count includes both a 2026-08-02
# restart from the previous session and the 17:10:09Z arming artefact from this
# one (a supervisor armed before the daemon had a log to watch — it is a
# watchdog, not a launcher). Neither is a failure of this run, and a permanently
# lit flag is a flag nobody reads. Pre-run restarts are reported separately, once.
RESTART_LOG="$CAPTURE_8080_DIR/restart-supervisor.log"
RESTART_ALL=$(grep -c "restarting" "$RESTART_LOG" 2>/dev/null); RESTART_ALL=${RESTART_ALL:-0}
RESTART_8080=$(awk -v s="$RUN_START" '/restarting/ && $1 >= s' "$RESTART_LOG" 2>/dev/null | wc -l | tr -d ' ')
RESTART_8080=${RESTART_8080:-0}
RESTART_PRE=$((RESTART_ALL - RESTART_8080))

FLAGS=0
if [ "${ERR_8080:-0}" -ne 0 ] 2>/dev/null; then
    echo; echo "!! 8080 current log has $ERR_8080 [ERR]/[FTL] line(s): $LOG_8080"; FLAGS=1
fi
if [ "${RESTART_8080:-0}" -ne 0 ] 2>/dev/null; then
    echo; echo "!! $RESTART_8080 supervisor restart(s) SINCE RUN START -- contiguity is broken,"
    echo "   the decisive epoch is now shorter than wall clock: $RESTART_LOG"
    FLAGS=1
fi
if [ "$WSJTX_STALE" -eq 1 ]; then
    echo; echo "!! WSJT-X reference leg is STALE: $WSJTX_AGE_TXT"
    echo "   The secondary (D-001 same-family) question cannot be answered while this holds."
    echo "   The primary drift screen is UNAFFECTED — it reads only the 8080 cycle archive."
    FLAGS=1
fi
if [ "$FLAGS" -eq 0 ]; then
    echo; echo "No [ERR]/[FTL] lines, no in-run restarts, reference leg fresh."
fi
if [ "${RESTART_PRE:-0}" -gt 0 ] 2>/dev/null; then
    echo "   (note: $RESTART_PRE restart(s) in the log pre-date this run -- not counted)"
fi

echo
echo "Current log:   $LOG_8080"
echo "Live archive:  $CYCLE_AUDIO_DIR  (excludes _pre-run-20260803/)"
