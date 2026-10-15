/** Site-wide links that are not part of the scraped data. */
export const COFFEE_URL = 'https://buymeacoffee.com/drlholloway';
export const REPO_URL = 'https://github.com/drlholloway/akashic';
export const ISSUES_URL = `${REPO_URL}/issues/new/choose`;
export const MAKER_NAME = 'Cryptid Effects';
export const MAKER_URL = 'https://cryptideffects.com';

/** A link that opens the "Wrong parts list" issue form with this circuit's page filled in. */
export function wrongParseUrl(boardName: string, pageUrl: string): string {
	const q = new URLSearchParams({ template: 'wrong_parse.yml', title: `Wrong parse: ${boardName}`, url: pageUrl });
	return `${REPO_URL}/issues/new?${q}`;
}

/** Designers with no shop to scrape, who sell their own PCBs when asked: where to reach them, by the
 *  maker's name at the start of an original ('Aleph Null Special Sauce'), or by the source for a builder
 *  whose circuits are clones of other makers' pedals. `lead` replaces 'designed this circuit and sells boards',
 *  `handle` is the forum name to message when it is not the maker's, and `also` the other boards they sell.
 *  `reach` is for a designer who shares layouts rather than selling boards: it replaces the 'Want a PCB?' line. */
export const MAKER_CONTACTS: { maker: string; url: string; where: string; vendor?: string; lead?: string; handle?: string; also?: string; reach?: string }[] = [
	{ maker: 'Aleph Null', url: 'https://forum.pedalpcb.com/members/aleph-null.30287/', where: 'the PedalPCB forum' },
	{ maker: 'Naegele Audio', handle: 'PedalBuilder', url: 'https://forum.pedalpcb.com/members/pedalbuilder.487/', where: 'the PedalPCB forum', vendor: 'pedalbuilder', lead: 'laid out a PCB for this circuit and sells boards', also: 'relay bypass and I/O boards' },
	{ maker: 'EfektPol', handle: '@efektpol', url: 'https://www.instagram.com/efektpol/', where: 'Instagram', vendor: 'efektpol', reach: 'Questions about this layout? EfektPol drew it' }
];

export function makerContact(originals: string[], vendor = '') {
	return MAKER_CONTACTS.find((m) => (m.vendor ? m.vendor === vendor : originals.some((o) => o.toLowerCase().startsWith(m.maker.toLowerCase() + ' '))));
}
