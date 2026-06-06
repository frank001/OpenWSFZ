"""L1 — FT8 protocol constants (public, from the FT8 specification).

These are protocol facts, not implementation borrowed from any decoder.
"""

# --- Symbol structure ---------------------------------------------------------
NUM_TONES = 8                 # 8-FSK
BITS_PER_SYMBOL = 3           # log2(8)
SYMBOL_PERIOD_S = 0.16        # 160 ms per symbol
TONE_SPACING_HZ = 6.25        # 1 / SYMBOL_PERIOD_S
NUM_DATA_SYMBOLS = 58         # 174 codeword bits / 3 bits per symbol
NUM_SYMBOLS = 79              # 58 data + 3 x 7 Costas sync symbols
SLOT_LENGTH_S = 15.0          # FT8 T/R period
TRANSMISSION_S = NUM_SYMBOLS * SYMBOL_PERIOD_S  # 12.64 s

# --- Codeword structure -------------------------------------------------------
MESSAGE_BITS = 77             # payload bits
CRC_BITS = 14
MESSAGE_PLUS_CRC_BITS = 91    # 77 + 14
PARITY_BITS = 83             # LDPC(174, 91)
CODEWORD_BITS = 174           # 91 + 83

# --- Sync ---------------------------------------------------------------------
# 7x7 Costas array used at symbol indices 0..6, 36..42, 72..78.
COSTAS_ARRAY = (3, 1, 4, 0, 6, 5, 2)
COSTAS_START_INDICES = (0, 36, 72)
COSTAS_LEN = 7

# Gray code: maps a 3-bit data value (0..7) to a transmitted tone index.
# tone = GRAY_MAP[value]
GRAY_MAP = (0, 1, 3, 2, 5, 6, 4, 7)

# --- Default rendering --------------------------------------------------------
DEFAULT_SAMPLE_RATE_HZ = 48000   # STUDY-SPEC §4.1: mono, 48 kHz, shared mode
REFERENCE_BANDWIDTH_HZ = 2500.0  # WSJT-X SNR reference bandwidth (STUDY-SPEC §5)
GFSK_BT = 2.0                    # Gaussian shaping bandwidth-time product (FT8)
