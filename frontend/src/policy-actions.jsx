import { useState } from "react";
import { Ellipsis, FileSearch, Pencil, Trash2, ArrowRight } from "lucide-react";
import { Link, useNavigate } from "./navigation";
import { api } from "./services/api";
import { ErrorNotice } from "./components";
import { useSession } from "./session";

export default function PolicyActions({ policy, onChanged, archived = false }) {
  const {user}=useSession();
  const [busy,setBusy]=useState(false),[error,setError]=useState(""),[removing,setRemoving]=useState(false);
  const navigate=useNavigate();
  const route=`/policies/library/${policy.id}/workflow`;
  async function run(action) {
    setBusy(true);setError("");
    try {
      if(action==="remove") {
        await api(`/policies/${policy.id}`,{method:"DELETE"});setRemoving(false);onChanged?.();
      } else if(action==="review") {
        await api(`/policies/${policy.id}/review`,{method:"POST"});navigate(route);
      } else {
        await api("/agents/jobs",{method:"POST",body:{kind:"policy_analyst",target_id:policy.id}});navigate(route);
      }
    } catch(e) {setError(e.message);} finally {setBusy(false);}
  }
  return <div className="policy-actions">
    <details><summary aria-label={`Actions for ${policy.title}`}><Ellipsis size={21}/></summary><div className="policy-action-menu">
      <Link to={route}><ArrowRight size={16}/> View policy workspace</Link>
      {user.role!=="auditor" && !archived && <><button disabled={busy} onClick={()=>run("review")}><FileSearch size={16}/> Review all transactions</button><button disabled={busy} onClick={()=>run("prepare")}><FileSearch size={16}/> Prepare policy requirements</button><Link to={`/policies/${policy.id}/edit`}><Pencil size={16}/> Update policy</Link></>}
      {user.role==="admin" && !archived && <button disabled={busy} onClick={()=>setRemoving(true)}><Trash2 size={16}/> Delete from active library</button>}
    </div></details>
    <ErrorNotice message={error}/>
    {removing && <div className="policy-remove-confirm" role="alert"><strong>Remove {policy.title} from active use?</strong><p>Its active checks will stop. Existing evidence stays archived and can be restored.</p><div className="button-row"><button className="button secondary" disabled={busy} onClick={()=>setRemoving(false)}>Cancel</button><button className="button primary" disabled={busy} onClick={()=>run("remove")}>Remove policy</button></div></div>}
  </div>;
}
