window.addEventListener('load', () => {
	const form = document.submission;
	form.addEventListener('submit', (event) => {
		event.preventDefault();
		const submitButton = document.getElementById('submitButton');
		submitButton.disabled = true;
		const spinner = document.getElementById("spinner");
		spinner.hidden = false;
		const data = new FormData(form);
		fetch(window.location.href, {method: 'POST', body: data}).then(async (resp) => {
			if (resp.ok) {
				alert('success');
			} else {
				alert(await resp.text());
			}
			document.getElementById('file').value = null;
			submitButton.disabled = false;
			spinner.hidden = true;
		});
	});
});