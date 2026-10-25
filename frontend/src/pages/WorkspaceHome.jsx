import { useRef, useState } from "react";
import { ArrowDownUp, ArrowRight, ArrowUpRight, BookOpen, Building2, ClipboardCheck, Plus, Users } from "lucide-react";
import { Link } from "../navigation";
import { Empty, ErrorNotice, Loading, SearchBox, formatDate, money, useAutoRefresh, useResource } from "../components";
import { Status } from "../product-components";
import { useSession } from "../session";

const sections = [
  { id: "policies", title: "Company policies", icon: BookOpen },
  { id: "people", title: "People", icon: Users },
  { id: "transactions", title: "Transactions", icon: ArrowDownUp },
  { id: "customers", title: "Customers", icon: Building2 },
];
const scrollTo = element => element?.scrollIntoView?.({block:"start", behavior:window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
function Content({ resource, children }) {
  if (resource.error) return <ErrorNotice message={resource.error} retry={resource.reload} />;
  if (!resource.data && resource.loading) return <Loading />;
  return children;
}
function Metric({ title, value, detail, icon: Icon, onClick }) {
  return <button className="overview-metric" onClick={onClick}><span className="metric-label"><span className="metric-symbol"><Icon size={18}/></span>{title}<ArrowUpRight size={15}/></span><strong>{value}</strong><span className="metric-detail">{detail}</span></button>;
}

export default function WorkspaceHome() {
  const { user } = useSession();
  const team = useResource("/team"), policies = useResource("/policies"), cases = useResource("/cases"), transactions = useResource("/monitor/transactions"), customers = useResource("/customers");
  useAutoRefresh(team.reload); useAutoRefresh(policies.reload); useAutoRefresh(cases.reload); useAutoRefresh(transactions.reload); useAutoRefresh(customers.reload);
  const initial = window.location.hash.replace("#workspace-", "");
  const [view, setView] = useState(sections.some(s => s.id === initial) ? initial : "policies");
  const [search, setSearch] = useState("");
  const directory = useRef(null);
  const canEdit = user.role !== "auditor";
  const open = (cases.data || []).filter(c => c.status !== "resolved").sort((a,b) => ({critical:0,high:1,medium:2,low:3}[a.priority] ?? 4) - ({critical:0,high:1,medium:2,low:3}[b.priority] ?? 4) || new Date(a.due_at || "9999") - new Date(b.due_at || "9999"));
  const count = resource => resource.data && !resource.error ? resource.data.length : "—";
  function show(id, scroll = false) { setView(id); setSearch(""); if (scroll) scrollTo(directory.current); }
  const inventories = {
    policies: {resource:policies, description:"The documents behind your decisions.", to:"/policies/library", action:"Add policy", create:"/policies/new", empty:"Your policy library starts here.", hint:"Upload a company policy to give your checks a source of truth.", records:(policies.data || []).map(p => ({id:p.id,title:p.title,subtitle:`Version ${p.version} · ${p.topic.toUpperCase()}`,to:`/policies/${p.id}/edit`,end:canEdit ? "View / update" : "View"}))},
    people: {resource:team, description:"The people moving your workspace forward.", to:"/settings?section=Team", action:"Invite people", create:user.role === "admin" ? "/settings?section=Team" : null, empty:"No members are available.", hint:"Refresh the directory to load your workspace members.", records:(team.data || []).map(p => ({id:p.id,title:p.name,subtitle:p.email,to:"/settings?section=Team",status:p.role}))},
    transactions: {resource:transactions, description:"Recent activity, ready for monitoring and review.", to:"/inbox/transactions", action:"Import transactions", create:"/inbox/transactions?mode=csv", empty:"Activity will appear here.", hint:"Add customers, then import a CSV or record a transaction.", records:(transactions.data || []).map(t => ({id:t.id,title:t.external_id,subtitle:`${t.counterparty} · ${formatDate(t.occurred_at)}`,to:`/customers/${t.customer_id}`,end:money(t.amount,t.currency)}))},
    customers: {resource:customers, description:"Customer context, connected to every investigation.", to:"/inbox/customers", action:"Add customer", create:"/inbox/customers/new", empty:"Meet your first customer.", hint:"Create a customer record before adding their transactions.", records:(customers.data || []).map(c => ({id:c.id,title:c.name,subtitle:c.external_id,to:`/customers/${c.id}`,status:c.kyc_status}))},
  };
  const selected = inventories[view], section = sections.find(s => s.id === view), Icon = section.icon;
  const filtered = selected.records.filter(r => `${r.title} ${r.subtitle}`.toLowerCase().includes(search.toLowerCase()));
  return <div className="workspace-overview">
    <header className="overview-hero">
      <div className="overview-hero-copy"><div className="overview-eyebrow"><span/> YOUR WORKSPACE, CONNECTED</div><h1>{user.workspace}</h1><p>A clearer view of your people, policies and activity.<br className="desktop-break"/> Find what matters. Move the next decision forward.</p><div className="overview-hero-actions">{canEdit && <Link className="button primary" to="/policies/new"><Plus size={17}/> Upload policy</Link>}{canEdit && <Link className="button secondary" to="/inbox/transactions?mode=csv"><ArrowDownUp size={17}/> Add activity</Link>}<Link className="hero-settings" to="/settings?section=Workspaces">Manage workspace <ArrowUpRight size={14}/></Link></div></div>
      <div className="workspace-emblem" aria-hidden="true"><div className="emblem-orbit orbit-a"/><div className="emblem-orbit orbit-b"/><div className="emblem-core"><BookOpen size={38} strokeWidth={1.25}/></div><span className="emblem-dot dot-a"/><span className="emblem-dot dot-b"/></div>
    </header>
    <section className="overview-metrics" aria-label="Workspace at a glance">
      <Metric title="Open reviews" value={cases.data && !cases.error ? open.length : "—"} detail="Loaded case inventory" icon={ClipboardCheck} onClick={() => scrollTo(document.getElementById("workspace-reviews"))}/>
      <Metric title="Company policies" value={count(policies)} detail="In your policy library" icon={BookOpen} onClick={() => show("policies",true)}/>
      <Metric title="Recent transactions" value={count(transactions)} detail="Latest 200 records" icon={ArrowDownUp} onClick={() => show("transactions",true)}/>
      <Metric title="Workspace people" value={count(team)} detail="Connected team members" icon={Users} onClick={() => show("people",true)}/>
    </section>
    <div className="overview-focus-grid">
      <section id="workspace-reviews" className="panel focus-panel" data-reveal>
        <div className="panel-heading"><div><span className="section-overline">YOUR NEXT MOVE</span><h2>Needs your attention</h2></div><Link className="subtle-action" to="/inbox">Review queue <ArrowUpRight size={15}/></Link></div>
        <Content resource={cases}>{open.length ? <div className="focus-records">{open.slice(0,3).map(c => <Link className="focus-record" key={c.id} to={`/cases/${c.id}`}><span className="focus-record-icon"><ClipboardCheck size={20}/></span><div><strong>{c.title}</strong><small>{c.customer_name} · {c.alert_count || 0} signals</small></div><Status value={c.priority}/><ArrowRight size={17}/></Link>)}</div> : <div className="overview-empty"><span className="calm-icon"><ClipboardCheck size={26}/></span><h3>A little breathing room.</h3><p>No open cases in the loaded queue. New control alerts will appear here.</p></div>}<div className="panel-bottom-line"><span>Evidence is assembled when you open a case.</span><Link to="/inbox/approvals">Control approvals <ArrowRight size={14}/></Link></div></Content>
      </section>
      <section className="panel activity-panel" data-reveal>
        <div className="panel-heading"><div><span className="section-overline">IN THE WORKSPACE</span><h2>Latest activity</h2></div><Link className="subtle-action" to="/inbox/transactions" aria-label="Open all transactions"><ArrowUpRight size={17}/></Link></div>
        <Content resource={transactions}>{transactions.data?.length ? <div className="activity-feed">{transactions.data.slice(0,3).map(t => <Link to={`/customers/${t.customer_id}`} key={t.id}><span className="activity-feed-dot"/><div><strong>{t.external_id}</strong><small>{formatDate(t.occurred_at)}</small></div><span>{money(t.amount,t.currency)}</span></Link>)}</div> : <div className="overview-empty compact"><ArrowDownUp size={25}/><h3>Ready when you are.</h3><p>Recent transactions will appear as activity arrives.</p></div>}</Content>
      </section>
    </div>
    <section ref={directory} className="workspace-library" id={`workspace-${view}`} data-reveal>
      <div className="library-section-heading"><div><span className="section-overline">A PLACE FOR EVERYTHING</span><h2>Inside your workspace</h2></div><span className="library-scope">Your workspace records</span></div>
      <nav aria-label="Workspace sections" className="collection-tabs">{sections.map(({id,title,icon:SectionIcon}) => <button key={id} aria-pressed={view===id} onClick={() => show(id)}><SectionIcon size={16}/>{title}</button>)}</nav>
      <section className="panel collection-panel" aria-label={section.title}>
        <div className="panel-heading"><div><h3>{section.title}</h3><p>{selected.description}</p></div>{canEdit && selected.create && <Link className="button secondary" to={selected.create}><Plus size={15}/>{selected.action}</Link>}</div>
        <Content resource={selected.resource}>
          <div className="collection-toolbar"><SearchBox value={search} onChange={setSearch} placeholder={`Search ${section.title.toLowerCase()}…`}/><span>{filtered.length} loaded</span></div>
          {filtered.length ? <div className="collection-records" key={view}>{filtered.slice(0,6).map(r => <Link key={r.id} to={r.to}><span className={`record-monogram ${view === "people" ? "round" : ""}`}>{view === "people" ? r.title.split(" ").map(s => s[0]).slice(0,2).join("") : <Icon size={19}/>}</span><div><strong>{r.title}</strong><small>{r.subtitle}</small></div>{r.status ? <Status value={r.status}/> : <span className="record-trailing">{r.end}</span>}<ArrowUpRight size={15}/></Link>)}</div> : <Empty icon={Icon} title={search ? "No matching records" : selected.empty}>{search ? "Try a different name or reference." : selected.hint}</Empty>}
          <div className="collection-footer"><span>Showing up to 6 records</span><Link to={selected.to}>Open full {view === "people" ? "directory" : "list"} <ArrowRight size={14}/></Link></div>
        </Content>
      </section>
    </section>
    <aside className="workspace-connection-note" data-reveal><span className="calm-icon"><Building2 size={20}/></span><div><strong>Keep your workspace connected.</strong><p>Manage incoming transaction feeds and the evidence sources your team uses.</p></div><Link className="subtle-action" to="/settings?section=Integrations">Manage connections <ArrowUpRight size={15}/></Link></aside>
  </div>;
}
