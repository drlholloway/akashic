"""Short descriptions for the parts index, one scheme per category: 'Dual JFET-Input Op-Amp DIP-8 /
SOIC-8', '100 kΩ Log (A) Potentiometer', '50 kΩ Trimmer 3362P', 'SPDT On-Off-On Toggle', 'Vactrol (LED +
LDR)', '500 mH Inductor', 'Audio Transformer 10 kΩ CT : 600 Ω CT', '32.768 kHz Crystal'. Transistors and
diodes have their own (transistors.describe, diodes.describe). What a part is comes from its number or
value; a detail that is not certain (a package, a taper) is left out rather than guessed."""
from __future__ import annotations

import re

from .normalize import _parse_si

# --- ICs ----------------------------------------------------------------------------------------------
# (pattern on the number with any maker prefix removed, description, packages: through-hole first, then
# surface mount). A number carries its package in the maker's suffix (TL072CP is DIP, TL072CD SOIC); with
# no suffix both are listed.
_D8, _D14, _D16 = ("DIP-8", "SOIC-8"), ("DIP-14", "SOIC-14"), ("DIP-16", "SOIC-16")
_OPAMP = [  # (number pattern, channels, input type)
    (r"TL0[5-8]1", "Single", "JFET"), (r"TL0[5-8]2", "Dual", "JFET"), (r"TL0[5-8]4", "Quad", "JFET"),
    (r"LF35[16]", "Single", "JFET"), (r"LF353|LF412", "Dual", "JFET"), (r"LF347", "Quad", "JFET"),
    (r"OPA2134|OPA2604|AD712|OPA2132", "Dual", "JFET"), (r"OPA134|OPA604", "Single", "JFET"), (r"TLE207[14]", "Quad", "JFET"),
    (r"4558|4559|4580|1458|LM833|NE5532|MC3317[28]|M5218|UPC4570|4570|LM4562|LM358|LM258|2904|TL022|747", "Dual", "BJT"),
    (r"4560|4565|3404A|5558|M5216|TA75558|LA6358|LT1013", "Dual", "BJT"), (r"BA718", "Dual", "BJT"), (r"TL044", "Quad", "BJT"),
    (r"4741|LM348|2902|MC3307[49]|3317[49]|TL974", "Quad", "BJT"),
    (r"17741|72741|741|748|NE5534|LM301A?|LM308|LM307|709|776|LT1012|TS321|OP-?0?7", "Single", "BJT"), (r"LM324|3403|4136|HA1457", "Quad", "BJT"),
    (r"OP275", "Dual", "JFET/BJT"),
    (r"TLC22[67]2|TLC272|TLC27M2|MCP602|OPA1678", "Dual", "CMOS"), (r"TLC27M4|LMC660|TLC2274", "Quad", "CMOS"),
    (r"AD823", "Dual", "JFET"), (r"LF444", "Quad", "JFET"),
    (r"CA3130|CA3140|3140", "Single", "MOSFET"), (r"CA3240|CA3260", "Dual", "MOSFET"),
]
_IC: list[tuple[str, str, tuple[str, ...]]] = [
    (r"LM13700|LM13600", "Dual OTA", _D16), (r"CA3080", "OTA", _D8), (r"CA3094", "OTA with Power Output", _D8),
    (r"BA6110", "Voltage-Controlled Amplifier", ("SIP-9",)),
    (r"TC1044S?|ICL7660|7660S?|7662B?C?|LTC1044|MAX1044|LTC1144", "Charge Pump Voltage Converter", _D8),
    (r"LT1054", "Charge Pump Voltage Converter", ("DIP-8", "SOIC-16")),
    (r"PT2399", "Echo Processor", ("DIP-16", "SOP-16")), (r"FV-?1", "Reverb and Multi-Effects DSP", ("SOIC-28",)),
    (r"MN3207|MN3007|BL3207|V3207", "1024-Stage BBD", ("DIP-8",)), (r"MN3208|MN3008|BL3208|V3208", "2048-Stage BBD", ("DIP-8",)),
    (r"MN3005|MN3205|V3205", "4096-Stage BBD", ("DIP-8",)), (r"MN3002", "512-Stage BBD", ("DIP-8",)),
    (r"SAD-?1024A?", "Dual 512-Stage BBD", ("DIP-16",)), (r"SAD512", "512-Stage BBD", ("DIP-8",)),
    (r"MN310[12]|BL310[12]|V3102|CT3101", "BBD Clock Driver", ("DIP-8",)),
    (r"NE57[01]|SA571", "Compandor", _D16), (r"LM386", "Audio Power Amplifier", _D8),
    (r"NE555|LM555|L555", "Timer", _D8), (r"ICM7555|TLC555|7555", "CMOS Timer", _D8), (r"NE556", "Dual Timer", _D14),
    (r"(?:LM)?311", "Comparator", _D8), (r"(?:LM)?393", "Dual Comparator", _D8), (r"(?:LM)?339", "Quad Comparator", _D14),
    (r"LM319", "Dual High-Speed Comparator", _D14), (r"LM3900|MC3401", "Quad Norton Amplifier", _D14),
    (r"XR2206", "Function Generator", _D16), (r"I?C?L?8038", "Waveform Generator", ("DIP-14",)),
    (r"(?:CA|LM)?3046|(?:CA)?3086", "NPN Transistor Array", _D14), (r"MPQ3904", "Quad NPN Transistor Array", ("DIP-14",)), (r"CA3019", "Diode Array", ("DIP-14",)), (r"27C?64", "64 Kbit EPROM", ("DIP-28",)), (r"AD633", "Analog Multiplier", _D8),
    (r"(?:LM|MC)?1496H", "Balanced Modulator", ("TO-100",)), (r"(?:LM|MC)?1496", "Balanced Modulator", _D14), (r"(?:LM|NE)?567", "Tone Decoder", _D8), (r"(?:MC)?1495", "Analog Multiplier", ("DIP-14",)),
    (r"LM3914", "Bar/Dot Display Driver", ("DIP-18",)), (r"(?:CEM)?3340", "VCO", ("DIP-16",)),
    (r"24LC32A?", "32 Kbit I2C EEPROM", _D8), (r"ATTINY85", "8-bit Microcontroller", _D8),
    (r"PIC12F675", "8-bit Microcontroller", _D8), (r"TLP222[AG]?", "Photo-MOSFET Relay", ("DIP-4",)),
    (r"BTDR-?[23]H?", "Digital Reverb Module", ()), (r"723", "Adjustable Voltage Regulator", _D14),
    # regulators and references the regulator rule does not cover
    (r"LM317T?", "Adjustable Positive Regulator", ("TO-220",)), (r"LM336", "2.5 V Shunt Reference", ("TO-92",)),
    (r"LM336Z?-5\.0", "5 V Shunt Reference", ("TO-92",)), (r"LM329(?:CZ)?", "6.9 V Precision Reference", ("TO-92",)),
    (r"TL431", "Adjustable Shunt Regulator", ("TO-92", "SOT-23")), (r"TL431(?:C|A|I)?LP", "Adjustable Shunt Regulator", ("TO-92",)),
    (r"RC4195", "±15 V Dual Tracking Regulator", ()), (r"TA7179P?", "±15 V Dual Tracking Regulator", ("DIP-14",)),
    (r"I[AE]B?0[15]\d{2}[SD]\d*|A0512S\w*", "Isolated DC/DC Converter", ()),
    # audio
    (r"LM1875T?", "Audio Power Amplifier", ("TO-220",)), (r"LM3886T?", "Audio Power Amplifier", ()),
    (r"TDA2030A?", "Audio Power Amplifier", ("TO-220",)), (r"TDA2822M?", "Dual Low-Voltage Audio Power Amplifier", ("DIP-8",)),
    (r"TDA7052", "BTL Audio Power Amplifier", ("DIP-8",)), (r"LM384", "5 W Audio Power Amplifier", ("DIP-14",)),
    (r"LM390", "1 W Battery Audio Power Amplifier", ("DIP-14",)), (r"LM381", "Dual Low-Noise Preamplifier", ("DIP-14",)),
    (r"LM387", "Dual Low-Noise Preamplifier", ("DIP-8",)), (r"(?:NE)?572", "Dual Compandor", _D16),
    (r"TA7136A?P", "Low-Noise Preamplifier", ("SIP-7",)), (r"BA662[AB]?", "OTA with Buffer", ()),
    (r"M5207L01", "Dual Linear-Control VCA", ()), (r"M51134P?", "Bass Sub-Harmonizer", ("DIP-20",)),
    (r"BA3812L", "5-Band Graphic Equalizer", ()), (r"BA634", "T Flip-Flop", ("SIP-5",)), (r"BA6124", "5-Dot LED Level Meter Driver", ()),
    (r"M51951A", "Voltage Detector and Reset", ("TO-92",)),
    (r"SSM2166", "Microphone Preamplifier with Compressor", _D14),
    (r"(?:THAT)?218[01]", "Voltage-Controlled Amplifier", ("SIP-8", "SOIC-8")), (r"(?:THAT)?2159", "Voltage-Controlled Amplifier", ("SIP-8",)),
    (r"THAT4301(?:RETROFIT)?", "Analog Engine (VCA, RMS Detector and Op-Amps)", _D16),
    (r"(?:CEM)?3360", "Dual VCA", ("DIP-14",)), (r"(?:CEM)?3310", "Envelope Generator", ("DIP-16",)), (r"CEM3320", "VCF", ("DIP-18",)),
    (r"(?:NE|LM)?566(?:CN)?", "VCO", ("DIP-8",)), (r"LM565(?:CN)?", "Phase-Locked Loop", ("DIP-14",)),
    (r"LF398", "Sample-and-Hold", _D8), (r"CS4330", "Stereo Audio DAC", ("SOIC-8",)), (r"CS5330", "Stereo Audio ADC", ("SOIC-8",)),
    (r"TAPLFO3?", "Tap-Tempo LFO", ("DIP-8",)), (r"RC4200", "Analog Multiplier", ("DIP-8",)),
    (r"LM394", "Matched NPN Transistor Pair", ()), (r"TL60[14]", "Analog Switch", ("DIP-8",)),
    (r"ULN2003A?", "Darlington Array", _D16), (r"SN7647[7]", "Complex Sound Generator", ("DIP-28",)),
    (r"SN76488(?:NF?)?", "Complex Sound Generator", ("DIP-16",)), (r"ZXCT1041", "Current Monitor", ("SOT-23-5",)),
    (r"6N138", "Darlington Optocoupler", ("DIP-8",)), (r"H11F1", "Photo-FET Optocoupler", ("DIP-6",)),
    # delay
    (r"MN3204", "512-Stage Low-Voltage BBD", ("DIP-8",)), (r"MN3001", "Dual 512-Stage BBD", ()), (r"MN3209", "256-Stage BBD", ()),
    (r"MN3011", "Multi-Tap 3328-Stage BBD", ()), (r"TDA1022", "512-Stage BBD", ("DIP-16",)),
    (r"M65831A?P?", "Digital Echo", ("DIP-24",)), (r"M50195P?", "Digital Echo", ()), (r"M50198P?", "Single-Chip Digital Delay", ()), (r"HT8955A?", "Digital Echo (Voice Delay)", ("DIP-24",)),
    (r"HT8950A", "Voice Modulator (Pitch Shift, Robot, Vibrato)", ("DIP-16",)), (r"HT8950", "Voice Modulator (Pitch Shift, Robot, Vibrato)", ("DIP-18",)),
    (r"ISD(?:25\d{2,3}|17\d{3}|1820|100A)", "Voice Record/Playback", ()), (r"APR9301(?:V2)?", "Voice Record/Playback", ()),
    # converters, memory, processors
    (r"DAC-?08|DAC080[07]", "8-bit DAC", ("DIP-16",)), (r"TLC7528(?:CN)?", "Dual 8-bit DAC", ("DIP-20",)),
    (r"ADC080[4]", "8-bit ADC", ("DIP-20", "SOIC-20")), (r"ADC080[89]", "8-bit ADC with 8-Channel Multiplexer", ("DIP-28",)),
    (r"ADC0820", "8-bit ADC", ("DIP-20",)),
    (r"(?:MCP)?41100", "Digital Potentiometer", _D8), (r"MCP4251", "Dual Digital Potentiometer", ("DIP-14",)), (r"AD5220", "Digital Potentiometer", _D8),
    (r"27C?16", "16 Kbit EPROM", ("DIP-24",)), (r"27C?32", "32 Kbit EPROM", ("DIP-24",)),
    (r"6116(?:LP)?", "16 Kbit SRAM", ("DIP-24",)), (r"6264", "64 Kbit SRAM", ("DIP-28",)), (r"23LC1024", "1 Mbit SPI SRAM", _D8),
    (r"MK4116|4116", "16 Kbit DRAM", ("DIP-16",)), (r"4164", "64 Kbit DRAM", ("DIP-16",)), (r"41256", "256 Kbit DRAM", ("DIP-16",)),
    (r"4464(?:-\d+)?", "256 Kbit DRAM", ("DIP-18",)), (r"M5M4246AP?(?:-\d+)?", "256 Kbit DRAM", ()), (r"93C46", "1 Kbit Microwire EEPROM", _D8),
    (r"PIC12F509", "8-bit Microcontroller", _D8), (r"PIC10F202", "8-bit Microcontroller", ("DIP-8", "SOT-23-6")),
    (r"(?:PIC)?16F68[48]", "8-bit Microcontroller", ("DIP-14", "SOIC-14")), (r"(?:PIC)?16F84A?(?:-04)?", "8-bit Microcontroller", ("DIP-18",)),
    (r"ATTINY13A?", "8-bit Microcontroller", _D8), (r"AVR(?:32|64|128)DB28", "8-bit Microcontroller", ("DIP-28", "SOIC-28", "SSOP-28")), (r"ATTINY841(?:-SSU)?", "8-bit Microcontroller", ("SOIC-14",)), (r"ATTINY84A?", "8-bit Microcontroller", ("DIP-14", "SOIC-14")),
    (r"ATTINY412(?:-SSNR?)?", "8-bit Microcontroller", ("SOIC-8",)),
    (r"ATMEGA328P?(?:-PU)?", "8-bit Microcontroller", ("DIP-28",)), (r"ESP32-?C3", "32-bit Wi-Fi Microcontroller", ()),
    (r"68B09", "8-bit Microprocessor", ("DIP-40",)), (r"Z-?80A?", "8-bit Microprocessor", ("DIP-40",)),
    (r"68B50", "Serial Interface (ACIA)", ("DIP-24",)), (r"8253(?:-5)?|8254|82C53", "Programmable Interval Timer", ("DIP-24",)),
]
_CMOS = {  # CD4000 logic: number -> function and pin count
    "4001": ("Quad 2-Input NOR", 14), "4007": ("Dual Complementary Pair and Inverter", 14), "4009": ("Hex Inverting Buffer", 16),
    "4011": ("Quad 2-Input NAND", 14), "4013": ("Dual D Flip-Flop", 14), "4015": ("Dual 4-Stage Shift Register", 16),
    "4016": ("Quad Bilateral Switch", 14), "4017": ("Decade Counter", 16), "4022": ("Octal Counter", 16),
    "4024": ("7-Stage Binary Counter", 14), "4027": ("Dual JK Flip-Flop", 16), "4040": ("12-Stage Binary Counter", 16),
    "4046": ("Phase-Locked Loop", 16), "4047": ("Monostable/Astable Multivibrator", 14), "4049": ("Hex Inverting Buffer", 16),
    "4050": ("Hex Buffer", 16), "4051": ("8-Channel Analog Multiplexer", 16), "4052": ("Dual 4-Channel Analog Multiplexer", 16),
    "4053": ("Triple 2-Channel Analog Multiplexer", 16), "4060": ("14-Stage Counter and Oscillator", 16),
    "4066": ("Quad Bilateral Switch", 14), "4069": ("Hex Inverter", 14), "4070": ("Quad XOR", 14),
    "4093": ("Quad 2-Input NAND Schmitt Trigger", 14), "40106": ("Hex Schmitt Trigger Inverter", 14),
    "4006": ("18-Stage Shift Register", 14), "4012": ("Dual 4-Input NAND", 14), "4030": ("Quad XOR", 14),
    "4042": ("Quad D Latch", 16), "4077": ("Quad XNOR", 14), "4081": ("Quad 2-Input AND", 14),
    "4098": ("Dual Monostable Multivibrator", 16), "40109": ("Quad Level Shifter", 16), "40174": ("Hex D Flip-Flop", 16),
    "4503": ("Hex 3-State Buffer", 16), "4504": ("Hex Level Shifter", 16), "4517": ("Dual 64-Stage Shift Register", 16),
    "4520": ("Dual Binary Counter", 16), "4526": ("Programmable Divide-by-N Counter", 16), "4555": ("Dual 1-of-4 Decoder", 16),
    "4584": ("Hex Schmitt Trigger Inverter", 14),
}
_TTL = {  # 74-series logic: number -> function and pin count
    "00": ("Quad 2-Input NAND", 14), "04": ("Hex Inverter", 14), "U04": ("Unbuffered Hex Inverter", 14), "08": ("Quad 2-Input AND", 14),
    "14": ("Hex Schmitt Trigger Inverter", 14), "32": ("Quad 2-Input OR", 14), "74": ("Dual D Flip-Flop", 14),
    "157": ("Quad 2-Input Multiplexer", 16), "174": ("Hex D Flip-Flop", 16), "195": ("4-Bit Shift Register", 16),
    "374": ("Octal D Flip-Flop", 20), "4040": ("12-Stage Binary Counter", 16),
    "02": ("Quad 2-Input NOR", 14), "07": ("Hex Open-Collector Buffer", 14), "26": ("Quad 2-Input High-Voltage NAND", 14),
    "42": ("BCD-to-Decimal Decoder", 16), "45": ("BCD-to-Decimal Decoder/Driver", 16), "51": ("Dual AND-OR-Invert", 14),
    "93": ("4-Bit Binary Counter", 14), "138": ("3-to-8 Line Decoder", 16), "139": ("Dual 2-to-4 Line Decoder", 16),
    "161": ("4-Bit Binary Counter", 16), "164": ("8-Bit Shift Register", 14), "221": ("Dual Monostable Multivibrator", 16),
    "238": ("3-to-8 Line Decoder", 16), "244": ("Octal Buffer", 20), "245": ("Octal Bus Transceiver", 20),
    "259": ("8-Bit Addressable Latch", 16), "273": ("Octal D Flip-Flop", 20), "367": ("Hex 3-State Buffer", 16),
    "574": ("Octal D Flip-Flop", 20), "595": ("8-Bit Shift Register with Output Latch", 16),
    "4053": ("Triple 2-Channel Analog Multiplexer", 16), "4511": ("BCD-to-7-Segment Decoder/Driver", 16),
    "925": ("4-Digit Counter with Display Driver", 16), "628": ("Voltage-Controlled Oscillator", 14), "373": ("Octal D Latch", 20),
}
_DIP_SUFFIX = re.compile(r"(?:C?P|C?N|AP|ACN|IN|PN|PU|PA|E|EZ|BP|CPD|CCPD|N8|CN8)(?:-\d+)?$")
_SO_SUFFIX = re.compile(r"(?:C?D|DR|M|MX|DT|SO|S8|CSO|SW)$")


def _packages(rest: str, pkgs: tuple[str, ...], jrc: bool) -> str:
    """The package a maker's suffix names, else every package the part comes in."""
    if not pkgs:
        return ""
    if len(pkgs) > 1 and rest:
        if jrc and re.fullmatch(r"D|DD", rest):
            return pkgs[0]  # JRC: NJM4558D is the DIP, NJM4558M the SOIC
        if _DIP_SUFFIX.search(rest):
            return pkgs[0]
        if _SO_SUFFIX.search(rest):
            return pkgs[1]
    return " / ".join(pkgs)


def _regulator(p: str) -> str:
    if m := re.fullmatch(r"LM2940(?:C?T)?(?:-(\d+))?", p):
        return f"{m.group(1) + ' V ' if m.group(1) else ''}1 A Low-Dropout Positive Regulator{' TO-220' if 'T' in p[6:] else ''}"
    if m := re.fullmatch(r"(?:LM)?340(L|LA|T)-?(\d\d)", p):
        low = m.group(1).startswith("L")
        return f"{int(m.group(2))} V {'100 mA' if low else '1 A'} Positive Regulator {'TO-92' if low else 'TO-220'}"
    sot89 = p.endswith("-AB3-R")  # UTC's SOT-89 code
    p = re.sub(r"G?-AB3-R$", "", p)
    m = re.fullmatch(r"(?:L|LM|UA|MC|KA|NJM|UPC|KIA)?(7[89])([LM]?)(\d\d)(?:[A-Z]{0,3}\d?)?(?:-[\d.]+)?", p)
    if not m or not (2 <= int(m.group(3)) <= 24 or m.group(3) == "33"):
        m2 = re.fullmatch(r"(?:LM)?340K?-?(\d\d)", p)
        return f"{int(m2.group(1))} V 1.5 A Positive Regulator TO-3" if m2 and "K" in p else ""
    v, low = int(m.group(3)), m.group(2) == "L"
    v_txt = "3.3 V" if v == 33 else f"{v} V"
    sign = "Positive" if m.group(1) == "78" else "Negative"
    pkg = "TO-92 / SOT-89" if low else "TO-220"
    if low and p.rstrip("A").endswith("Z"):
        pkg = "TO-92"
    if sot89:
        pkg = "SOT-89"
    amps = "100 mA" if low else "500 mA" if m.group(2) == "M" else "1 A"
    return f"{v_txt} {amps} {sign} Regulator {pkg}"


_IC_ALIASES = {  # numbers drawn wrong on a source schematic, described as the part meant
    "M5281AL": "M5218AL",  # Boss TR-2: IC2A is labelled M5216AL and B/C M5281AL; the TR-2 uses M5218AL op-amps
    "M5616L": "M5216L",    # Boss HM-2 redraw: IC1 M5216L, IC2/IC3 M5616L
}


def describe_ic(value: str) -> str:
    v = re.sub(r"\s+", "", value.upper())
    v = _IC_ALIASES.get(v, v)
    v = re.sub(r"^(?:TL)-(?=\d)", "TL", v)  # 'TL-082'
    if r := _regulator(v):
        return r
    jrc = v.startswith(("JRC", "NJM"))
    p = re.sub(r"^(?:JRC|NJM|KIA|KA|HA|UPC|UPD|UA|MC|LM|NE|SA|RC|CA|AD|IC|TC|ICL|LT|LTC)(?=\d)", "", v)  # maker prefixes on bare numbers
    p = re.sub(r"^HD14(\d{3})|^MC14(\d{3})|^14(0\d\d)(?=[A-Z]|$)", lambda m: "CD4" + (m.group(1) or m.group(2) or m.group(3)), p)
    for num, ch, inp in _OPAMP:
        for cand in (v, p):
            m = re.match(rf"(?:[A-Z]{{0,4}})?({num})(.*)$", cand)
            if m and (m.start(1) == 0 or cand[:m.start(1)].isalpha()):
                pkgs = _D14 if ch == "Quad" or num == "747" else _D8
                rest = m.group(2)
                if (jrc or cand.startswith("M5")) and pkgs == _D8 and re.fullmatch(r"A?L", rest):
                    return f"{ch} {inp}-Input Op-Amp SIP-8"  # Mitsubishi M5218L, JRC NJM4558L: L is the single-in-line package
                if cand.startswith("BA718"):
                    return f"{ch} {inp}-Input Op-Amp SIP-9"
                if num == "TL044":
                    return f"{ch} Low-Power {inp}-Input Op-Amp DIP-16"  # two supply pairs, so 16 pins
                if cand.startswith("M5") and re.fullmatch(r"A?", rest):
                    return f"{ch} {inp}-Input Op-Amp DIP-8 / SIP-8 / SOIC-8"  # Mitsubishi made each in all three
                if cand.startswith("M5") and re.fullmatch(r"A?FP", rest):
                    return f"{ch} {inp}-Input Op-Amp SOIC-8"  # M5218AFP
                return f"{ch} {inp}-Input Op-Amp {_packages(rest, pkgs, jrc)}".strip()
    m = re.fullmatch(r"(?:CD|HEF|MC1)?(4[05]\d{2,3})(UB|B|BE|BCN|BM|BF|BP)?(.*)", p)
    if m and m.group(1) in {k for k in _CMOS} | {"4069", "4049"}:
        fn, pins = _CMOS[m.group(1)]
        unb = "Unbuffered " if m.group(2) == "UB" and m.group(1) == "4069" else ""
        return f"CMOS {unb}{fn} {_packages(m.group(3) or (m.group(2) or '')[1:], (f'DIP-{pins}', f'SOIC-{pins}'), False)}"
    fam = num = rest = ""
    if m := re.fullmatch(r"(?:SN|MM|DM)?74(LS|HC|HCT|AC|ACT|C|F|ALS|LV|S|L)?(U?\d{2,4})(.*)", v):
        fam, num, rest = "74" + (m.group(1) or ""), m.group(2), m.group(3)
    elif m := re.fullmatch(r"(LS|HC)(\d{2,3})(.*)", v):  # 'LS174': the 74 left off
        fam, num, rest = "74" + m.group(1), m.group(2), m.group(3)
    elif m := re.fullmatch(r"(?:TC)?40H0?(\d{2,3})(.*)", v):  # Toshiba's TC40H000 is a 74HC00
        fam, num, rest = "TC40H", m.group(1), m.group(2)
    if num in _TTL:
        fn, pins = _TTL[num]
        return f"{fam} {fn} {_packages(rest, (f'DIP-{pins}', f'SOIC-{pins}'), False)}"
    for num, fn, pkgs in _IC:  # noqa: B007
        for cand in (v, p):
            m = re.fullmatch(rf"(?:[A-Z]{{0,4}})?({num})([A-Z0-9-]*)", cand)
            if m:
                return f"{fn} {_packages(m.group(2), pkgs, jrc)}".strip()
    return ""


# --- pots and trimmers ----------------------------------------------------------------------------------
_TAPER = {"A": "Log (A)", "B": "Linear (B)", "C": "Reverse Log (C)", "W": "W-Taper", "G": "G-Taper", "D": "D-Taper"}


def _ohms(n: float) -> str:
    for div, unit in ((1e6, "MΩ"), (1e3, "kΩ"), (1, "Ω")):
        if n >= div:
            x = n / div
            return f"{x:g} {unit}"
    return f"{n:g} Ω"


def describe_pot(value: str, types: list[str]) -> str:
    m = re.fullmatch(r"([ABCWGD]?)(\d+(?:[.,]\d+)?)\s*([kKmM]?)", value.strip())
    if not m:
        return ""
    n = _parse_si(m.group(2).replace(",", ".") + {"k": "k", "K": "k", "m": "M", "M": "M"}.get(m.group(3), ""))
    if not n:
        return ""
    dual = bool(types) and bool(re.search(r"\bdual\b|\bstereo\b|gang", types[0], re.I))  # the most common listing only
    taper = _TAPER.get(m.group(1).upper(), "")
    return " ".join(x for x in (_ohms(n), taper, "Dual-Gang" if dual else "", "Potentiometer") if x)


def describe_trim(value: str, types: list[str]) -> str:
    m = re.fullmatch(r"[ABCW]?(\d+(?:[.,]\d+)?)\s*([kKmM]?)", value.strip())  # '100KB' on a service sheet: the taper is immaterial
    if not m:
        return ""
    n = _parse_si(m.group(1).replace(",", ".") + {"k": "k", "K": "k", "m": "M", "M": "M"}.get(m.group(2), ""))
    if not n:
        return ""
    return f"{_ohms(n)} Trimmer"  # the model (3362P, multi-turn) differs from board to board


# --- switches -------------------------------------------------------------------------------------------
def describe_switch(value: str, types: list[str]) -> str:
    v = value.upper().replace(" ", "")
    m = re.match(r"^(SP|DP|3P|4P|[1-6]P)(ST|DT|[2-9]T)", v)
    if not m:
        return ""
    poles = {"SP": "SP", "DP": "DP", "1P": "SP", "2P": "DP"}.get(m.group(1), m.group(1))
    throws = m.group(2)
    name = poles + throws
    t = (types[0] if types else "").lower()  # the most common listing: others may be a different switch of the same poles
    pos = re.search(r"\(?ON\)?-?OFF-?\(?ON\)?|ON-?ON-?ON|ON-?ON|ON-?OFF", v + " " + t.upper())
    pos_txt = ""
    if pos:
        p = pos.group(0).replace("(", "").replace(")", "")
        p = re.sub(r"ON-?OFF-?ON", "On-Off-On", p, flags=re.I)
        p = re.sub(r"ON-?ON-?ON", "On-On-On", p, flags=re.I)
        p = re.sub(r"ON-?ON", "On-On", p, flags=re.I)
        p = re.sub(r"ON-?OFF", "On-Off", p, flags=re.I)
        pos_txt = p
    if "rotary" in t:
        kind = "Rotary"
    elif "slide" in t:
        kind = "Slide"
    elif re.search(r"stomp|foot", t):
        kind = "Footswitch"
    elif "toggle" in t:
        kind = "Toggle"
    elif name in ("3PDT", "4PDT"):
        kind = "Footswitch"
    elif throws in ("ST", "DT") and name in ("SPST", "SPDT", "DPST", "DPDT"):
        kind = "Toggle"
    elif re.fullmatch(r"[4-9]T", throws):
        kind = "Rotary"
    else:
        kind = "Switch"
    if kind == "Rotary":
        pos_txt = ""
    return " ".join(x for x in (name, pos_txt, kind) if x)


# --- optos ----------------------------------------------------------------------------------------------
_LDR_SPECS = {"GL5516": "5-10 kΩ light 0.5 MΩ dark", "GL5528": "10-20 kΩ light 1 MΩ dark", "GL5537-1": "20-30 kΩ light 2 MΩ dark",
              "GL5537-2": "30-50 kΩ light 3 MΩ dark", "GL5539": "50-100 kΩ light 5 MΩ dark", "GL5549": "100-200 kΩ light 10 MΩ dark"}


def describe_opto(value: str, types: list[str]) -> str:
    v = value.upper().replace(" ", "")
    if re.match(r"^VTL5C\d", v) or v == "VACTROL":
        return "Vactrol (LED + LDR)"
    if re.match(r"^NSL-?32", v):
        return "Optocoupler (LED + LDR)"
    if re.match(r"^CLM6000", v):
        return "Optocoupler (LED + LDR)"
    if re.match(r"^H11F[123]", v):
        return "Photo-FET Optocoupler DIP-6"
    if re.match(r"^6N13[89]", v):
        return "Darlington Optocoupler DIP-8"
    if re.match(r"^CPC1017", v):
        return "Solid-State Relay SOP-4"
    if v in _LDR_SPECS:
        return f"LDR (Photoresistor) {_LDR_SPECS[v]}"
    if re.match(r"^(?:LDR\d*|GL55\d\d|PDV-P\d+|NSL-19|KE-?10720)", v):
        return "LDR (Photoresistor)"
    return ""


# --- inductors, transformers, crystals ------------------------------------------------------------------
def describe_inductor(value: str, types: list[str]) -> str:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(?:-(\d+(?:\.\d+)?))?\s*([UMN]?)H", value.upper().replace("Μ", "U"))
    if not m:
        return ""
    unit = {"U": "µH", "M": "mH", "N": "nH", "": "H"}[m.group(3)]
    val = f"{m.group(1)}-{m.group(2)}" if m.group(2) else f"{float(m.group(1)):g}"
    return f"{val} {unit} {'Adjustable ' if m.group(2) else ''}Inductor"


_XFM = {"42TL019": "10 kΩ CT : 600 Ω CT", "42TM022": "1.5 kΩ CT : 600 Ω CT", "LT44": "20 kΩ : 1 kΩ CT"}


def describe_transformer(value: str, types: list[str]) -> str:
    v = re.sub(r"\s+.*$", "", value.upper())
    base = re.sub(r"(?:-?RC|-R|T)$", "", v)
    if base in _XFM:
        return f"Audio Transformer {_XFM[base]}"
    if re.match(r"^(?:42T[LM]\d{3}|TY-?\d{3}P?|OEP\d|LT\d\d|LM-NP)", v):
        return "Audio Transformer"
    return ""


def describe_crystal(value: str, types: list[str]) -> str:
    v = value.upper()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(K|M)HZ", v)
    if not m and re.match(r"^DT-?38$", v) and any("32.768" in t for t in types):
        m = re.match(r"(32.768)(K)", "32.768K")
    if not m:
        return ""
    cyl = " Cylinder" if re.search(r"AB38T|DT-?38", v) else ""
    return f"{m.group(1)} {m.group(2).lower() if m.group(2) == 'K' else 'M'}Hz Crystal{cyl}"


def describe(category: str, value: str, types: list[str]) -> str:
    fn = {"IC": lambda v, t: describe_ic(v), "POT": describe_pot, "TRIM": describe_trim, "SW": describe_switch,
          "OPTO": describe_opto, "L": describe_inductor, "XFM": describe_transformer, "XTAL": describe_crystal}.get(category)
    return fn(value, types) if fn else ""
