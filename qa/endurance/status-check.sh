#!/usr/bin/env bash
# qa/endurance/status-check.sh
#
# Standing status check for the multi-day 20m corpus-gathering run (8080 vs 8081
# vs WSJT-X). Produces the exact table format agreed in
# qa/cycleframer-alignment-replay/2026-08-01-2001-qa-context-clear-handoff-multiday-20m-live-run.md §2
# — written once here so it stops being re-derived by hand on every check.
#
# Usage:   bash qa/endurance/status-check.sh
# Override capture dirs if they ever move:
#   CAPTURE_8080_DIR=... CAPTURE_8081_DIR=... WSJTX_DIR=... bash qa/endurance/status-check.sh
#
# Deliberately NOT `set -e` — a monitoring script must survive a missing file or
# an empty log (early in a run, mid-restart, etc.) and still print what it can,
# rather than dying silently on the first hiccup.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PARENT_DIR="$(dirname "$REPO_ROOT")"

CAPTURE_8080_DIR="${CAPTURE_8080_DIR:-$PARENT_DIR/OpenWSFZ-8080-capture}"
CAPTURE_8081_DIR="${CAPTURE_8081_DIR:-$PARENT_DIR/OpenWSFZ-8081-capture}"
WSJTX_DIR="${WSJTX_DIR:-/c/Users/Frank/AppData/Local/WSJT-X}"

echo "=== Status check: $(date -u +"%Y-%m-%dT%H:%M:%SZ") ==="

# --- Resolve the *current* log file per instance: latest by the filename-embedded
#     startup timestamp (openswfz-YYYYMMDDTHHMMSSZ.log), NOT by mtime. mtime can
#     race on a same-second fresh start, and every capture dir carries stale
#     bundled logs from unrelated historical testing that a naive `ls -t` can pick up.
current_log() {
    ls "$1"/logs/openswfz-*.log 2>/dev/null | sort | tail -1
}
LOG_8080="$(current_log "$CAPTURE_8080_DIR")"
LOG_8081="$(current_log "$CAPTURE_8081_DIR")"

# --- Current band, from the most recent archived cycle's dial_mhz (self-updating;
#     8081 is free-hopping so this must be read live, not assumed).
band_label() {
    local csv
    csv="$(find "$1" -iname "cycle-archive.csv" 2>/dev/null | head -1)"
    [ -z "$csv" ] && { echo "?"; return; }
    local mhz
    mhz="$(tail -1 "$csv" 2>/dev/null | awk -F',' '{print $5}')"
    [ -z "$mhz" ] && { echo "?"; return; }
    case "$mhz" in
        1.8*|1.9*)   echo "160m ($mhz)" ;;
        3.5*|3.7*|3.8*) echo "80m ($mhz)" ;;
        7.0*|7.1*)   echo "40m ($mhz)" ;;
        10.1*)       echo "30m ($mhz)" ;;
        14.0*)       echo "20m ($mhz)" ;;
        18.1*)       echo "17m ($mhz)" ;;
        21.0*)       echo "15m ($mhz)" ;;
        24.9*)       echo "12m ($mhz)" ;;
        28.0*)       echo "10m ($mhz)" ;;
        *)           echo "$mhz" ;;
    esac
}
BAND_8080="$(band_label "$CAPTURE_8080_DIR")"
BAND_8081="$(band_label "$CAPTURE_8081_DIR")"

# WSJT-X has no cycle-archive.csv; its ALL.TXT carries dial freq as field 2 of
# every line instead (e.g. "260801_203245    14.074 Rx FT8 ..."), so read the
# last line rather than reusing band_label()'s csv path.
wsjtx_band_label() {
    local mhz
    mhz="$(tail -1 "$1" 2>/dev/null | awk '{print $2}')"
    [ -z "$mhz" ] && { echo "-"; return; }
    case "$mhz" in
        1.8*|1.9*)      echo "160m ($mhz)" ;;
        3.5*|3.7*|3.8*) echo "80m ($mhz)" ;;
        7.0*|7.1*)      echo "40m ($mhz)" ;;
        10.1*)          echo "30m ($mhz)" ;;
        14.0*)          echo "20m ($mhz)" ;;
        18.1*)          echo "17m ($mhz)" ;;
        21.0*)          echo "15m ($mhz)" ;;
        24.9*)          echo "12m ($mhz)" ;;
        28.0*)          echo "10m ($mhz)" ;;
        *)              echo "$mhz" ;;
    esac
}
BAND_WSJTX="$(wsjtx_band_label "$WSJTX_DIR/ALL.TXT")"

# --- WAV + ALL.TXT counts
wav_count()       { find "$1" -iname "*.wav" -path "*cycle-audio*" 2>/dev/null | wc -l | tr -d ' '; }
wsjtx_wav_count()  { find "$1/save" -iname "*.wav" 2>/dev/null | wc -l | tr -d ' '; }
line_count()       { local n; n=$(wc -l < "$1" 2>/dev/null | tr -d ' '); echo "${n:-0}"; }

WAV_8080=$(wav_count "$CAPTURE_8080_DIR")
WAV_8081=$(wav_count "$CAPTURE_8081_DIR")
WAV_WSJTX=$(wsjtx_wav_count "$WSJTX_DIR")

TXT_8080="$CAPTURE_8080_DIR/ALL.TXT"
TXT_8081="$CAPTURE_8081_DIR/ALL.TXT"
TXT_WSJTX="$WSJTX_DIR/ALL.TXT"

LINES_8080=$(line_count "$TXT_8080")
LINES_8081=$(line_count "$TXT_8081")
LINES_WSJTX=$(line_count "$TXT_WSJTX")

pct() { awk -v a="$1" -v b="$2" 'BEGIN { if (b+0==0) print "n/a"; else printf "%.1f%%", (a/b*100) }'; }

PCT_8080=$(pct "$LINES_8080" "$LINES_WSJTX")
PCT_8081=$(pct "$LINES_8081" "$LINES_WSJTX")

# --- Decodes in the last 30 minutes (leading YYMMDD_HHMMSS field of ALL.TXT)
T30=$(date -u --date="-30 minutes" +%y%m%d_%H%M%S)
d30() { awk -v t="$T30" '$1 >= t' "$1" 2>/dev/null | wc -l | tr -d ' '; }
D30_8080=$(d30 "$TXT_8080"); D30_8080=${D30_8080:-0}
D30_8081=$(d30 "$TXT_8081"); D30_8081=${D30_8081:-0}
D30_WSJTX=$(d30 "$TXT_WSJTX"); D30_WSJTX=${D30_WSJTX:-0}

D30PCT_8080=$(pct "$D30_8080" "$D30_WSJTX")
D30PCT_8081=$(pct "$D30_8081" "$D30_WSJTX")

# --- 0-dec/20: zeros among the last 20 "decode(s) found" lines in the *current* log
zero_count() {
    local log="$1"
    [ -z "$log" ] && { echo "n/a"; return; }
    grep -oP "\d+(?= decode\(s\) found)" "$log" 2>/dev/null | tail -20 | grep -c "^0$"
}
ZERO_8080=$(zero_count "$LOG_8080")
ZERO_8081=$(zero_count "$LOG_8081")

# --- Box-drawing table renderer (matches the reference screenshot's style).
#     Rows are passed as "cell|cell|cell..." strings; column widths are computed
#     from actual content so this stays correct as values grow (e.g. 6-digit
#     ALL.TXT counts later in the run).
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

    local border_top="┌" border_mid="├" border_bot="└" seg
    local top="┌" mid="├" bot="└"
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
    for ((i = 1; i < ${#rows[@]}; i++)); do
        print_row "${rows[i]}"
    done
    echo "$bot"
}

echo
render_table \
    "Source|Band|WAVs|ALL.TXT|vs WSJTX|Decodes/30min|0-dec/20" \
    "WSJT-X|$BAND_WSJTX|$WAV_WSJTX|$LINES_WSJTX|-|$D30_WSJTX|-" \
    "8080|$BAND_8080|$WAV_8080|$LINES_8080|$PCT_8080|$D30_8080 ($D30PCT_8080)|$ZERO_8080/20" \
    "8081|$BAND_8081|$WAV_8081|$LINES_8081|$PCT_8081|$D30_8081 ($D30PCT_8081)|$ZERO_8081/20"

# --- Silent checks: only surface if nonzero ---
ERR_8080=$(grep -c "\[ERR\]\|\[FTL\]" "$LOG_8080" 2>/dev/null); ERR_8080=${ERR_8080:-0}
ERR_8081=$(grep -c "\[ERR\]\|\[FTL\]" "$LOG_8081" 2>/dev/null); ERR_8081=${ERR_8081:-0}

RESTART_LOG_8080="$(find "$CAPTURE_8080_DIR" -maxdepth 1 -iname "restart-supervisor.log" 2>/dev/null | head -1)"
RESTART_LOG_8081="$(find "$CAPTURE_8081_DIR" -maxdepth 1 -iname "restart-supervisor.log" 2>/dev/null | head -1)"
RESTART_8080=$(grep -c "restarting" "$RESTART_LOG_8080" 2>/dev/null); RESTART_8080=${RESTART_8080:-0}
RESTART_8081=$(grep -c "restarting" "$RESTART_LOG_8081" 2>/dev/null); RESTART_8081=${RESTART_8081:-0}

FLAGS=0
if [ "${ERR_8080:-0}" -ne 0 ] 2>/dev/null; then echo; echo "!! 8080 current log has $ERR_8080 [ERR]/[FTL] line(s): $LOG_8080"; FLAGS=1; fi
if [ "${ERR_8081:-0}" -ne 0 ] 2>/dev/null; then echo; echo "!! 8081 current log has $ERR_8081 [ERR]/[FTL] line(s): $LOG_8081"; FLAGS=1; fi
if [ "${RESTART_8080:-0}" -ne 0 ] 2>/dev/null; then echo; echo "!! 8080 restart-supervisor.log shows $RESTART_8080 restart(s): $RESTART_LOG_8080"; FLAGS=1; fi
if [ "${RESTART_8081:-0}" -ne 0 ] 2>/dev/null; then echo; echo "!! 8081 restart-supervisor.log shows $RESTART_8081 restart(s): $RESTART_LOG_8081"; FLAGS=1; fi
if [ "$FLAGS" -eq 0 ]; then echo; echo "No [ERR]/[FTL] lines, no supervisor-triggered restarts on either instance."; fi

echo
echo "Current logs: 8080=$LOG_8080"
echo "              8081=$LOG_8081"
