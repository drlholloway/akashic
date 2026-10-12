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
 *  maker's name at the start of an original ('Aleph Null Special Sauce'). */
export const MAKER_CONTACTS: { maker: string; url: string; where: string }[] = [
	{ maker: 'Aleph Null', url: 'https://forum.pedalpcb.com/members/aleph-null.30287/', where: 'the PedalPCB forum' }
];

export function makerContact(originals: string[]) {
	return MAKER_CONTACTS.find((m) => originals.some((o) => o.toLowerCase().startsWith(m.maker.toLowerCase() + ' ')));
}
