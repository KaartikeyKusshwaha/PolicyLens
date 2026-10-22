import { beforeEach,expect,test,vi } from "vitest";
import { fireEvent,render,screen,waitFor } from "@testing-library/react";
import DeletionRequests from "./DeletionRequests";
import { api } from "../services/api";
vi.mock("../services/api",()=>({api:vi.fn()}));
beforeEach(()=>vi.clearAllMocks());
const request={id:"request-one",customer_id:"customer-one",status:"requested",created_by:"author",reason:"Synthetic logical deletion plan.",expires_at:"2026-10-24T00:00:00Z",inventory_sha256:"pinned-hash",history:[],scope:"Logical review only; no execution.",snapshot:{candidates:[],retained_audit:{scope:"Audit history stays retained."},excluded_scope:["External backups"]}};
const detail={request,current_inventory_sha256:"pinned-hash",stale:false,expired:false,current_blockers:[{code:"external_copy_reconciliation_required"}],execution_available:false};
const user={id:"reviewer",role:"reviewer"};
async function inspect(){fireEvent.click(screen.getByRole("button",{name:"Inspect request request-one"}));await screen.findByText("Current request evidence");}

test("stale plan cannot be approved even when previously requested",async()=>{
 api.mockResolvedValue({...detail,stale:true,current_inventory_sha256:"changed-hash"});
 render(<DeletionRequests requests={[request]} user={user} reload={vi.fn()} />);await inspect();
 expect(screen.queryByRole("button",{name:"Approve logical deletion plan"})).toBeNull();
 expect(screen.getByText(/inventory changed/)).toBeTruthy();
 expect(screen.getByText("No execution action is available.")).toBeTruthy();
});

test("approval records discovery evidence and acknowledgements without claiming execution",async()=>{
 api.mockImplementation(async(path,options)=>options?.method==="POST"?{status:"approved"}:detail);
 const reload=vi.fn();render(<DeletionRequests requests={[request]} user={user} reload={reload} />);await inspect();
 fireEvent.change(screen.getByLabelText("Deletion review reason"),{target:{value:"Reviewed the pinned plan and retained audit limitations."}});
 fireEvent.change(screen.getByLabelText("Copy discovery evidence reference"),{target:{value:"TEST-DISCOVERY"}});
 fireEvent.change(screen.getByLabelText("Copy discovery evidence SHA-256"),{target:{value:"a".repeat(64)}});
 fireEvent.click(screen.getByLabelText("I reviewed retained audit history"));fireEvent.click(screen.getByLabelText("I reviewed physical and restore limitations"));
 fireEvent.click(screen.getByRole("button",{name:"Approve logical deletion plan"}));
 await screen.findByText("Deletion plan review recorded. No records or files were deleted.");
 expect(reload).toHaveBeenCalledOnce();
 await waitFor(()=>expect(api).toHaveBeenCalledWith("/retention/deletion-requests/request-one/approve",{method:"POST",body:{reason:"Reviewed the pinned plan and retained audit limitations.",discovery_reference:"TEST-DISCOVERY",discovery_evidence_sha256:"a".repeat(64),acknowledge_retained_audit:true,acknowledge_physical_and_restore_limits:true}}));
});

test("authors and auditors can inspect without approving their own plan",async()=>{
 api.mockResolvedValue(detail);
 const {rerender}=render(<DeletionRequests requests={[request]} user={{id:"author",role:"admin"}} reload={vi.fn()} />);await inspect();
 expect(screen.queryByRole("button",{name:"Approve logical deletion plan"})).toBeNull();
 expect(screen.getByRole("button",{name:"Cancel deletion request"})).toBeTruthy();
 rerender(<DeletionRequests requests={[request]} user={{id:"auditor",role:"auditor"}} reload={vi.fn()} />);
 expect(screen.queryByRole("button",{name:"Cancel deletion request"})).toBeNull();
 expect(screen.queryByRole("button",{name:"Reject deletion request"})).toBeNull();
});
