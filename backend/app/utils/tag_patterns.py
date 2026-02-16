"""Equipment tag patterns for extraction"""

EQUIPMENT_PATTERNS = [
    # RTU - Remote Terminal Units (high priority - multiple naming conventions)
    # Patterns: RTU-D01, RTU-F02, RTU D01, RTU_123, RTU123A, RTU(S)
    (r'\bRTU[-_\s]?[A-Z]\d{1,3}[A-Z]?\b', 'RTU'),  # RTU-D01, RTU-F02, RTU D01
    (r'\bRTU[-_]?\d{1,4}[A-Z]?\b', 'RTU'),          # RTU-123, RTU_456, RTU1A
    (r'\bRTU\([A-Z]\)\b', 'RTU'),                   # RTU(S), RTU(A)
    (r'\bRTU\b', 'RTU'),                            # Plain RTU
    # Standard patterns: TYPE-NUMBER or TYPE_NUMBER
    (r'\b(FAN|AHU|FCU|VAV[E]?|MAU|EF|SF|RF)-?\d{1,4}[A-Z]?\b', 'FAN'),
    (r'\b(FAN|AHU|FCU|VAV[E]?|MAU|EF|SF|RF)-[A-Z]\d{1,4}[A-Z]?\b', 'FAN'), # VAVE-F04
    (r'\b(MOT|MTR|M)-?\d{1,4}[A-Z]?\b', 'MOTOR'),
    (r'\b(VFD|VSD|AFD)-?\d{1,4}[A-Z]?\b', 'VFD'),
    (r'\b(PMP|P)-?\d{1,4}[A-Z]?\b', 'PUMP'),
    (r'\b(BKR|CB|MCCB)-?\d{1,4}[A-Z]?\b', 'BREAKER'),
    (r'\b(RLY|CR|TR)-?\d{1,4}[A-Z]?\b', 'RELAY'),
    (r'\b(PLC|DCS|PAC)-?\d{1,4}[A-Z]?\b', 'PLC'),
    (r'\b(TS|PS|FS|LS|PT|FT|LT|TT)-?\d{1,4}[A-Z]?\b', 'SENSOR'),
    (r'\b(CV|MOV|SOV|BV|GV)-?\d{1,4}[A-Z]?\b', 'VALVE'),
    (r'\b(MCC|SWG|PNL|DP|LP|MDP)-?\d{1,4}[A-Z]?\b', 'PANEL'),
    (r'\b(XFMR|TX)-?\d{1,4}[A-Z]?\b', 'TRANSFORMER'),
    (r'\bTR-\d{1,4}[A-Z]?\b', 'TRANSFORMER'),              # TR requires hyphen to avoid "TR1" false positives
    (r'\bT-\d{1,4}[A-Z]?\b', 'TRANSFORMER'),                # T requires hyphen (T-1 yes, T1 no)
    # Additional equipment types
    (r'\b(SW|HS|SS|DS)-?\d{1,4}[A-Z]?\b', 'SWITCH'),
    (r'\b(HMI|OIT|OIU)-?\d{1,4}[A-Z]?\b', 'HMI'),
    (r'\b(UPS)-?\d{1,4}[A-Z]?\b', 'UPS'),
    (r'\b(GEN|DG|EG)-?\d{1,4}[A-Z]?\b', 'GENERATOR'),
    (r'\b(CAP|CAPBANK)-?\d{1,4}[A-Z]?\b', 'CAPACITOR'),
    (r'\b(CT|VT|PT)-?\d{1,4}[A-Z]?\b', 'INSTRUMENT_TRANSFORMER'),
    # Protective relays (ANSI device numbers - require hyphen or suffix to avoid matching plain numbers)
    (r'\b(27|50|51|52|59|67|81|86|87)-\d{1,2}[A-Z]?\b', 'PROTECTIVE_RELAY'),    # 50-1, 87-1A
    (r'\b(27|50|51|52|59|67|81|86|87)[A-Z]\b', 'PROTECTIVE_RELAY'),              # 50N, 51G, 87T
    # Generic pattern for unrecognized equipment (alphanumeric tags, requires hyphen or underscore)
    (r'\b([A-Z]{2,5})[-_]([A-Z]?\d{1,4})([A-Z]?)\b', 'OTHER'),
]

WIRE_PATTERNS = [
    r'\bW-?\d{3,5}\b',
    r'\b\d{3,4}[A-Z]{0,2}\b',
    r'\bCABLE-?\d{2,4}\b',
]

CONTROL_KEYWORDS = ['controls', 'controlled by', 'starts', 'stops', 'enables', 'interlocked']
POWER_KEYWORDS = ['powers', 'powered by', 'feeds', 'fed from', 'supplies']
