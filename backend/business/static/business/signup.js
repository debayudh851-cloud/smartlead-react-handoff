'use strict';
const form=document.getElementById('signup-form');
const feedback=document.getElementById('signup-feedback');
form.addEventListener('submit',async event=>{
  event.preventDefault();
  const body=Object.fromEntries(new FormData(form));
  feedback.classList.remove('error');
  if(body.password!==body.confirm_password){feedback.textContent='Passwords do not match.';feedback.classList.add('error');return;}
  delete body.confirm_password;
  const submit=form.querySelector('button');submit.disabled=true;
  try {
    const response=await fetch('/api/user/register/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const result=await response.json();
    if(!response.ok) throw new Error(Object.entries(result).map(([field,value])=>`${field}: ${Array.isArray(value)?value.join(' '):value}`).join('\n'));
    form.reset();form.hidden=true;
    feedback.textContent=document.body.dataset.role==='admin'?result.message:'Account created successfully. Use the Log in link below to sign in.';
  } catch(error){feedback.textContent=error.message;feedback.classList.add('error');}
  finally {submit.disabled=false;}
});
