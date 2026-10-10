/** Sections that fold at their header, the folded ones kept in this browser under `key`. */
export function folds(key: string) {
	let folded = $state<string[]>([]);
	$effect(() => {
		try {
			const v = JSON.parse(localStorage.getItem(key) ?? '[]');
			if (Array.isArray(v)) folded = v.filter((k) => typeof k === 'string');
		} catch {
			// storage blocked or empty: every section open
		}
	});
	function set(keys: string[]) {
		folded = keys;
		try {
			localStorage.setItem(key, JSON.stringify(keys));
		} catch {
			// the page still folds; it just forgets on reload
		}
	}
	return {
		has: (k: string) => folded.includes(k),
		toggle: (k: string) => set(folded.includes(k) ? folded.filter((x) => x !== k) : [...folded, k]),
		set
	};
}
