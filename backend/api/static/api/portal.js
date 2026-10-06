// Tokens live only in this page's memory and are cleared on sign-out/reload.
let tokens = null;
const result = document.querySelector('#result');
function show(panel) {
  document.querySelectorAll('.panel').forEach(el => el.hidden = el.id !== panel);
  document.querySelectorAll('[data-panel]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.panel === panel)));
}
function updateSession() { document.querySelector('#session-status').textContent = tokens ? 'Signed in · session held in this page' : 'Signed out'; }
function clearSession() { tokens = null; updateSession(); document.querySelector('#users-body').replaceChildren(); }
function report(data) { result.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2); }
async function request(endpoint, data, auth = false) {
  const headers = {'Content-Type':'application/json'};
  if (auth && tokens) headers.Authorization = `Bearer ${tokens.access}`;
  const response = await fetch(endpoint, {method:data === undefined ? 'GET' : 'POST', headers, credentials:'omit', body:data === undefined ? undefined : JSON.stringify(data)});
  const payload = await response.json().catch(() => ({detail:'Unexpected server response.'}));
  if (!response.ok) { report({status:response.status, ...payload}); return null; }
  return payload;
}
async function run(button, action) {
  button.disabled = true; report('Working…');
  try { await action(); } catch (error) { report('Unable to reach the server. Check your connection and try again.'); }
  finally { button.disabled = false; }
}
document.querySelectorAll('[data-panel]').forEach(el => el.addEventListener('click', () => show(el.dataset.panel)));
document.querySelectorAll('form').forEach(form => form.addEventListener('submit', event => {
  event.preventDefault();
  run(form.querySelector('button'), async () => {
    const data = Object.fromEntries(new FormData(form));
    let endpoint = form.dataset.endpoint;
    if (form.id === 'recovery-form') endpoint = document.querySelector('#recovery-action').value;
    if (form.id === 'reset-form') endpoint = `/api/${document.querySelector('#reset-role').value}/reset-password/`;
    const payload = await request(endpoint, data);
    if (!payload) return;
    if (endpoint === '/api/token/' || endpoint === '/api/user/register/') {
      tokens = payload.tokens || payload; updateSession(); report(payload.message || 'Signed in successfully.');
    } else { report(payload); }
    if (form.id === 'reset-form') { clearSession(); history.replaceState(null, '', '/'); }
    form.querySelectorAll('input[type=password]').forEach(input => input.value = '');
  });
}));
document.querySelector('#logout').addEventListener('click', event => run(event.target, async () => {
  if (tokens) await request('/api/auth/logout/', {refresh:tokens.refresh}, true);
  clearSession(); report('Signed out.');
}));
document.querySelector('#refresh').addEventListener('click', event => run(event.target, async () => {
  if (!tokens) return report('Sign in first.');
  const payload = await request('/api/token/refresh/', {refresh:tokens.refresh});
  if (payload) {tokens.access = payload.access; report('Session refreshed.');} else clearSession();
}));
document.querySelector('#load-users').addEventListener('click', event => run(event.target, async () => {
  if (!tokens) return report('Sign in with a super-admin account first.');
  const payload = await request('/api/admin/users/', undefined, true);
  if (!payload) return;
  const body = document.querySelector('#users-body'); body.replaceChildren();
  payload.users.forEach(user => {
    const row = document.createElement('tr');
    [user.username, user.email, user.is_staff ? 'Admin' : 'User', new Date(user.date_joined).toLocaleString()].forEach(value => {
      const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
    }); body.append(row);
  }); report(`${payload.count} users loaded.`);
}));
const match = location.pathname.match(/^\/(user|admin)\/reset-password\/([^/]+)\/([^/]+)\/$/);
if (match) {
  show('reset'); document.querySelector('#reset-role').value = match[1];
  document.querySelector('[name=uid]').value = decodeURIComponent(match[2]);
  document.querySelector('[name=token]').value = decodeURIComponent(match[3]);
} else show('login');
