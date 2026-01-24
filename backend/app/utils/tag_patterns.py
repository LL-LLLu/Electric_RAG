"""Equipment tag patterns for extraction"""

EQUIPMENT_PATTERNS = [
    # Standard patterns: TYPE-NUMBER or TYPE_NUMBER
    (r'\b(FAN|AHU|FCU|VAV|MAU|EF|SF|RF)-?\d{1,4}[A-Z]?\b', 'FAN'),
    (r'\b(MOT|MTR|M)-?\d{1,4}[A-Z]?\b', 'MOTOR'),
    (r'\b(VFD|VSD|AFD)-?\d{1,4}[A-Z]?\b', 'VFD'),
    (r'\b(PMP|P)-?\d{1,4}[A-Z]?\b', 'PUMP'),
    (r'\b(BKR|CB|MCCB)-?\d{1,4}[A-Z]?\b', 'BREAKER'),
    (r'\b(RLY|CR|TR)-?\d{1,4}[A-Z]?\b', 'RELAY'),
    (r'\b(PLC|DCS|PAC)-?\d{1,4}[A-Z]?\b', 'PLC'),
    (r'\b(TS|PS|FS|LS|PT|FT|LT|TT)-?\d{1,4}[A-Z]?\b', 'SENSOR'),
    (r'\b(CV|MOV|SOV|BV|GV)-?\d{1,4}[A-Z]?\b', 'VALVE'),
    (r'\b(MCC|SWG|PNL|DP)-?\d{1,4}[A-Z]?\b', 'PANEL'),
    (r'\b(XFMR|TX|TR)-?\d{1,4}[A-Z]?\b', 'TRANSFORMER'),
    # Generic pattern for unrecognized equipment
    (r'\b([A-Z]{2,4})-(\d{2,4})([A-Z]?)\b', 'OTHER'),
]

WIRE_PATTERNS = [
    r'\bW-?\d{3,5}\b',
    r'\b\d{3,4}[A-Z]{0,2}\b',
    r'\bCABLE-?\d{2,4}\b',
]

CONTROL_KEYWORDS = ['controls', 'controlled by', 'starts', 'stops', 'enables', 'interlocked']
POWER_KEYWORDS = ['powers', 'powered by', 'feeds', 'fed from', 'supplies']
