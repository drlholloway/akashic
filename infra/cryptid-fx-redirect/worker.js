// cryptid-fx.com is a typo-catcher for cryptideffects.com: send everything there,
// permanently, keeping the path and query so deep links survive.
export default {
	fetch(request) {
		const url = new URL(request.url);
		return Response.redirect(`https://www.cryptideffects.com${url.pathname}${url.search}`, 301);
	}
};
