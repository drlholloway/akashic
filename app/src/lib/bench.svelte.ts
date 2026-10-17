import { browser } from '$app/environment';

/** My bench: the circuits a visitor keeps, by circuit id ('cryptid:3pdt-led-board'), each with the day it was
 * added and a note. Kept in this browser only; an export file or a share link carries it elsewhere. */
export interface BenchItem {
	added: string; // YYYY-MM-DD
	note: string;
}

const KEY = 'akashic-bench';
const INVENTORY = 'akashic-inventory'; // What can I build's parts list, carried in the same export file

function read(): Record<string, BenchItem> {
	try {
		const v = JSON.parse(localStorage.getItem(KEY) ?? 'null');
		if (!v || typeof v.items !== 'object') return {};
		const out: Record<string, BenchItem> = {};
		for (const [id, it] of Object.entries(v.items as Record<string, Partial<BenchItem>>)) {
			if (it && typeof it === 'object') out[id] = { added: typeof it.added === 'string' ? it.added : '', note: typeof it.note === 'string' ? it.note : '' };
		}
		return out;
	} catch {
		return {}; // storage blocked or empty
	}
}

class Bench {
	items = $state<Record<string, BenchItem>>({});
	private started = false;

	/** Read the bench once, and follow changes made in other tabs. */
	init() {
		if (!browser || this.started) return;
		this.started = true;
		this.items = read();
		window.addEventListener('storage', (e) => {
			if (e.key === KEY) this.items = read();
		});
	}
	get ids(): string[] {
		return Object.keys(this.items).sort((a, b) => this.items[b].added.localeCompare(this.items[a].added));
	}
	get count(): number {
		return Object.keys(this.items).length;
	}
	has(id: string): boolean {
		return id in this.items;
	}
	add(id: string, note = '') {
		if (id in this.items) return;
		this.items[id] = { added: new Date().toISOString().slice(0, 10), note };
		this.save();
		// Ask the browser not to clear the site's storage when space runs low (Safari's seven-day rule still applies).
		navigator.storage?.persist?.().catch(() => {});
	}
	remove(id: string) {
		delete this.items[id];
		this.save();
	}
	toggle(id: string) {
		if (this.has(id)) this.remove(id);
		else this.add(id);
	}
	setNote(id: string, note: string) {
		if (!(id in this.items)) return;
		this.items[id].note = note;
		this.save();
	}
	clear() {
		this.items = {};
		this.save();
	}
	private save() {
		try {
			localStorage.setItem(KEY, JSON.stringify({ v: 1, items: this.items }));
		} catch {
			// the bench still works on this page; it just forgets on reload
		}
	}

	/** The export file: the bench and What can I build's parts list. */
	exportFile(): string {
		let inventory: unknown = null;
		try {
			inventory = JSON.parse(localStorage.getItem(INVENTORY) ?? 'null');
		} catch {
			// no parts list to carry
		}
		return JSON.stringify({ app: 'akashic', kind: 'bench', v: 1, exported: new Date().toISOString(), bench: this.items, inventory }, null, 1);
	}
	/** Merge an export file in: circuits already on the bench keep their note unless it is empty; parts are added
	 * to the parts list. Returns how many circuits and parts were new. */
	importFile(text: string, known: (id: string) => boolean): { circuits: number; parts: number } {
		const f = JSON.parse(text);
		if (!f || f.app !== 'akashic' || typeof f.bench !== 'object') throw new Error('Not an Akashic bench file');
		let circuits = 0;
		for (const [id, it] of Object.entries(f.bench as Record<string, Partial<BenchItem>>)) {
			if (!known(id)) continue;
			const note = typeof it?.note === 'string' ? it.note : '';
			if (!(id in this.items)) {
				this.items[id] = { added: typeof it?.added === 'string' ? it.added : new Date().toISOString().slice(0, 10), note };
				circuits++;
			} else if (!this.items[id].note && note) this.items[id].note = note;
		}
		this.save();
		let parts = 0;
		if (f.inventory && typeof f.inventory.parts === 'object') {
			try {
				const cur = JSON.parse(localStorage.getItem(INVENTORY) ?? 'null') ?? { parts: {}, assume: ['SW'] };
				for (const [k, n] of Object.entries(f.inventory.parts as Record<string, unknown>)) {
					if (!(k in cur.parts) && (n === null || typeof n === 'number')) {
						cur.parts[k] = n;
						parts++;
					}
				}
				localStorage.setItem(INVENTORY, JSON.stringify(cur));
			} catch {
				// the bench came in; the parts list could not be stored
			}
		}
		return { circuits, parts };
	}
}

export const bench = new Bench();
