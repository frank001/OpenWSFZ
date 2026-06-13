## MODIFIED Requirements

### Requirement: Two-pass decode structure with spectrogram-domain suppression

`K_MAX_PASSES` SHALL be set to **2**. Pass 0 is the full-waterfall decode (unchanged). Pass 1 is a
spectrogram-domain suppression decode: for each decoded candidate from pass 0, the shim attenuates
that signal's energy in the waterfall using a soft SNR-scaled factor for the exact decoded tone bin
and its ±1 nearest neighbours for each of the 79 FT8 symbols, then re-runs `ftx_find_candidates`
and `ftx_decode_candidate` on the modified waterfall. Both passes participate in the cross-pass
deduplication hash table so no message is reported more than once.

The inter-pass mechanism SHALL be spectrogram-domain tile attenuation via `suppress_candidate_tiles`.
PCM-domain SIC (introduced experimentally in shim 20260008 and 20260009, H3 and H3b) is NOT
the active mechanism as of shim 20260010; the GFSK helper functions remain in the source but
are not called.

#### Scenario: Pass 1 uses the spectrogram-suppressed waterfall

- **WHEN** pass 0 decodes at least one signal
- **THEN** the waterfall used by pass 1 SHALL have the tile energy of all pass-0 decoded signals
  attenuated (or zeroed, for strong signals) before candidate search begins

#### Scenario: Two-pass result count is queryable via ft8_get_last_pass_counts

- **WHEN** `ft8_decode_all` executes both passes and `ft8_get_last_pass_counts` is called with
  capacity 2
- **THEN** the function SHALL return 2 and `out_counts[0]` + `out_counts[1]` SHALL equal the total
  number of unique messages returned by `ft8_decode_all`

#### Scenario: Decode loop terminates after K_MAX_PASSES (2) iterations

- **WHEN** `ft8_decode_all` is called with any valid PCM buffer
- **THEN** the decode loop SHALL terminate after exactly 2 passes regardless of how many signals
  remain

#### Scenario: No second monitor_t is allocated (H3b infrastructure removed)

- **WHEN** `ft8_decode_all` executes
- **THEN** only one `monitor_t` instance (`mon`) SHALL be allocated and freed; no `mon2`,
  `gfsk_kernel`, `gfsk_prefix`, or `synth_buf_q` heap allocations SHALL occur in the
  inter-pass stage
