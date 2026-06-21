# CONTAMINATED — Do Not Use

**Status:** Not authoritative  
**Reason:** This S7 run was executed simultaneously with `d009-k10-confirm-s5` on the same
VB-CABLE virtual device. The OS mixer combined the S7 co-channel audio with the S5 AWGN
stream. Decode rates are slightly lower than the clean re-run (co_channel_sweep 85.0% vs
86.67% clean).

**Clean replacement:** `../d009-k10-confirm-s7-clean/` — sequential run with no S5 overlap.

Retained for the record. Not used in formal gate evaluation.
