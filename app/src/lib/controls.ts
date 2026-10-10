// Control names grouped across vendors' spellings, for searching and filtering by control.
// `names` are the spellings a group takes in (compared after `normalizeControl`); `syn` are the
// words a circuit with that control is also found by in the search box. Short or ambiguous
// spellings (HI, LO, INT, FB, MASTER...) map into a group but are not searched as synonyms.

export interface ControlGroup {
	label: string;
	names: string[];
	syn: string[];
}

export const CONTROL_GROUPS: ControlGroup[] = [
	{ label: 'Volume', names: ['VOLUME', 'VOL', 'LEVEL', 'LVL', 'OUTPUT', 'OUT', 'LOUD', 'LOUDNESS', 'MASTER', 'MASTER VOLUME', 'MASTER VOL', 'OUTPUT LEVEL'], syn: ['volume', 'vol', 'level', 'output', 'loud'] },
	{ label: 'Gain', names: ['GAIN', 'DRIVE', 'OVERDRIVE', 'DIST', 'DISTORTION', 'DIRT', 'CRUNCH', 'PRE-GAIN', 'PREGAIN', 'PRE GAIN'], syn: ['gain', 'drive', 'overdrive', 'distortion', 'dist', 'dirt'] },
	{ label: 'Fuzz', names: ['FUZZ'], syn: ['fuzz'] },
	{ label: 'Tone', names: ['TONE'], syn: ['tone'] },
	{ label: 'Treble', names: ['TREBLE', 'TREB', 'HIGH', 'HIGHS', 'HI', 'TOP'], syn: ['treble', 'treb', 'highs'] },
	{ label: 'Mid', names: ['MID', 'MIDS', 'MIDDLE', 'MIDRANGE'], syn: ['mid', 'mids', 'middle'] },
	{ label: 'Bass', names: ['BASS', 'LOW', 'LOWS', 'LO', 'BOTTOM'], syn: ['bass', 'lows'] },
	{ label: 'Presence', names: ['PRESENCE', 'PRES'], syn: ['presence', 'pres'] },
	{ label: 'Contour', names: ['CONTOUR', 'SCOOP'], syn: ['contour', 'scoop'] },
	{ label: 'Bright', names: ['BRIGHT', 'BRITE'], syn: ['bright'] },
	{ label: 'Cut', names: ['CUT', 'HI-CUT', 'HI CUT', 'HIGH CUT'], syn: ['cut'] },
	{ label: 'Boost', names: ['BOOST'], syn: ['boost'] },
	{ label: 'Bias', names: ['BIAS'], syn: ['bias'] },
	{ label: 'Starve', names: ['STARVE', 'SAG', 'VOLTAGE'], syn: ['starve', 'sag'] },
	{ label: 'Blend', names: ['BLEND', 'MIX', 'BALANCE', 'BAL', 'WET/DRY', 'DRY/WET'], syn: ['blend', 'mix', 'balance'] },
	{ label: 'Sustain', names: ['SUSTAIN', 'SUS', 'SUST'], syn: ['sustain'] },
	{ label: 'Compression', names: ['COMP', 'COMPRESSION', 'SQUEEZE', 'RATIO'], syn: ['comp', 'compression', 'ratio'] },
	{ label: 'Attack', names: ['ATTACK'], syn: ['attack'] },
	{ label: 'Release', names: ['RELEASE'], syn: ['release'] },
	{ label: 'Threshold', names: ['THRESHOLD', 'THRESH'], syn: ['threshold'] },
	{ label: 'Gate', names: ['GATE'], syn: ['gate'] },
	{ label: 'Rate', names: ['RATE', 'SPEED'], syn: ['rate', 'speed'] },
	{ label: 'Depth', names: ['DEPTH', 'DEP', 'INTENSITY', 'INT'], syn: ['depth', 'intensity'] },
	{ label: 'Width', names: ['WIDTH'], syn: ['width'] },
	{ label: 'Time', names: ['TIME', 'DELAY', 'DELAY TIME'], syn: ['time', 'delay'] },
	{ label: 'Repeats', names: ['FEEDBACK', 'FDBK', 'FDBACK', 'FB', 'REPEATS', 'REPEAT', 'REGEN', 'REGENERATION'], syn: ['feedback', 'repeats', 'regen', 'regeneration'] },
	{ label: 'Decay', names: ['DECAY', 'DWELL'], syn: ['decay', 'dwell'] },
	{ label: 'Sensitivity', names: ['SENSITIVITY', 'SENS'], syn: ['sensitivity', 'sens'] },
	{ label: 'Frequency', names: ['FREQ', 'FREQUENCY'], syn: ['freq', 'frequency'] },
	{ label: 'Resonance', names: ['RESONANCE', 'RES', 'PEAK', 'Q'], syn: ['resonance', 'peak'] },
	{ label: 'Filter', names: ['FILTER', 'FILT'], syn: ['filter'] },
	{ label: 'Octave', names: ['OCTAVE', 'OCT'], syn: ['octave'] },
	{ label: 'Clipping', names: ['CLIPPING', 'CLIP'], syn: ['clipping', 'clip'] },
	{ label: 'Wave', names: ['WAVE', 'SHAPE', 'WAVEFORM'], syn: ['wave', 'shape', 'waveform'] },
	{ label: 'Range', names: ['RANGE'], syn: ['range'] },
	{ label: 'Voice', names: ['VOICE', 'VOICING'], syn: ['voice', 'voicing'] },
	{ label: 'Input', names: ['INPUT', 'INPUT GAIN', 'IN'], syn: ['input'] },
	{ label: 'Body', names: ['BODY', 'FAT', 'WEIGHT'], syn: ['body', 'fat', 'weight'] },
	{ label: 'Clean', names: ['CLEAN', 'DRY'], syn: ['clean', 'dry'] },
	{ label: 'Sweep', names: ['SWEEP', 'MANUAL'], syn: ['sweep', 'manual'] },
	{ label: 'Color', names: ['COLOR', 'COLOUR'], syn: ['color', 'colour'] },
	{ label: 'Pitch', names: ['PITCH', 'TUNE', 'TUNING'], syn: ['pitch', 'tune'] }
];

const BY_NAME = new Map(CONTROL_GROUPS.flatMap((g) => g.names.map((n) => [n, g] as const)));

/** 'Vol 1' -> 'VOL', 'MODE (toggle switch)' -> 'MODE': a control as the group table spells it. */
export function normalizeControl(raw: string): string {
	return raw
		.toUpperCase()
		.replace(/\(.*?\)/g, '')
		.replace(/\s*\d+$/, '')
		.replace(/\s+/g, ' ')
		.trim();
}

/** The group a control belongs to ('Volume' for 'LEVEL'), or null. */
export function controlGroup(raw: string): ControlGroup | null {
	return BY_NAME.get(normalizeControl(raw)) ?? null;
}

/** The labels of the groups a circuit's controls fall in. */
export function controlLabels(controls: string[]): Set<string> {
	const out = new Set<string>();
	for (const c of controls) {
		const g = controlGroup(c);
		if (g) out.add(g.label);
	}
	return out;
}

/** Search text for a circuit's controls: each name as written, plus its group's synonyms. */
export function controlSearchText(controls: string[]): string {
	return controls
		.filter((c) => !/^\d+ knobs?$/i.test(c))
		.map((c) => [c, ...(controlGroup(c)?.syn ?? [])].join(' '))
		.join(' ');
}
