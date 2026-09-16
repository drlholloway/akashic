import { browser } from '$app/environment';

export type Currency = 'USD' | 'EUR' | 'GBP' | 'native';
export interface Rates {
	base: 'USD';
	date: string | null;
	rates: Record<string, number>; // USD -> X
}

const KEY = 'pcblib.currency';
const SYMBOL: Record<string, string> = { USD: '$', EUR: '€', GBP: '£' };

function readPref(): Currency {
	if (!browser) return 'USD';
	try {
		const v = localStorage.getItem(KEY);
		if (v === 'USD' || v === 'EUR' || v === 'GBP' || v === 'native') return v;
	} catch {
		/* storage unavailable */
	}
	return 'USD';
}

class CurrencyStore {
	selected = $state<Currency>('USD');
	rates = $state<Rates>({ base: 'USD', date: null, rates: { USD: 1 } });

	init(rates: Rates | null) {
		if (rates) this.rates = rates;
		this.selected = readPref();
	}
	set(c: Currency) {
		this.selected = c;
		try {
			localStorage.setItem(KEY, c);
		} catch {
			/* ignore */
		}
	}
	/** Convert an amount from the vendor's currency into the selected one; null if no rate. */
	convert(amount: number, from: string): { amount: number; currency: string; converted: boolean } {
		const target = this.selected === 'native' ? from : this.selected;
		if (target === from) return { amount, currency: from, converted: false };
		const rFrom = this.rates.rates[from];
		const rTo = this.rates.rates[target];
		if (!rFrom || !rTo) return { amount, currency: from, converted: false };
		return { amount: (amount / rFrom) * rTo, currency: target, converted: true };
	}
	/** Formatted price in the selected currency, e.g. "$27.10". */
	format(amount: number | null, from: string): string {
		if (amount == null) return '';
		const c = this.convert(amount, from);
		return `${SYMBOL[c.currency] ?? c.currency + ' '}${c.amount.toFixed(2)}`;
	}
	/** The vendor's own listing, for tooltips: "£22.00 at vendor". */
	native(amount: number | null, from: string): string {
		if (amount == null) return '';
		return `${SYMBOL[from] ?? from + ' '}${amount.toFixed(2)}`;
	}
	/** Numeric value in the selected currency, for sorting. */
	value(amount: number | null, from: string): number {
		if (amount == null) return Number.POSITIVE_INFINITY;
		return this.convert(amount, from).amount;
	}
}

export const currency = new CurrencyStore();
