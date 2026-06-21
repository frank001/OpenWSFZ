# CONTAMINATED — Do Not Use

**Status:** Not authoritative  
**Reason:** This S5 run was executed simultaneously with `d009-k10-confirm-s7` on the same
VB-CABLE virtual device. The OS mixer combined the S5 AWGN stream with the S7 co-channel
audio. FP counts may be inflated or suppressed by co-channel signal content.

**Clean replacement:** `../d009-k10-confirm-s5-clean/` — sequential run with no S7 overlap.

Retained for the record. Not used in any analysis.
