#!/bin/bash
# Run on the PC AFTER the Captain has woken sol (and not before): stage the third night's inputs on sol under ~/_l1p (the chain tn_arms.sh reads them there).
#   - the 800 selected WAVs + the warm-up WAV + the 3 F-DRY WAVs of night 20260930_1930 (selection_3n.json) -> ~/_l1p/wav/20260930_1930_endurance_run-gathered/owsfz/wav/
#   - the night's WSJT-X ALL.TXT (the reference) -> ~/_l1p/wsjtx_ALL_3n.TXT
#   - selection_3n.json -> ~/_l1p/selection_3n.json   (its SHA-256 is verified on sol against the freeze commit's value)
# The libft8.so, the Developer's b1d8a06e tree and the built Replay81 are staged separately (build on sol, freeze commit records the .so SHA-256).
# usage: SEL_SHA=<sha256 from the freeze commit> bash tn_stage.sh
: "${SEL_SHA:?set SEL_SHA to the SHA-256 of the selection recorded in the freeze commit}"
K="-i $HOME/.ssh/claude/id_ed25519_sol -o BatchMode=yes -o ConnectTimeout=15"
S=/d/Projects/claude/_qa-scratch/late-sub
RUN=20260930_1930
ART=/d/Projects/claude/OpenWSFZ/artefacts/${RUN}_endurance_run-gathered
DEST='~/_l1p'
[ "$(sha256sum $S/selection_3n.json | cut -d' ' -f1)" = "$SEL_SHA" ] || { echo "selection differs from the freeze commit's SHA-256"; exit 9; }
ssh $K claude@sol "mkdir -p $DEST/wav/${RUN}_endurance_run-gathered/owsfz/wav" || exit 9
scp $K "$S/selection_3n.json" "claude@sol:$DEST/selection_3n.json" || exit 9
scp $K "$S/selection_3n_dry.json" "claude@sol:$DEST/selection_3n_dry.json" || exit 9
scp $K "$ART/wsjt-x/ALL.TXT" "claude@sol:$DEST/wsjtx_ALL_3n.TXT" || exit 9
python -I - "$S/selection_3n.json" > "$S/stage_list_3n.txt" <<'PY'
import json, sys
sys.stdout.reconfigure(newline=chr(10))   # Windows python would write CRLF and tar would look for names ending in CR
r = json.load(open(sys.argv[1]))["runs"]["20260930_1930"]
import os
dry = json.load(open(sys.argv[1].replace(".json", "_dry.json")))["runs"]["20260930_1930"]["FULL"]
for s in r["FULL"] + [r["warmup"]] + dry:
    print(s + ".wav")
PY
[ "$(wc -l < $S/stage_list_3n.txt)" = 804 ] || { echo "stage list is not 804 files"; exit 9; }
(cd "$ART/owsfz/wav" && tar cf - -T "$S/stage_list_3n.txt") | ssh $K claude@sol "tar xf - -C $DEST/wav/${RUN}_endurance_run-gathered/owsfz/wav" || exit 9
n=$(ssh $K claude@sol "ls $DEST/wav/${RUN}_endurance_run-gathered/owsfz/wav | wc -l")
r=$(ssh $K claude@sol "sha256sum $DEST/selection_3n.json | cut -d' ' -f1")
same=DIFFERENT
[ "$r" = "$SEL_SHA" ] && same=SAME
echo "staged: wavs on sol=$n (expect 804); selection sha on sol=$r ($same)"
