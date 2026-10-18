export type Vendor = 'pedalpcb' | 'aionfx' | 'madbean' | 'guitarpcb' | 'fuzzdog' | 'sheepylove' | 'deadendfx' | 'moonn' | 'fivecats' | 'parasit' | 'pcbway-gtu' | 'pcbguitarmania' | 'deadastronaut' | 'bentfishbowl' | 'ggg' | 'lectricfx' | 'expanon' | 'zerogiod' | 'otrfx' | 'dirtmonger' | 'maskaudio' | 'effectslayouts' | 'jmk' | 'eae' | 'c2c' | 'deadair' | 'rwlpedal' | 'sheepygit' | 'otherpedals' | 'godcity' | 'effects1776' | 'rullywow' | 'mas' | 'tonepad' | 'wraa' | 'frog' | 'thcustom' | 'guitarelectronics' | 'opelectronics' | 'griffin' | 'coda' | 'delyk' | 'tayda' | 'schalltechnik' | 'electricdruid' | 'zeppelin' | 'moody' | 'gigahearts' | 'scientificguitarist' | 'holyisland' | 'cryptid' | 'effdub' | 'tagboardeffects' | 'dirtbox' | 'effectslayouts-blog' | 'modelectronics' | 'verop2p' | 'pedalbuilder' | 'efektpol' | 'midwayfair' | 'amplifiedparts' | 'revolutiondeux' | 'mattg';

export interface IndexEntry {
	id: string;
	file_id: string;
	vendor: Vendor;
	name: string;
	subtitle: string;
	based_on: string;
	/** One name per original ('Electro-Harmonix Big Muff Pi' for 'EHX Big Muff'); '' when based_on is a description. */
	original: string;
	/** Every original, for a board its vendor says builds more than one ('Ibanez BN5 / SP5'); absent otherwise. */
	originals?: string[];
	/** The maker's own board of an original that layouts and clones name ('Dead Astronaut Tremshifter'): `original` is itself. */
	own_design?: boolean;
	category: string;
	effect_type: string;
	enclosure: string;
	difficulty: string;
	price: number | null;
	currency: string;
	in_stock: boolean | null;
	/** The date a vendor refresh first found the board no longer listed; '' while listed. Such boards are kept. */
	delisted?: string;
	/** The date of the last vendor refresh that found the board listed. */
	last_listed?: string;
	url: string;
	doc_url: string;
	image_url: string;
	controls: string[];
	tags: string[];
	actives: string[];
	bom_count: number;
	has_schematic: boolean;
	has_kicad: boolean;
	/** Every way the circuit can be built, first its own; absent for a plain PCB. */
	builds?: Build[];
	/** Stripboard size as the layout prints it, strips by holes ('18x18'). */
	board?: string;
	/** Whether the source marks the layout as verified by a build; absent when it does not say. */
	verified?: boolean;
}

export type Build = 'pcb' | 'vero' | 'tagboard' | 'turret' | 'perfboard' | 'p2p';
export const BUILD_NAMES: Record<Build, string> = { pcb: 'PCB', vero: 'Vero', tagboard: 'Tagboard', turret: 'Turret board', perfboard: 'Perfboard', p2p: 'Point to point' };
export const BUILD_ORDER: Build[] = ['pcb', 'vero', 'perfboard', 'tagboard', 'turret', 'p2p'];
const PCB_ONLY: Build[] = ['pcb'];
/** The originals a circuit is based on: usually one, none for a description, several for a board that builds more than one. */
export const originalsOf = (e: { original: string; originals?: string[] }): string[] => e.originals ?? (e.original ? [e.original] : []);
export const buildsOf = (e: { builds?: Build[] }): Build[] => e.builds ?? PCB_ONLY;

/** How a circuit that is not a bought PCB is built: a drawing on a layout site. */
export interface Layout {
	build?: Build;
	board?: string;
	cuts?: number;
	links?: number;
	verified?: boolean;
	images?: string[];
	also?: { build: Build; url: string }[];
}

export interface BomRow {
	ref: string;
	value: string;
	part_type: string;
	notes: string;
	category: string;
	norm_value: string;
	sort_key: number;
	variant?: string;
	/** The part pages this row belongs to, as [part, page slug]: one per alternative in '2N5088 or 2N5089'. */
	xref?: [string, string][];
}

export interface Circuit extends IndexEntry {
	/** The other boards based on the same original, the maker's own first: from the export, so the page needs no index. */
	siblings?: Pick<IndexEntry, 'file_id' | 'name' | 'vendor' | 'enclosure' | 'controls' | 'price' | 'currency' | 'own_design'>[];
	/** What the person who read the parts list off the drawing could not be sure of. */
	uncertain?: string[];
	fixes?: string[]; // the source's own corrections to its drawing, applied to the parts list
	description: string;
	sku: string;
	extra_docs: Record<string, string>;
	schematic_page: number | null;
	doc_version: string;
	kicad_path: string;
	owner_schematic?: string; // the site owner's own boards: schematic SVG served from the bundle
	owner_photo?: string;
	bom: BomRow[];
	variants?: string[];
	scraped_at: string;
	layout?: Layout;
}

export interface PartEntry {
	key: string; // "IC:LM308"
	category: string;
	value: string;
	circuits: string[];
	types: string[];
	/** The manufacturer's datasheet: a link, or a path under static/datasheets/ for a discontinued part with no maker's copy. */
	datasheet?: string;
	/** The hosted file is a row in a maker's selector table, not a full datasheet. */
	selector?: boolean;
	/** Every sheet for the part, first its own: a discontinued part made by several fabs has one per maker. */
	datasheets?: { href: string; maker: string; selector: boolean }[];
	zeners?: { pn: string; series: string; power: string; package: string; datasheet: string }[];
	desc?: string; // what the part is: 'Si NPN BJT TO-92 TH', 'Si Schottky DO-41 TH' (transistors.describe, diodes.describe)
	count: number;
	/** The hosted sheet is of a part that may still be made: only the sheet is gone from the maker's site. */
	sheet_only?: boolean;
	slug: string;
}

/** needs.json: what each board takes, for 'What can I build'. Parts are named by their place in parts.json. */
export interface Needs {
	/** What owning a part covers besides itself: a 1N4739 is a 9V1 zener. */
	also: Record<string, number[]>;
	/** n: one entry per requirement, [how many, part, alternative, ...]. u: rows that name no part the catalog knows. */
	circuits: Record<string, { n: number[][]; u?: number }>;
}

export interface VendorInfo {
	id: Vendor;
	name: string;
	url: string;
	license_note: string;
	kind?: VendorKind;
	warning?: string;
}

export const VENDOR_NAMES: Record<Vendor, string> = {
	pedalpcb: 'PedalPCB',
	aionfx: 'Aion FX',
	madbean: 'Madbean',
	guitarpcb: 'GuitarPCB',
	fuzzdog: 'Fuzz Dog',
	sheepylove: 'Sheepylove',
	deadendfx: 'Dead End FX',
	moonn: 'Moonn Electronics',
	fivecats: 'Five Cats Pedals',
	parasit: 'Parasit Studio',
	'pcbway-gtu': 'PCBWay: Glory to Ukraine',
	pcbguitarmania: 'PCB Guitar Mania',
	deadastronaut: 'Dead Astronaut FX',
	bentfishbowl: 'Bent Fishbowl',
	ggg: 'General Guitar Gadgets',
	lectricfx: 'Lectric-FX',
	expanon: 'Experimentalists Anonymous',
	zerogiod: 'Zero G IOD',
	otrfx: 'On The Road Effects',
	dirtmonger: 'Dirt Monger Instruments',
	maskaudio: 'Mask Audio Electronics',
	effectslayouts: 'Effects Layouts',
	jmk: 'JMK PCBs',
	eae: 'Electronic Audio Experiments',
	c2c: 'C2C Electronics',
	deadair: 'Dead Air Studios',
	rwlpedal: 'RWL Pedals',
	sheepygit: 'Sheepylove on GitHub',
	otherpedals: 'Other Pedals',
	godcity: 'God City Instruments',
	effects1776: '1776 Effects',
	rullywow: 'Rullywow Industries',
	mas: 'MAS Effects',
	modelectronics: 'Mod Electronics',
	verop2p: 'Vero P2P',
	pedalbuilder: 'Naegele Audio',
	midwayfair: 'Jon Patton',
	amplifiedparts: 'Amplified Parts',
	revolutiondeux: 'Revolution Deux',
	mattg: 'Matt Garman',
	efektpol: 'EfektPol',
	tonepad: 'Tonepad',
	wraa: 'WRAA Labs',
	frog: 'Frog Pedals',
	thcustom: 'TH Custom Effects',
	guitarelectronics: 'Guitar-Electronics.eu',
	opelectronics: 'OP Electronics',
	griffin: 'Griffin Effects',
	coda: 'Coda Effects',
	delyk: 'delyk PCBs',
	tayda: 'Tayda Electronics (DHEA)',
	schalltechnik: 'Schalltechnik_04',
	electricdruid: 'Electric Druid',
	zeppelin: 'Zeppelin Design Labs',
	moody: 'Moody Sounds',
	gigahearts: 'Gigahearts FX',
	scientificguitarist: 'Scientific Guitarist',
	holyisland: 'Holy Island Audio',
	cryptid: 'Cryptid Effects',
	effdub: 'Eff Dub Audio',
	tagboardeffects: 'Tagboard Effects',
	dirtbox: 'Dirtbox Layouts',
	'effectslayouts-blog': 'Effects Layouts (blog)'
};

export type VendorKind = 'shop' | 'projects' | 'repo' | 'blog' | 'archive' | 'layout' | 'kit';
export const VENDOR_KIND: Partial<Record<Vendor, VendorKind>> = { 'pcbway-gtu': 'projects', rwlpedal: 'repo', sheepygit: 'repo', scientificguitarist: 'repo', cryptid: 'repo', bentfishbowl: 'blog', effdub: 'blog', expanon: 'archive', schalltechnik: 'blog', tagboardeffects: 'layout', dirtbox: 'layout', 'effectslayouts-blog': 'layout', modelectronics: 'kit', verop2p: 'layout', pedalbuilder: 'blog', efektpol: 'layout', midwayfair: 'projects', amplifiedparts: 'layout', revolutiondeux: 'blog', mattg: 'repo' };
/** The fab a 'projects' source's boards are ordered from, when it is not the source's own name. */
export const VENDOR_FAB: Partial<Record<Vendor, string>> = { 'pcbway-gtu': 'PCBWay', midwayfair: 'OSH Park' };
/** Where a source's bare PCBs (tagged 'PCB only') are sold, when it is not the source itself. */
/** What a 'repo' source shares, when it is not gerbers. */
export const VENDOR_FILES: Partial<Record<Vendor, string>> = { mattg: 'the KiCad project' };
export const VENDOR_STORE: Partial<Record<Vendor, string>> = { modelectronics: 'Amplified Parts' };

export function primaryAction(v: Vendor): string {
	const k = VENDOR_KIND[v] ?? 'shop';
	return k === 'kit' ? `See the kit at ${VENDOR_NAMES[v]}` : k === 'layout' ? `Open the layout at ${VENDOR_NAMES[v]}` : k === 'blog' ? `Read the post at ${VENDOR_NAMES[v]}` : k === 'archive' ? `Open the schematic at ${VENDOR_NAMES[v]}` : k === 'projects' ? `Order the board at ${VENDOR_FAB[v] ?? VENDOR_NAMES[v]}` : k === 'repo' ? `Get ${VENDOR_FILES[v] ?? 'the gerbers'} at ${VENDOR_NAMES[v]}` : `Buy the PCB at ${VENDOR_NAMES[v]}`;
}

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
	XFM: 'Transformers',
	CONN: 'Jacks & sockets',
	HW: 'Hardware',
	OTHER: 'Other'
};

export const PART_ORDER = ['R', 'C', 'D', 'Q', 'IC', 'OPTO', 'L', 'XFM', 'XTAL', 'POT', 'TRIM', 'SW', 'LED', 'CONN', 'HW', 'OTHER'];

/** A transistor's key limits from the parameter database (BJT or FET fields apply). */
export interface TransistorSpec {
	pn: string;
	boards?: number;
	score?: number;
	hfe?: number;
	vce?: number;
	ic?: number;
	pc?: number;
	ft?: number;
	vds?: number;
	vgs?: number;
	vgsth?: number;
	idmax?: number;
	pd?: number;
	rds?: number;
}

export interface SubsEntry {
	kind: 'bjt' | 'jfet' | 'mosfet';
	mat?: string;
	pol?: string;
	ch?: string;
	spec: TransistorSpec;
	anchor?: string; // the listed equivalent whose parameters stand in for a part the database lacks
	used: TransistorSpec[];
	closest: TransistorSpec[];
}

/** One week of the changelog (Monday to Sunday), built from the commit history at export. */
export interface ChangeWeek {
	week: string;
	items: { sha: string; date: string; subject: string; detail: string }[];
}
