# NFR-021 redaction map -- AWGN-FP ROW 0 result CSVs

Every callsign-shaped token the project's own scanner (`qa/rr-study/nfr021_pre_merge_scan.py`, `CALL_RE` + `classify()`) flagged in
`results/*_decodes.csv` was replaced with a distinct `<RDCTnn>` placeholder.

These tokens are **decoder output, not injected truth** -- verified before rewriting: none of the
73 appears in any `truth.csv` or scenario file, and the injected corpus itself carries zero
non-Q-prefix callsign-shaped tokens. They are noise-hallucinated strings that happen to match a
callsign shape.

Placeholders are deliberately **not** Q-prefix: a Q-prefix placeholder would be indistinguishable
from a legitimately injected synthetic call and would corrupt future `truth.csv` joins.

Fingerprint is `"CS-" + sha256(token)[:6]`, the scanner's own `fp()`. The map is one-way by
construction -- it identifies nothing on its own.

| placeholder | token fingerprint |
|---|---|
| `<RDCT01>` | `CS-5139e9` |
| `<RDCT02>` | `CS-7120d5` |
| `<RDCT03>` | `CS-04028f` |
| `<RDCT04>` | `CS-912876` |
| `<RDCT05>` | `CS-07f833` |
| `<RDCT06>` | `CS-747771` |
| `<RDCT07>` | `CS-8b38ef` |
| `<RDCT08>` | `CS-af7c02` |
| `<RDCT09>` | `CS-32091d` |
| `<RDCT10>` | `CS-e03e96` |
| `<RDCT11>` | `CS-b74805` |
| `<RDCT12>` | `CS-6816de` |
| `<RDCT13>` | `CS-d4db96` |
| `<RDCT14>` | `CS-6ebf47` |
| `<RDCT15>` | `CS-ef7332` |
| `<RDCT16>` | `CS-e605a6` |
| `<RDCT17>` | `CS-1192a5` |
| `<RDCT18>` | `CS-749b4c` |
| `<RDCT19>` | `CS-eece83` |
| `<RDCT20>` | `CS-5b0237` |
| `<RDCT21>` | `CS-b66b31` |
| `<RDCT22>` | `CS-ada6f8` |
| `<RDCT23>` | `CS-dadcfd` |
| `<RDCT24>` | `CS-eab828` |
| `<RDCT25>` | `CS-93c6ce` |
| `<RDCT26>` | `CS-fb87f2` |
| `<RDCT27>` | `CS-b8d59b` |
| `<RDCT28>` | `CS-ad360c` |
| `<RDCT29>` | `CS-81c082` |
| `<RDCT30>` | `CS-e9cf18` |
| `<RDCT31>` | `CS-224370` |
| `<RDCT32>` | `CS-0edca3` |
| `<RDCT33>` | `CS-badcb1` |
| `<RDCT34>` | `CS-fa39ca` |
| `<RDCT35>` | `CS-97b6ed` |
| `<RDCT36>` | `CS-33ca6b` |
| `<RDCT37>` | `CS-c2ce7e` |
| `<RDCT38>` | `CS-5e261d` |
| `<RDCT39>` | `CS-d7eec9` |
| `<RDCT40>` | `CS-c2e5a0` |
| `<RDCT41>` | `CS-6db53a` |
| `<RDCT42>` | `CS-caa9c5` |
| `<RDCT43>` | `CS-86e744` |
| `<RDCT44>` | `CS-0b1bde` |
| `<RDCT45>` | `CS-99df2c` |
| `<RDCT46>` | `CS-271eb4` |
| `<RDCT47>` | `CS-f329a8` |
| `<RDCT48>` | `CS-fda80a` |
| `<RDCT49>` | `CS-d6155e` |
| `<RDCT50>` | `CS-52c654` |
| `<RDCT51>` | `CS-69c6eb` |
| `<RDCT52>` | `CS-53e161` |
| `<RDCT53>` | `CS-ee5445` |
| `<RDCT54>` | `CS-3edb5a` |
| `<RDCT55>` | `CS-0aed7f` |
| `<RDCT56>` | `CS-6d4d3d` |
| `<RDCT57>` | `CS-ac941a` |
| `<RDCT58>` | `CS-e9c8ab` |
| `<RDCT59>` | `CS-1df6f1` |
| `<RDCT60>` | `CS-52b51b` |
| `<RDCT61>` | `CS-113eea` |
| `<RDCT62>` | `CS-95d3e5` |
| `<RDCT63>` | `CS-ddb524` |
| `<RDCT64>` | `CS-5c72f6` |
| `<RDCT65>` | `CS-40da64` |
| `<RDCT66>` | `CS-6ec691` |
| `<RDCT67>` | `CS-a05ad5` |
| `<RDCT68>` | `CS-7c95c5` |
| `<RDCT69>` | `CS-55b45f` |
| `<RDCT70>` | `CS-ea086c` |
| `<RDCT71>` | `CS-52311c` |
| `<RDCT72>` | `CS-0620ab` |
| `<RDCT73>` | `CS-3dc2c1` |
