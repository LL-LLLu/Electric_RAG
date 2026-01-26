import os
import json
import logging
import time
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


# Specialized agent prompts for different analysis aspects
EQUIPMENT_AGENT_PROMPT = """You are an expert at identifying equipment in electrical/mechanical drawings.

Extract ALL equipment tags and identifiers from this page. Be extremely thorough.

EQUIPMENT CATEGORIES TO FIND:
- Electrical: MCC, MDP, DP, LP, PNL, XFMR, CB, BKR, DISC, FDR, SWG, ATS, UPS, PDU
- Motors/Drives: M, MTR, VFD, VSD, ASD, SOFT STARTER
- Control: PLC, RTU, DCS, HMI, PAC, I/O, RIO, DDC, BMS, BAS
- HVAC: AHU, RTU, FCU, VAV, CRAH, CRAC, CU, AC, EF, SF, RF, MAU, ERU, HRU
- Pumps: P, PMP, CWP, HWP, CHWP, CDP, CUP, SWP
- Valves: V, MOV, SOV, CV, BV, GV, CHV, PRV, RV, FV, TV
- Sensors: TT, PT, FT, LT, AT, PDT, DPT, TE, PE, FE, LE, TI, PI, FI, LI
- Instrumentation: TIC, PIC, FIC, LIC, AIC, TSL, TSH, PSL, PSH, FSL, FSH
- Breakers/Protection: 52, 27, 50, 51, 86, 87, OCR, OCPD, GFCI, AFCI
- Other: EUH, UH, HUM, TH, STAT, BDD, LVR, DMR

For EACH equipment found, provide:
- tag: The exact tag/identifier
- type: Equipment category
- description: What it is/does based on context
- specs: Any specifications found (HP, kW, voltage, capacity, etc.)

Respond in JSON format:
{
    "equipment": [
        {
            "tag": "VFD-101",
            "type": "VFD",
            "description": "Variable Frequency Drive for pump P-101",
            "specs": {"hp": "50", "voltage": "480V", "enclosure": "NEMA 4X"}
        }
    ]
}
"""

ELECTRICAL_AGENT_PROMPT = """You are an expert electrical engineer analyzing power distribution.

Analyze this page for ALL electrical/power connections and relationships.

FIND THESE ELECTRICAL DETAILS:
1. POWER FEED CHAINS: What feeds what (e.g., "MCC-1 is fed from MDP-1 via BKR-101")
2. BREAKER ASSIGNMENTS: Which breakers feed which equipment
3. WIRE/CABLE INFO: Wire sizes, cable types, conduit sizes, wire numbers
4. VOLTAGE LEVELS: Equipment voltages, transformation points
5. LOAD INFORMATION: HP ratings, kW, kVA, FLA, amp ratings
6. PROTECTION DEVICES: Fuses, breakers, relays protecting equipment
7. GROUNDING: Ground connections, ground buses

For EACH electrical connection, capture:
- source: The upstream equipment/device
- target: The downstream equipment/device
- connection_type: FEEDS, PROTECTS, GROUNDS, SWITCHES
- wire_info: Wire size, cable type, wire numbers if shown
- breaker: Breaker/fuse designation if applicable
- voltage: Voltage level
- load: Load rating if shown

Respond in JSON format:
{
    "electrical_connections": [
        {
            "source": "MCC-1",
            "target": "VFD-101",
            "connection_type": "FEEDS",
            "wire_info": {"size": "#10 AWG", "cable": "3C+G", "wire_numbers": ["W101", "W102", "W103"]},
            "breaker": "BKR-15",
            "voltage": "480V",
            "load": "50HP"
        }
    ],
    "power_hierarchy": ["MAIN XFMR -> MDP-1 -> MCC-1 -> VFD-101 -> M-101"]
}
"""

CONTROL_AGENT_PROMPT = """You are an expert control systems engineer analyzing control connections.

Analyze this page for ALL control system connections and signal relationships.

FIND THESE CONTROL DETAILS:
1. PLC/DCS CONNECTIONS: What I/O points connect to what devices
2. CONTROL SIGNALS: 4-20mA, 0-10V, digital I/O, Modbus, BACnet
3. CONTROL LOOPS: What controls what (PID loops, on/off control)
4. INTERLOCKS: Safety interlocks, permissives, trips
5. CONTROL WIRING: Control wire numbers, terminal blocks, junction boxes
6. NETWORK CONNECTIONS: Communication buses, protocols, network drops
7. HMI/OPERATOR INTERFACES: What gets displayed/controlled where

For EACH control connection, capture:
- controller: The controlling device (PLC, DDC, etc.)
- field_device: The field device being controlled/monitored
- io_type: DI, DO, AI, AO, or communication protocol
- signal_type: 4-20mA, 0-10V, 24VDC, dry contact, etc.
- wire_info: Control wire numbers, cable designations
- point_name: I/O point name/address if shown
- function: What this connection does

Respond in JSON format:
{
    "control_connections": [
        {
            "controller": "PLC-1",
            "field_device": "VFD-101",
            "io_type": "AO",
            "signal_type": "4-20mA",
            "wire_info": {"wire_numbers": ["C101", "C102"], "terminal": "TB-1"},
            "point_name": "AO-101",
            "function": "Speed command to VFD"
        },
        {
            "controller": "PLC-1",
            "field_device": "PT-101",
            "io_type": "AI",
            "signal_type": "4-20mA",
            "wire_info": {"wire_numbers": ["C201", "C202"]},
            "point_name": "AI-201",
            "function": "Pressure feedback from discharge"
        }
    ],
    "interlocks": [
        {
            "trigger": "PSH-101",
            "action": "Trips P-101",
            "type": "SAFETY",
            "description": "High pressure shutdown"
        }
    ]
}
"""

DRAWING_TYPE_CLASSIFICATION_PROMPT = """Classify this drawing page into one of these types:

TYPES:
- ONE_LINE: Single-line electrical diagram showing power distribution (bus bars, breakers, transformers, switchgear, MCCs, feeders)
- PID: Piping & Instrumentation diagram showing process flow (pipes, valves, instruments, vessels, pumps with flow paths)
- CONTROL_SCHEMATIC: Control wiring diagram showing relay logic, PLC I/O, control circuits, ladder logic
- WIRING_DIAGRAM: Point-to-point wiring diagram showing terminals, wire numbers, cable schedules, interconnections
- SCHEDULE: Tabular data like panel schedules, cable schedules, equipment lists, load lists
- GENERAL: Cover sheets, title blocks, notes, details, legends, or pages that don't fit other categories

Analyze the content and structure of the page to determine its type.

Return JSON only: {"drawing_type": "ONE_LINE", "confidence": 0.85}
"""

MECHANICAL_AGENT_PROMPT = """You are an expert mechanical/piping engineer analyzing mechanical systems.

Analyze this page for ALL mechanical/piping connections and relationships.

FIND THESE MECHANICAL DETAILS:
1. PIPING CONNECTIONS: What connects to what via pipes
2. PIPE SPECIFICATIONS: Pipe sizes, materials, insulation
3. FLOW DIRECTION: Direction of flow between equipment
4. DUCT CONNECTIONS: Ductwork between HVAC equipment
5. MECHANICAL DRIVES: What drives what (motor drives pump, etc.)
6. VALVE POSITIONS: Inline valves, their function and position
7. DRAIN/VENT CONNECTIONS: Drains, vents, relief paths

For EACH mechanical connection, capture:
- upstream: The upstream equipment
- downstream: The downstream equipment
- connection_type: PIPE, DUCT, SHAFT, BELT
- medium: What flows through (water, air, refrigerant, etc.)
- size: Pipe/duct size
- spec: Material, schedule, insulation
- inline_devices: Valves, dampers, strainers inline

Respond in JSON format:
{
    "mechanical_connections": [
        {
            "upstream": "P-101",
            "downstream": "HX-101",
            "connection_type": "PIPE",
            "medium": "Chilled Water",
            "size": "4 inch",
            "spec": "SCH40 CS",
            "inline_devices": [
                {"tag": "V-101", "type": "ISOLATION", "position": "UPSTREAM"},
                {"tag": "CV-101", "type": "CONTROL", "position": "DOWNSTREAM"}
            ]
        }
    ],
    "drive_connections": [
        {
            "driver": "M-101",
            "driven": "P-101",
            "coupling": "DIRECT",
            "specs": "50HP, 1800RPM"
        }
    ]
}
"""


class AIAnalysisService:
    """AI-powered page analysis with specialized agents for comprehensive extraction"""

    def __init__(self):
        self.provider = os.environ.get("LLM_PROVIDER", "claude").lower()
        self.anthropic_client = None
        self.gemini_model = None

        if self.provider == "claude":
            try:
                import anthropic
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if api_key:
                    self.anthropic_client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                pass
        elif self.provider == "gemini":
            try:
                import google.generativeai as genai
                api_key = os.environ.get("GEMINI_API_KEY")
                if api_key:
                    genai.configure(api_key=api_key)
                    self.gemini_model = genai.GenerativeModel("gemini-2.0-flash")
            except ImportError:
                pass

    def _has_llm(self) -> bool:
        return self.anthropic_client is not None or self.gemini_model is not None

    def _call_llm(self, prompt: str, max_tokens: int = 2048) -> str:
        """Call the LLM with the given prompt"""
        if self.provider == "gemini" and self.gemini_model:
            response = self.gemini_model.generate_content(prompt)
            return response.text
        elif self.anthropic_client:
            response = self.anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        return ""

    def _parse_json_response(self, response_text: str) -> Dict:
        """Extract JSON from LLM response"""
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        return {}

    def _run_equipment_agent(self, page_text: str, page_number: int, document_name: str) -> Dict:
        """Equipment identification agent"""
        prompt = f"""{EQUIPMENT_AGENT_PROMPT}

Document: {document_name}
Page: {page_number}

Page Content:
---
{page_text}
---

Extract all equipment. Respond with JSON only."""

        try:
            response = self._call_llm(prompt)
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"Equipment agent error: {e}")
            return {"equipment": []}

    def _run_electrical_agent(self, page_text: str, page_number: int, document_name: str) -> Dict:
        """Electrical/power analysis agent"""
        prompt = f"""{ELECTRICAL_AGENT_PROMPT}

Document: {document_name}
Page: {page_number}

Page Content:
---
{page_text}
---

Analyze all electrical connections. Respond with JSON only."""

        try:
            response = self._call_llm(prompt)
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"Electrical agent error: {e}")
            return {"electrical_connections": []}

    def _run_control_agent(self, page_text: str, page_number: int, document_name: str) -> Dict:
        """Control systems analysis agent"""
        prompt = f"""{CONTROL_AGENT_PROMPT}

Document: {document_name}
Page: {page_number}

Page Content:
---
{page_text}
---

Analyze all control connections. Respond with JSON only."""

        try:
            response = self._call_llm(prompt)
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"Control agent error: {e}")
            return {"control_connections": [], "interlocks": []}

    def _run_mechanical_agent(self, page_text: str, page_number: int, document_name: str) -> Dict:
        """Mechanical/piping analysis agent"""
        prompt = f"""{MECHANICAL_AGENT_PROMPT}

Document: {document_name}
Page: {page_number}

Page Content:
---
{page_text}
---

Analyze all mechanical connections. Respond with JSON only."""

        try:
            response = self._call_llm(prompt)
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"Mechanical agent error: {e}")
            return {"mechanical_connections": [], "drive_connections": []}

    def _classify_drawing_type(self, page_text: str, page_number: int, document_name: str) -> Dict:
        """Classify the drawing type of a page"""
        prompt = f"""{DRAWING_TYPE_CLASSIFICATION_PROMPT}

Document: {document_name}
Page: {page_number}

Page Content:
---
{page_text[:5000]}
---

Classify this page. Respond with JSON only."""

        try:
            response = self._call_llm(prompt, max_tokens=256)
            result = self._parse_json_response(response)
            drawing_type = result.get("drawing_type", "GENERAL")
            # Validate the drawing type
            valid_types = ["ONE_LINE", "PID", "CONTROL_SCHEMATIC", "WIRING_DIAGRAM", "SCHEDULE", "GENERAL"]
            if drawing_type not in valid_types:
                drawing_type = "GENERAL"
            return {
                "drawing_type": drawing_type,
                "confidence": result.get("confidence", 0.5)
            }
        except Exception as e:
            logger.error(f"Drawing type classification error on page {page_number}: {e}")
            return {"drawing_type": "GENERAL", "confidence": 0.0}

    def analyze_page(self, page_text: str, page_number: int, document_name: str) -> Dict:
        """
        Comprehensive page analysis using multiple specialized agents.
        Runs agents in parallel for efficiency, then combines results.
        """
        if not self._has_llm():
            print(f"[AI] No LLM available, skipping AI analysis for page {page_number}")
            return {"analysis": "", "equipment": [], "relationships": []}

        if not page_text or len(page_text.strip()) < 50:
            print(f"[AI] Page {page_number} has insufficient text, skipping analysis")
            return {"analysis": "Page has minimal text content", "equipment": [], "relationships": []}

        # Truncate very long text
        text_to_analyze = page_text[:12000] if len(page_text) > 12000 else page_text

        start_time = time.time()
        print(f"[AI] Page {page_number}: Starting multi-agent analysis (parallel)...")

        # Run all agents in parallel using ThreadPoolExecutor
        equipment_result = {}
        electrical_result = {}
        control_result = {}
        mechanical_result = {}
        classification_result = {"drawing_type": "GENERAL", "confidence": 0.0}

        try:
            with ThreadPoolExecutor(max_workers=5) as executor:
                # Submit all agent tasks including classification
                futures = {
                    executor.submit(self._run_equipment_agent, text_to_analyze, page_number, document_name): "equipment",
                    executor.submit(self._run_electrical_agent, text_to_analyze, page_number, document_name): "electrical",
                    executor.submit(self._run_control_agent, text_to_analyze, page_number, document_name): "control",
                    executor.submit(self._run_mechanical_agent, text_to_analyze, page_number, document_name): "mechanical",
                    executor.submit(self._classify_drawing_type, text_to_analyze, page_number, document_name): "classification",
                }

                # Collect results as they complete
                for future in as_completed(futures):
                    agent_name = futures[future]
                    try:
                        result = future.result()
                        if agent_name == "equipment":
                            equipment_result = result
                            print(f"[AI] Page {page_number}: Equipment Agent completed")
                        elif agent_name == "electrical":
                            electrical_result = result
                            print(f"[AI] Page {page_number}: Electrical Agent completed")
                        elif agent_name == "control":
                            control_result = result
                            print(f"[AI] Page {page_number}: Control Agent completed")
                        elif agent_name == "mechanical":
                            mechanical_result = result
                            print(f"[AI] Page {page_number}: Mechanical Agent completed")
                        elif agent_name == "classification":
                            classification_result = result
                            print(f"[AI] Page {page_number}: Classification completed - {result.get('drawing_type', 'GENERAL')}")
                    except Exception as e:
                        logger.error(f"{agent_name} agent error on page {page_number}: {e}")

        except Exception as e:
            logger.error(f"Agent execution error on page {page_number}: {e}")

        # Combine results
        combined = self._combine_agent_results(
            equipment_result,
            electrical_result,
            control_result,
            mechanical_result
        )

        # Add drawing type classification
        combined["drawing_type"] = classification_result.get("drawing_type", "GENERAL")
        combined["drawing_type_confidence"] = classification_result.get("confidence", 0.0)

        elapsed = time.time() - start_time
        eq_count = len(combined.get("equipment", []))
        rel_count = len(combined.get("relationships", []))
        print(f"[AI] Page {page_number} analyzed in {elapsed:.1f}s | {eq_count} equipment | {rel_count} relationships")

        return combined

    def _combine_agent_results(
        self,
        equipment_result: Dict,
        electrical_result: Dict,
        control_result: Dict,
        mechanical_result: Dict
    ) -> Dict:
        """Combine results from all agents into a unified structure"""

        # Extract equipment tags
        equipment_list = equipment_result.get("equipment", [])
        equipment_tags = []
        equipment_details = []

        for eq in equipment_list:
            if isinstance(eq, dict):
                tag = eq.get("tag", "")
                if tag:
                    equipment_tags.append(tag)
                    equipment_details.append(eq)
            elif isinstance(eq, str):
                equipment_tags.append(eq)
                equipment_details.append({"tag": eq, "type": "UNKNOWN"})

        # Build relationships from all sources
        relationships = []
        detailed_connections = []

        # Process electrical connections
        for conn in electrical_result.get("electrical_connections", []):
            source = conn.get("source", "")
            target = conn.get("target", "")
            if source and target:
                # Add to simple relationships
                conn_type = conn.get("connection_type", "FEEDS")
                relationships.append(f"{source} {conn_type.lower()} {target}")

                # Add detailed connection
                detailed_connections.append({
                    "source": source,
                    "target": target,
                    "category": "ELECTRICAL",
                    "connection_type": conn_type,
                    "details": {
                        "wire_info": conn.get("wire_info"),
                        "breaker": conn.get("breaker"),
                        "voltage": conn.get("voltage"),
                        "load": conn.get("load")
                    }
                })

        # Process control connections
        for conn in control_result.get("control_connections", []):
            controller = conn.get("controller", "")
            field_device = conn.get("field_device", "")
            if controller and field_device:
                io_type = conn.get("io_type", "")
                function = conn.get("function", "")

                if io_type in ["AI", "DI"]:
                    relationships.append(f"{field_device} sends signal to {controller}")
                else:
                    relationships.append(f"{controller} controls {field_device}")

                detailed_connections.append({
                    "source": controller,
                    "target": field_device,
                    "category": "CONTROL",
                    "connection_type": io_type,
                    "details": {
                        "signal_type": conn.get("signal_type"),
                        "wire_info": conn.get("wire_info"),
                        "point_name": conn.get("point_name"),
                        "function": function
                    }
                })

        # Process interlocks
        for interlock in control_result.get("interlocks", []):
            trigger = interlock.get("trigger", "")
            action = interlock.get("action", "")
            if trigger and action:
                relationships.append(f"{trigger} {action}")
                detailed_connections.append({
                    "source": trigger,
                    "target": action,
                    "category": "INTERLOCK",
                    "connection_type": interlock.get("type", "SAFETY"),
                    "details": {
                        "description": interlock.get("description")
                    }
                })

        # Process mechanical connections
        for conn in mechanical_result.get("mechanical_connections", []):
            upstream = conn.get("upstream", "")
            downstream = conn.get("downstream", "")
            if upstream and downstream:
                medium = conn.get("medium", "")
                if medium:
                    relationships.append(f"{upstream} connects to {downstream} via {medium}")
                else:
                    relationships.append(f"{upstream} connects to {downstream}")

                detailed_connections.append({
                    "source": upstream,
                    "target": downstream,
                    "category": "MECHANICAL",
                    "connection_type": conn.get("connection_type", "PIPE"),
                    "details": {
                        "medium": medium,
                        "size": conn.get("size"),
                        "spec": conn.get("spec"),
                        "inline_devices": conn.get("inline_devices")
                    }
                })

        # Process drive connections
        for conn in mechanical_result.get("drive_connections", []):
            driver = conn.get("driver", "")
            driven = conn.get("driven", "")
            if driver and driven:
                relationships.append(f"{driver} drives {driven}")
                detailed_connections.append({
                    "source": driver,
                    "target": driven,
                    "category": "MECHANICAL",
                    "connection_type": "DRIVES",
                    "details": {
                        "coupling": conn.get("coupling"),
                        "specs": conn.get("specs")
                    }
                })

        # Process power hierarchy
        power_hierarchy = electrical_result.get("power_hierarchy", [])

        # Generate summary
        summary_parts = []
        if equipment_tags:
            summary_parts.append(f"Contains {len(equipment_tags)} equipment items")
        if detailed_connections:
            elec_count = sum(1 for c in detailed_connections if c["category"] == "ELECTRICAL")
            ctrl_count = sum(1 for c in detailed_connections if c["category"] == "CONTROL")
            mech_count = sum(1 for c in detailed_connections if c["category"] == "MECHANICAL")
            if elec_count:
                summary_parts.append(f"{elec_count} electrical connections")
            if ctrl_count:
                summary_parts.append(f"{ctrl_count} control connections")
            if mech_count:
                summary_parts.append(f"{mech_count} mechanical connections")

        summary = ". ".join(summary_parts) if summary_parts else "Page analyzed"

        return {
            "analysis": summary,
            "equipment": equipment_tags,
            "equipment_details": equipment_details,
            "relationships": relationships,
            "detailed_connections": detailed_connections,
            "power_hierarchy": power_hierarchy,
            "raw_results": {
                "equipment": equipment_result,
                "electrical": electrical_result,
                "control": control_result,
                "mechanical": mechanical_result
            }
        }

    def analyze_page_fast(self, page_text: str, page_number: int, document_name: str) -> Dict:
        """
        Fast single-pass analysis for when full multi-agent analysis is too slow.
        Uses a comprehensive single prompt instead of multiple agents.
        """
        if not self._has_llm():
            return {"analysis": "", "equipment": [], "relationships": []}

        if not page_text or len(page_text.strip()) < 50:
            return {"analysis": "Page has minimal text content", "equipment": [], "relationships": []}

        text_to_analyze = page_text[:10000] if len(page_text) > 10000 else page_text

        prompt = f"""You are an expert engineer analyzing electrical/mechanical drawings. Extract ALL information from this page.

Document: {document_name}
Page: {page_number}

Page Content:
---
{text_to_analyze}
---

Extract and respond with this JSON structure:
{{
    "summary": "Brief description of the page content",
    "equipment": [
        {{"tag": "VFD-101", "type": "VFD", "description": "Variable frequency drive", "specs": "50HP 480V"}}
    ],
    "electrical_connections": [
        {{"source": "MCC-1", "target": "VFD-101", "type": "FEEDS", "breaker": "BKR-15", "wire": "#10 AWG", "voltage": "480V"}}
    ],
    "control_connections": [
        {{"controller": "PLC-1", "device": "VFD-101", "io_type": "AO", "signal": "4-20mA", "function": "Speed command"}}
    ],
    "mechanical_connections": [
        {{"upstream": "P-101", "downstream": "HX-101", "type": "PIPE", "size": "4 inch", "medium": "CHW"}}
    ],
    "interlocks": [
        {{"trigger": "PSH-101", "action": "Trips P-101", "type": "SAFETY"}}
    ]
}}

Be thorough - extract ALL equipment tags, wire numbers, pipe sizes, control signals, and relationships visible on this page."""

        try:
            start_time = time.time()
            response = self._call_llm(prompt, max_tokens=3000)
            result = self._parse_json_response(response)

            # Convert to standard format
            equipment_tags = []
            equipment_details = []
            relationships = []
            detailed_connections = []

            for eq in result.get("equipment", []):
                if isinstance(eq, dict):
                    tag = eq.get("tag", "")
                    if tag:
                        equipment_tags.append(tag)
                        equipment_details.append(eq)

            # Process connections
            for conn in result.get("electrical_connections", []):
                src, tgt = conn.get("source", ""), conn.get("target", "")
                if src and tgt:
                    relationships.append(f"{src} feeds {tgt}")
                    detailed_connections.append({
                        "source": src, "target": tgt,
                        "category": "ELECTRICAL",
                        "connection_type": conn.get("type", "FEEDS"),
                        "details": conn
                    })

            for conn in result.get("control_connections", []):
                ctrl, dev = conn.get("controller", ""), conn.get("device", "")
                if ctrl and dev:
                    relationships.append(f"{ctrl} controls {dev}")
                    detailed_connections.append({
                        "source": ctrl, "target": dev,
                        "category": "CONTROL",
                        "connection_type": conn.get("io_type", ""),
                        "details": conn
                    })

            for conn in result.get("mechanical_connections", []):
                up, down = conn.get("upstream", ""), conn.get("downstream", "")
                if up and down:
                    relationships.append(f"{up} connects to {down}")
                    detailed_connections.append({
                        "source": up, "target": down,
                        "category": "MECHANICAL",
                        "connection_type": conn.get("type", "PIPE"),
                        "details": conn
                    })

            for intlk in result.get("interlocks", []):
                trigger = intlk.get("trigger", "")
                action = intlk.get("action", "")
                if trigger:
                    relationships.append(f"{trigger} {action}")

            elapsed = time.time() - start_time
            print(f"[AI] Page {page_number} fast-analyzed in {elapsed:.1f}s | {len(equipment_tags)} equipment | {len(relationships)} relationships")

            return {
                "analysis": result.get("summary", ""),
                "equipment": equipment_tags,
                "equipment_details": equipment_details,
                "relationships": relationships,
                "detailed_connections": detailed_connections
            }

        except Exception as e:
            logger.error(f"Fast analysis error on page {page_number}: {e}")
            return {"analysis": f"Analysis failed: {str(e)}", "equipment": [], "relationships": []}

    def generate_document_summary(self, page_analyses: List[Dict], document_name: str) -> str:
        """Generate an overall document summary from all page analyses"""
        if not self._has_llm():
            return ""

        # Collect all equipment and connections
        all_equipment = set()
        all_connections = []
        page_summaries = []

        for i, analysis in enumerate(page_analyses):
            if analysis.get("equipment"):
                all_equipment.update(analysis["equipment"])
            if analysis.get("analysis"):
                page_summaries.append(f"Page {i+1}: {analysis['analysis']}")
            if analysis.get("detailed_connections"):
                all_connections.extend(analysis["detailed_connections"])

        if not page_summaries:
            return ""

        # Count connection types
        elec_conns = [c for c in all_connections if c.get("category") == "ELECTRICAL"]
        ctrl_conns = [c for c in all_connections if c.get("category") == "CONTROL"]
        mech_conns = [c for c in all_connections if c.get("category") == "MECHANICAL"]

        prompt = f"""Based on the analysis of an electrical/mechanical drawing document, provide a comprehensive summary.

Document: {document_name}

Page Summaries:
{chr(10).join(page_summaries[:30])}

Equipment Found ({len(all_equipment)} items):
{', '.join(sorted(all_equipment)[:50])}

Connection Summary:
- Electrical connections: {len(elec_conns)}
- Control connections: {len(ctrl_conns)}
- Mechanical connections: {len(mech_conns)}

Provide a 2-3 paragraph summary covering:
1. What this document contains and its purpose
2. The main systems and equipment covered
3. Key relationships and connections between components
4. Notable control strategies or power distribution schemes"""

        try:
            print(f"[AI] Generating comprehensive document summary...")
            start_time = time.time()
            summary = self._call_llm(prompt, max_tokens=1024)
            elapsed = time.time() - start_time
            print(f"[AI] Document summary generated in {elapsed:.1f}s")
            return summary
        except Exception as e:
            logger.error(f"Document summary error: {e}")
            return ""


# Singleton instance
ai_analysis_service = AIAnalysisService()
