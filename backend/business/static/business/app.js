'use strict';
// Tokens are held only in memory. A page reload requires a fresh sign-in.
let access = '', refresh = '', nextServices = null, nextLeads = null;
const portalRole=document.body.dataset.role || 'user';
const $ = id => document.getElementById(id);
const feedback = (message, error=false) => { $('feedback').textContent=message; $('feedback').classList.toggle('error',error); };
async function api(url, method='GET', body=null, retried=false, extra={}) {
  const headers={...extra}; if(access) headers.Authorization=`Bearer ${access}`;
  if(body!==null) headers['Content-Type']='application/json';
  let response=await fetch(url,{method,headers,body:body===null?undefined:JSON.stringify(body)});
  if(response.status===401 && refresh && !retried && !url.includes('/auth/refresh/')) {
    const r=await fetch('/api/auth/refresh/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({refresh})});
    if(r.ok){access=(await r.json()).access; return api(url,method,body,true,extra);}
    access='';refresh='';$('session').textContent='Session expired. Sign in again.';
  }
  const data=response.status===204?null:await response.json().catch(()=>({detail:'Unexpected server response.'}));
  if(!response.ok) throw new Error(JSON.stringify(data));
  return data;
}
function el(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
function button(text,fn){const b=el('button',text);b.type='button';b.addEventListener('click',()=>run(fn));return b;}
async function run(fn){try{await fn();}catch(error){feedback(error.message,true);}}
function data(form){return Object.fromEntries(new FormData(form));}
function bind(id,handler){$(id).addEventListener('submit',event=>{event.preventDefault();run(()=>handler(data(event.target),event.target));});}
function rows(payload){return payload.results||payload;}
function list(id,items,render){$(id).replaceChildren();if(!items.length)$(id).append(el('p','No records yet.'));items.forEach(item=>$(id).append(render(item)));}
function requireLogin(){if(!access)throw new Error('Please sign in first.');}
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>{['catalog','customer','staff','supervision'].filter(id=>$(id)).forEach(id=>$(id).hidden=id!==b.dataset.tab);}));
bind('login',async body=>{access='';refresh='';const tokens=await api(`/api/${portalRole}/login/`,'POST',body);access=tokens.access;refresh=tokens.refresh;const p=await api('/api/auth/profile/');$('session').textContent=`${p.username} · ${p.role}`;feedback('Signed in.');if(portalRole==='admin'){await $('load-dashboard').onclick();}if(portalRole==='superuser'){await loadAccounts();await loadRegistrations();}});
$('logout').onclick=()=>run(async()=>{if(access&&refresh)await api('/api/auth/logout/','POST',{refresh});access='';refresh='';$('session').textContent='Signed out';['my-enquiries','my-wishlist','my-notifications','leads','dashboard','pending-reviews','accounts-list','registrations-list'].filter(id=>$(id)).forEach(id=>$(id).replaceChildren());feedback('Signed out.');});
async function services(url='/api/services/'){const p=await api(url);nextServices=p.next;$('more-services').hidden=!nextServices;list('services',rows(p),s=>{const c=el('article',undefined,'card');c.append(el('h3',s.name),el('p',s.description),el('p',`From ₹${s.starting_price}`,'price'));c.append(button('Details',()=>detail(s.id)),button('Enquire',()=>{$('service-choice').value=s.id;$('enquiry').scrollIntoView({behavior:'smooth'});}),button('Save',async()=>{requireLogin();await api('/api/wishlist/','POST',{service:s.id});feedback('Saved to wishlist.');}));return c;});}
async function detail(id){const s=await api(`/api/services/${id}/`);const box=$('service-detail');box.hidden=false;box.replaceChildren(el('h2',s.name),el('p',s.description));(s.features||[]).forEach(f=>box.append(el('p',`• ${f}`)));s.images.forEach(image=>{const img=el('img');img.src=image.image;img.alt=image.alt_text;box.append(img);});s.packages.forEach(p=>box.append(el('p',`${p.name}: ₹${p.price} — ${p.description}`)));const reviews=await api(`/api/reviews/?service=${id}`);rows(reviews).forEach(r=>box.append(el('p',`${r.rating}/5 — ${r.comment}`)));const related=await api(`/api/services/${id}/related/`);box.append(el('h3','Related services'));related.forEach(r=>box.append(button(r.name,()=>detail(r.id))));box.scrollIntoView({behavior:'smooth'});}
bind('search',body=>services('/api/services/?'+new URLSearchParams(body)));$('more-services').onclick=()=>run(()=>services(nextServices));
bind('enquiry',async(body,form)=>{requireLogin();body.service=Number(body.service);body.total_visits=1;body.page_views_per_visit=1;body.time_on_website=Math.max(0,Math.round((Date.now()-started)/1000));const key=form.dataset.requestKey||(form.dataset.requestKey=crypto.randomUUID());const e=await api('/api/enquiries/','POST',body,false,{'Idempotency-Key':key});delete form.dataset.requestKey;feedback(`Enquiry #${e.id} submitted. Status: ${e.status}.`);form.reset();});
async function customer(){requireLogin();const [p,e,w,n]=await Promise.all([api('/api/auth/profile/'),api('/api/enquiries/'),api('/api/wishlist/'),api('/api/notifications/')]);['first_name','last_name','phone'].forEach(key=>$('profile').elements[key].value=p[key]||'');list('my-enquiries',rows(e),item=>el('p',`#${item.id} ${item.service_name} — ${item.status}`));list('my-wishlist',rows(w),item=>{const c=el('div',undefined,'card');c.append(el('span',item.service_name),button('Remove',async()=>{await api(`/api/wishlist/${item.id}/`,'DELETE');await customer();}));return c;});list('my-notifications',rows(n),item=>{const c=el('div',undefined,'card');c.append(el('p',`${item.is_read?'Read':'Unread'}: ${item.message}`));if(!item.is_read)c.append(button('Mark read',async()=>{await api(`/api/notifications/${item.id}/`,'PATCH',{is_read:true});await customer();}));return c;});}
$('load-customer').onclick=()=>run(customer);bind('profile',async body=>{await api('/api/auth/profile/','PATCH',body);feedback('Profile saved.');});bind('password',async(body,form)=>{await api('/api/auth/password/change/','POST',body);access='';refresh='';$('session').textContent='Sign in with your new password';form.reset();feedback('Password changed.');});bind('review',async(body,form)=>{body.service=Number(body.service);body.rating=Number(body.rating);await api('/api/reviews/','POST',body);feedback('Review submitted for moderation.');form.reset();});
async function leads(url='/api/leads/'){const p=await api(url);nextLeads=p.next;$('more-leads').hidden=!nextLeads;list('leads',rows(p),l=>{const c=el('article',undefined,'card');c.append(el('h3',`Lead #${l.id} · ${l.enquiry.service_name}`),el('p',`${l.status} · ${l.enquiry.contact_email} · Budget ₹${l.enquiry.budget}`),el('p',l.enquiry.requirement));if(l.latest_prediction)c.append(el('p',`Demo prediction: ${(l.latest_prediction.probability*100).toFixed(1)}% (${l.latest_prediction.probability_band})`));c.append(button('History & follow-ups',async()=>{const [h,f]=await Promise.all([api(`/api/leads/${l.id}/history/`),api(`/api/leads/${l.id}/followup/`)]);c.append(el('pre',JSON.stringify({history:h,followups:f},null,2)));}));return c;});}
$('more-leads').onclick=()=>run(()=>leads(nextLeads));bind('lead-filter',body=>leads('/api/leads/?'+new URLSearchParams(body)));
$('load-dashboard').onclick=()=>run(async()=>{const d=await api('/api/admin/dashboard/');$('dashboard').replaceChildren();['leads','converted','closed','due_followups','high_probability_leads'].forEach(k=>{const c=el('div',undefined,'card');c.append(el('h3',k.replaceAll('_',' ')),el('p',String(d[k])));$('dashboard').append(c);});await leads();});
bind('lead-update',async body=>{const id=body.id;delete body.id;if(body.assigned_to)body.assigned_to=Number(body.assigned_to);else delete body.assigned_to;await api(`/api/leads/${id}/`,'PATCH',body);feedback('Lead updated.');await leads();});bind('followup',async(body,form)=>{const id=body.id;delete body.id;body.follow_up_date=new Date(body.follow_up_date).toISOString();await api(`/api/leads/${id}/followup/`,'POST',body);feedback('Follow-up scheduled.');form.reset();});bind('predict',async body=>{body.lead_id=Number(body.lead_id);const p=await api('/api/ml/predict/','POST',body);feedback(`Demo probability: ${(p.probability*100).toFixed(1)}% (${p.probability_band}).`);await leads();});bind('moderate',async body=>{await api(`/api/admin/reviews/${body.id}/`,'PATCH',{is_approved:body.is_approved==='true'});feedback('Review decision saved.');});$('load-reviews').onclick=()=>run(async()=>{const p=await api('/api/admin/reviews/');list('pending-reviews',rows(p).filter(r=>!r.is_approved),r=>el('p',`Review #${r.id} · ${r.rating}/5 · ${r.comment}`));});
const started=Date.now();
run(async()=>{const p=await api('/api/categories/');rows(p).forEach(c=>{const o=el('option',c.name);o.value=c.id;$('categories').append(o);});const s=await api('/api/services/?ordering=name');rows(s).forEach(service=>{const o=el('option',service.name);o.value=service.id;$('service-choice').append(o);});await services();});

// Each interface has its own role-specific login; API permissions also enforce access.
if(portalRole!=='user') { $('catalog').hidden=true; $('customer').hidden=true; $('staff').hidden=portalRole!=='admin'; }
let nextAccounts=null,nextRegistrations=null;
async function loadAccounts(url='/api/admin/accounts/') {
  requireLogin(); const p=await api(url);nextAccounts=p.next;$('more-accounts').hidden=!nextAccounts;
  list('accounts-list',rows(p),account=>{const c=el('article',undefined,'card');c.append(el('h3',account.username),el('p',`${account.email} · ${account.role} · ${account.is_active?'Active':'Inactive'}`));
    c.append(button(account.is_active?'Deactivate':'Activate',async()=>{await api(`/api/admin/accounts/${account.id}/`,'PATCH',{is_active:!account.is_active});await loadAccounts();}));return c;});
}
async function loadRegistrations(url='/api/superuser/admin-registrations/') {
  requireLogin();const p=await api(url);nextRegistrations=p.next;$('more-registrations').hidden=!nextRegistrations;
  list('registrations-list',rows(p),application=>{const c=el('article',undefined,'card');c.append(el('h3',application.username),el('p',`${application.email} · ${application.status}`));
    if(application.status==='PENDING') ['APPROVED','REJECTED'].forEach(status=>c.append(button(status==='APPROVED'?'Approve admin':'Reject',async()=>{await api(`/api/superuser/admin-registrations/${application.id}/decision/`,'POST',{status});await loadRegistrations();await loadAccounts();})));return c;});
}
if($('account-filter')) {bind('account-filter',body=>loadAccounts('/api/admin/accounts/?'+new URLSearchParams(body)));$('more-accounts').onclick=()=>run(()=>loadAccounts(nextAccounts));$('load-registrations').onclick=()=>run(()=>loadRegistrations());$('more-registrations').onclick=()=>run(()=>loadRegistrations(nextRegistrations));}

if(portalRole!=='user') feedback('Sign in to load your workspace.');
