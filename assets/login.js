window.addEventListener('load', () => {
	const form = document.loginForm;
	form.addEventListener('submit', (event) => {
		event.preventDefault();
		const data = new FormData(form);
		fetch('/login', {method: "POST", body: data}).then(async (resp) => {
			if (resp.ok) {
				window.location.replace('/');
			} else {
				alert(await resp.text());
			}
		});
	});
});