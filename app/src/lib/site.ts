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
