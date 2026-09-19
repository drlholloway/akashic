<script lang="ts">
	import { currency, type Currency } from './currency.svelte';
	const options: { value: Currency; label: string }[] = [
		{ value: 'USD', label: 'USD $' },
		{ value: 'EUR', label: 'EUR €' },
		{ value: 'GBP', label: 'GBP £' },
		{ value: 'native', label: 'As listed' }
	];
</script>

<label class="currency" title={currency.rates.date ? `Converted at ECB rates from ${currency.rates.date}` : 'No exchange rates loaded'}>
	<span class="label">Prices</span>
	<select value={currency.selected} onchange={(e) => currency.set(e.currentTarget.value as Currency)} disabled={!currency.rates.date}>
		{#each options as o}
			<option value={o.value}>{o.label}</option>
		{/each}
	</select>
</label>

<style>
	.currency { display: inline-flex; align-items: center; gap: 8px; }
	.currency select { border: 1px solid var(--rule-strong); border-radius: var(--radius); background: var(--sheet); padding: 4px 8px; }
	.currency select:disabled { opacity: 0.5; }
</style>
