export type Vendor = 'pedalpcb' | 'aionfx' | 'madbean' | 'guitarpcb' | 'fuzzdog' | 'sheepylove' | 'deadendfx';

export interface IndexEntry {
	id: string;
	file_id: string;
	vendor: Vendor;
	name: string;
	subtitle: string;
	based_on: string;
	category: string;
	effect_type: string;
	enclosure: string;
	difficulty: string;
	price: number | null;
	currency: string;
	in_stock: boolean | null;
	url: string;
	doc_url: string;
	image_url: string;
	controls: string[];
	tags: string[];
	actives: string[];
	bom_count: number;
	has_schematic: boolean;
	has_kicad: boolean;
}

export interface BomRow {
	ref: string;
	value: string;
	part_type: string;
	notes: string;
	category: string;
	norm_value: string;
	sort_key: number;
}

export interface Circuit extends IndexEntry {
	description: string;
	sku: string;
	extra_docs: Record<string, string>;
	schematic_page: number | null;
	doc_version: string;
	kicad_path: string;
	bom: BomRow[];
	scraped_at: string;
}

export interface PartEntry {
	key: string; // "IC:LM308"
	category: string;
	value: string;
	circuits: string[];
	types: string[];
	count: number;
	slug: string;
}

export interface VendorInfo {
	id: Vendor;
	name: string;
	url: string;
	license_note: string;
}

export const VENDOR_NAMES: Record<Vendor, string> = {
	pedalpcb: 'PedalPCB',
	aionfx: 'Aion FX',
	madbean: 'Madbean',
	guitarpcb: 'GuitarPCB',
	fuzzdog: 'Fuzz Dog',
	sheepylove: 'Sheepy Love',
	deadendfx: 'Dead End FX'
};

export const PART_CATEGORY_NAMES: Record<string, string> = {
	R: 'Resistors',
	C: 'Capacitors',
	D: 'Diodes',
	Q: 'Transistors',
	IC: 'ICs',
	POT: 'Potentiometers',
	TRIM: 'Trimmers',
	SW: 'Switches',
	LED: 'LEDs',
	L: 'Inductors',
	XTAL: 'Crystals',
	OPTO: 'Opto',
	CONN: 'Jacks & sockets',
	HW: 'Hardware',
	OTHER: 'Other'
};

export const PART_ORDER = ['R', 'C', 'D', 'Q', 'IC', 'OPTO', 'L', 'XTAL', 'POT', 'TRIM', 'SW', 'LED', 'CONN', 'HW', 'OTHER'];
