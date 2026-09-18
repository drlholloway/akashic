// cryptid-fx.com is a typo-catcher for cryptideffects.com. The bare domain and www go to
// the store; any other subdomain goes to the same subdomain on the real domain, so
// akashic.cryptid-fx.com lands on akashic.cryptideffects.com. Permanent, path preserved.
export default {
	fetch(request) {
		const url = new URL(request.url);
		const sub = url.hostname.replace(/\.?cryptid-fx\.com$/, '');
		const host = sub && sub !== 'www' ? `${sub}.cryptideffects.com` : 'www.cryptideffects.com';
		return Response.redirect(`https://${host}${url.pathname}${url.search}`, 301);
	}
};
