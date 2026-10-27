export class OperatorConsole {
  constructor(root,{api,esc,download}){
    this.root=root;this.api=api;this.esc=esc;this.download=download;this.active=true;
    root.classList.add('operator-page');
    this.click=event=>this.handleClick(event);
    this.submit=event=>this.handleSubmit(event);
    root.addEventListener('click',this.click);
    root.addEventListener('submit',this.submit);
    this.refresh();
  }
  destroy(){this.active=false;this.root.classList.remove('operator-page');this.root.removeEventListener('click',this.click);this.root.removeEventListener('submit',this.submit);}
  async refresh(){
    try{
      const [status,feedback,members]=await Promise.all([this.api('/operator/status'),this.api('/operator/feedback'),this.api('/operator/members')]);
      if(!this.active)return;
      const esc=this.esc,ops=status.operations,last=ops.runs.backup,restore=ops.runs.restore;
      const date=value=>value?new Date(value*1000).toLocaleString():'Not yet recorded';
      const check=(label,value)=>`<li><span>${label}</span><strong>${value?'Configured':'Pending'}</strong></li>`;
      this.root.innerHTML=`<div class="row between"><h1>Operator console</h1><button class="btn secondary small" data-operator="refresh">Refresh</button></div>
        <div id="operator-error" class="error hidden" role="alert"></div><p id="operator-progress" role="status"></p>
        <div class="field-grid"><section class="panel stack"><h2>Service health</h2><p>${status.metrics.active_streams} live connections · ${status.metrics.server_errors} server errors since restart</p><p>Typical response ${status.metrics.latency_ms.p50} ms · 95th percentile ${status.metrics.latency_ms.p95} ms</p><p>${Math.floor(ops.disk_free_bytes/1024/1024)} MB of storage available</p><p>${status.open_reports} open reports · ${status.open_feedback} feedback items</p><button class="btn secondary" data-action="moderation">Review reports</button></section>
        <section class="panel stack"><h2>Backups and recovery</h2><p>Automatic backups ${ops.backups_enabled?'enabled':'disabled'} · ${ops.backup_interval_hours}-hour interval · retain ${ops.backup_keep}</p><p>Last backup: ${esc(date(last?.completed_at))} (${esc(last?.status||'pending')})</p><p>Last restore check: ${esc(date(restore?.completed_at))} (${esc(restore?.status||'pending')})</p><p>These backups are on the server’s storage. Download a copy to protected storage outside the hosting account.</p><button class="btn" data-operator="backup">Create backup</button><button class="btn secondary" data-operator="restore-check">Verify a separate restore</button><details><summary>Download the latest backup</summary><form id="operator-backup-download" class="stack"><p>This file contains private account and conversation data. Confirm your account password and keep the downloaded file protected.</p><label>Account password<input name="password" type="password" autocomplete="current-password" required></label><button class="btn secondary" type="submit">Download backup</button><p class="error hidden" role="alert"></p><p data-download-status role="status"></p></form></details><button class="text-button" data-operator="cleanup">Clean up expired temporary records</button></section></div>
        <section class="panel stack"><h2>Launch setup</h2><ul class="operator-checks">${check('Operator identity and contact',status.readiness.operator_configured)}${check('Email delivery settings',status.readiness.email_configured)}${check('Owner membership approvals',status.verification.approval_required)}${check('External verification settings',status.verification.configured)}${check('Privacy review recorded',status.readiness.privacy_review_recorded)}${check('Physical phone acceptance',status.readiness.physical_device_checks_recorded)}${check('Student pilot',status.readiness.student_pilot_completed)}</ul><p>Configuration checks do not establish email receipt, legal approval or successful student testing. Record those observations separately.</p>${status.email.issues.length?`<details><summary>Email setup</summary><ul>${status.email.issues.map(issue=>`<li>${esc(issue)}</li>`).join('')}</ul></details>`:''}${status.verification.issues.length?`<details><summary>Verification setup</summary><ul>${status.verification.issues.map(issue=>`<li>${esc(issue)}</li>`).join('')}</ul></details>`:''}</section>
        <section class="panel stack"><h2>Membership approvals</h2><p>${members.approval_required?'Only approved members can use campus discovery and conversations.':'Approval enforcement is off for this development build.'} Approving membership does not verify age.</p>${members.items.map(member=>`<article class="feedback-item"><div class="row between"><strong>${esc(member.display_name)} · @${esc(member.username)}</strong><small>${esc(member.approval_status)}</small></div><p>${esc(member.email)}<br>${esc(member.program||'Profile setup incomplete')}</p><div class="row">${member.approval_status!=='approved'?`<button class="btn small" data-operator="member" data-id="${esc(member.id)}" data-status="approve">Approve member</button>`:''}${member.approval_status!=='rejected'?`<button class="btn secondary small" data-operator="member" data-id="${esc(member.id)}" data-status="decline">Decline membership</button>`:''}</div></article>`).join('')}</section>
        <section class="panel stack"><h2>Pilot feedback</h2>${feedback.items.length?feedback.items.map(item=>`<article class="feedback-item"><div class="row between"><strong>${esc(item.category)} · ${esc(item.username?'@'+item.username:'Deleted account')}</strong><small>${esc(item.status)}</small></div><p class="feedback-body">${esc(item.body)}</p><div class="row">${['open','triaged','resolved'].filter(value=>value!==item.status).map(value=>`<button class="btn secondary small" data-operator="feedback" data-id="${esc(item.id)}" data-status="${value}">Mark ${value}</button>`).join('')}</div></article>`).join(''):'<p>No feedback has been submitted yet.</p>'}</section>`;
    }catch(error){if(!this.active||error.stale)return;this.root.innerHTML=`<section class="panel"><h1>Operator console</h1><p role="alert">${this.esc(error.message)}</p><button class="btn secondary" data-operator="refresh">Try again</button></section>`;}
  }
  async handleClick(event){
    const button=event.target.closest('[data-operator]');if(!button)return;
    event.preventDefault();const action=button.dataset.operator;
    if(action==='refresh'){await this.refresh();return;}
    if(action==='member'&&button.dataset.status==='decline'){
      const row=button.closest('article');if(row.querySelector('[data-decline-confirmation]'))return;
      const box=document.createElement('div');box.dataset.declineConfirmation='';box.className='notice stack';
      box.innerHTML=`<p>Decline this membership? Existing connections will end and Dating will turn off. Saved messages will be retained, and future connections need fresh consent.</p><div class="row"><button class="btn danger small" data-operator="member-decline-confirm" data-id="${this.esc(button.dataset.id)}">Confirm decline</button><button class="btn secondary small" data-operator="cancel-decline">Cancel</button></div>`;
      row.append(box);return;
    }
    if(action==='cancel-decline'){button.closest('[data-decline-confirmation]').remove();return;}
    button.disabled=true;
    const progress=this.root.querySelector('#operator-progress'),error=this.root.querySelector('#operator-error');
    error?.classList.add('hidden');if(progress)progress.textContent=action==='feedback'?'Saving…':'Running the selected operation…';
    try{
      if(action==='feedback')await this.api('/operator/feedback/'+button.dataset.id,'POST',{status:button.dataset.status});
      else if(action==='member'||action==='member-decline-confirm')await this.api('/operator/members/'+button.dataset.id,'POST',{action:action==='member'?'approve':'decline',reason:action==='member'?'':'unable_to_confirm'});
      else await this.api('/operator/maintenance/'+action,'POST',{});
      if(this.active)await this.refresh();
    }catch(problem){if(!this.active||problem.stale)return;if(error){error.textContent=problem.message;error.classList.remove('hidden');}if(progress)progress.textContent='';}
    finally{if(button.isConnected)button.disabled=false;}
  }
  async handleSubmit(event){
    const form=event.target;if(form.id!=='operator-backup-download')return;
    event.preventDefault();event.stopPropagation();
    const button=form.querySelector('[type=submit]'),error=form.querySelector('[role=alert]'),status=form.querySelector('[data-download-status]');
    button.disabled=true;error.classList.add('hidden');status.textContent='Preparing the download…';
    try{const checksum=await this.download(form.elements.password.value);form.elements.password.value='';status.textContent='Download requested. Save the file securely. SHA-256: '+checksum;}
    catch(problem){error.textContent=problem.message;error.classList.remove('hidden');status.textContent='';}
    finally{if(button.isConnected)button.disabled=false;}
  }
}
