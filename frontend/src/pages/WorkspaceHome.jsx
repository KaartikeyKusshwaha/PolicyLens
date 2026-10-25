import { BookOpen, Users, ArrowUpRight, ArrowDownUp, ClipboardCheck, Building2, Plus } from "lucide-react";
import { Link } from "../navigation";
import { ErrorNotice, Loading, PageHeading, formatDate, money, useAutoRefresh, useResource } from "../components";
import { Status } from "../product-components";
import { useSession } from "../session";

function Section({ id, title, icon: Icon, resource, children, action }) {
  return <section id={id} className="panel workspace-section"><div className="panel-heading"><h2><Icon size={18} /> {title}</h2>{action}</div><div className="section-padding">{resource.error ? <ErrorNotice message={resource.error} retry={resource.reload} /> : resource.loading && !resource.data ? <Loading /> : children}</div></section>;
}

export default function WorkspaceHome() {
  const { user } = useSession();
  const team = useResource("/team"), policies = useResource("/policies"), cases = useResource("/cases"), transactions = useResource("/monitor/transactions"), customers = useResource("/customers");
  useAutoRefresh(team.reload); useAutoRefresh(policies.reload); useAutoRefresh(cases.reload); useAutoRefresh(transactions.reload); useAutoRefresh(customers.reload);
  const canEdit = user.role !== "auditor";
  const open = (cases.data || []).filter(c => c.status !== "resolved").sort((a,b) => ({critical:0,high:1,medium:2,low:3}[a.priority] ?? 4) - ({critical:0,high:1,medium:2,low:3}[b.priority] ?? 4) || new Date(a.due_at || "9999") - new Date(b.due_at || "9999"));
  return <>
    <PageHeading eyebrow="YOUR WORKSPACE" title={user.workspace} action={<Link className="button secondary" to="/settings?section=Workspaces">Switch or manage workspace</Link>}>Your people, policies and activity, together. Everything you add here belongs to this workspace.</PageHeading>
    <nav className="workspace-shortcuts" aria-label="Workspace sections">
      {[["People","workspace-people"],["Customers","workspace-customers"],["Transactions","workspace-transactions"],["Company policies","workspace-policies"],["Reviews","workspace-reviews"]].map(([title,id]) => <a href={`#${id}`} key={id}>{title}</a>)}
    </nav>
    <div className="workspace-grid">
      <Section id="workspace-reviews" title="Reviews" icon={ClipboardCheck} resource={cases} action={<Link className="text-link" to="/inbox">Open review queue <ArrowUpRight size={14}/></Link>}>
        <p className="workspace-section-intro">{open.length} open cases in the loaded inventory. Evidence is assembled when you open a case.</p>
        <div className="workspace-records">{open.slice(0,4).map(c => <Link key={c.id} to={`/cases/${c.id}`}><div><strong>{c.title}</strong><small>{c.customer_name} · {c.alert_count || 0} signals</small></div><Status value={c.priority}/></Link>)}</div>
        {!open.length && <p>No open cases. Approved controls will flag activity that needs attention.</p>}
        <Link className="text-link" to="/inbox/approvals">Review pending control approvals</Link>
      </Section>
      <Section id="workspace-policies" title="Company policies" icon={BookOpen} resource={policies} action={canEdit && <Link className="button secondary" to="/policies/new"><Plus size={14}/> Add policy</Link>}>
        <p className="workspace-section-intro">{policies.data?.length || 0} policies in your library. Upload a document or update an existing version.</p>
        <div className="workspace-records">{policies.data?.slice(0,4).map(p => <Link key={p.id} to={`/policies/${p.id}/edit`}><div><strong>{p.title}</strong><small>Version {p.version}</small></div><span>{canEdit ? "View / update" : "View"}</span></Link>)}</div>
        {!policies.data?.length && <p>Add your first company policy to ground checks and cited research.</p>}
        <Link className="text-link" to="/policies/library">Open policy library <ArrowUpRight size={14}/></Link>
      </Section>
      <Section id="workspace-transactions" title="Transactions" icon={ArrowDownUp} resource={transactions} action={canEdit && <Link className="button secondary" to="/inbox/transactions?mode=csv"><Plus size={14}/> Add activity</Link>}>
        <p className="workspace-section-intro">Recent customer activity. Approved controls run automatically as transactions arrive.</p>
        <div className="workspace-records">{transactions.data?.slice(0,4).map(t => <Link key={t.id} to={`/customers/${t.customer_id}`}><div><strong>{t.external_id}</strong><small>{formatDate(t.occurred_at)}</small></div><span>{money(t.amount,t.currency)}</span></Link>)}</div>
        {!transactions.data?.length && <p>No transactions yet. Add customers, then upload a CSV or record a payment.</p>}
        <Link className="text-link" to="/inbox/transactions">Open transactions <ArrowUpRight size={14}/></Link>
      </Section>
      <Section id="workspace-people" title="People" icon={Users} resource={team} action={user.role === "admin" && <Link className="button secondary" to="/settings?section=Team"><Plus size={14}/> Invite people</Link>}>
        <p className="workspace-section-intro">{team.data?.length || 0} connected members. Roles define who investigates, reviews and manages the workspace.</p>
        <div className="workspace-records">{team.data?.slice(0,4).map(person => <div key={person.id}><div><strong>{person.name}</strong><small>{person.email}</small></div><Status value={person.role}/></div>)}</div>
        <Link className="text-link" to="/settings?section=Team">Manage workspace people <ArrowUpRight size={14}/></Link>
      </Section>
      <Section id="workspace-customers" title="Customers & companies" icon={Building2} resource={customers} action={canEdit && <Link className="button secondary" to="/inbox/customers/new"><Plus size={14}/> Add customer</Link>}>
        <p className="workspace-section-intro">Customer records and their recorded due-diligence status.</p>
        <div className="workspace-records">{customers.data?.slice(0,4).map(customer => <Link key={customer.id} to={`/customers/${customer.id}`}><div><strong>{customer.name}</strong><small>{customer.external_id}</small></div><Status value={customer.kyc_status}/></Link>)}</div>
        {!customers.data?.length && <p>Your workspace starts empty. Add a customer before recording their activity.</p>}
        <Link className="text-link" to="/inbox/customers">Open customer directory <ArrowUpRight size={14}/></Link>
      </Section>
      <section className="panel section-padding workspace-section"><h2>Workspace connections</h2><p className="workspace-section-intro">Manage transaction ingestion and the evidence sources used by your team.</p><div className="stack-actions"><Link className="button secondary" to="/settings?section=Integrations">Transaction integrations</Link><Link className="text-link" to="/settings/sources">Evidence sources <ArrowUpRight size={14}/></Link></div></section>
    </div>
  </>;
}
