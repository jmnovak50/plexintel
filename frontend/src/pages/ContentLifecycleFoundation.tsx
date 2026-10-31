import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AppShell from '../components/AppShell';
import { FoundationSections } from '../components/EligibilityViews';
import { FOUNDATION_CONTENT } from '../lib/contentLifecycle';

export default function ContentLifecycleFoundation({stage}:{stage:keyof typeof FOUNDATION_CONTENT}) {
  const navigate=useNavigate();const [user,setUser]=useState<{username:string;is_admin:boolean}|null>(null);const [error,setError]=useState('');
  useEffect(()=>{let active=true;setUser(null);fetch('/api/admin/me',{credentials:'include'}).then(async r=>{
    if(!r.ok){navigate('/',{replace:true});return;}const me=await r.json();
    if(stage!=='queue'&&!me.is_admin){navigate('/recs',{replace:true});return;}if(active)setUser(me);
  }).catch(()=>{if(active)setError('Unable to verify access.');});return()=>{active=false;};},[navigate,stage]);
  const content=FOUNDATION_CONTENT[stage];
  return <AppShell title={content.title} eyebrow={stage==='queue'?'Your content lifecycle':'Administration'} description={content.question} signedInAs={user?.username} showAdminNav={!!user?.is_admin} headerActions={<Link className="recs-btn-secondary" to="/recs">Recommendations</Link>}>
    {error?<p role="alert">{error}</p>:!user?<p role="status">Checking access…</p>:<FoundationSections stage={stage}/>}
  </AppShell>;
}
