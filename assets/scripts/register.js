window.addEventListener('load', () => {
	const form = document.getElementById('regForm');
	form.addEventListener('submit', (event) => {
		event.preventDefault();
		const submitButton = document.getElementById('submitButton');
		submitButton.disabled = true;
		const data = new FormData(form);
		fetch('/register', {method: "POST", body: data}).then(async (resp) => {
			if (resp.ok) {
				alert('Registered. Check your email to verify your account. The verification email may be in your junk folder. The verification will expire in 1 hour.');
				window.location.replace('/');
			} else {
				alert(await resp.text());
				submitButton.disabled = false;
			}
		});
	});
});