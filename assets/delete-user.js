function deleteUser(email) {
	if (!confirm(`Delete user ${email}?`)) {
		return;
	}
	fetch('/delete_user', {method: 'POST', body: JSON.stringify({email: email})}).then(async (resp) => {
		if (!resp.ok) {
			alert(await resp.text());
		} else {
			window.location.reload();
		}
	});
}