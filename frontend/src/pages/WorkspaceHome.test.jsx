import React from "react";
import { beforeEach, expect, test, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import WorkspaceHome from "./WorkspaceHome";
import { api } from "../services/api";
import { useSession } from "../session";

vi.mock("../services/api", () => ({api:vi.fn()}));
vi.mock("../session", () => ({useSession:vi.fn()}));
beforeEach(() => {
  useSession.mockReturnValue({user:{name:"Owner",workspace:"Bluewater Team",role:"admin"}});
  api.mockImplementation(async path => path === "/team" ? [{id:"p1",name:"Fictional Reviewer",email:"review@example.invalid",role:"reviewer"}] : []);
});
test("named workspace groups records and their upload, invite and review actions", async () => {
  render(<MemoryRouter><WorkspaceHome/></MemoryRouter>);
  await screen.findByRole("heading",{name:"Company policies"});
  expect(screen.getByRole("heading",{name:"Bluewater Team"})).toBeTruthy();
  expect(screen.getByRole("heading",{name:"Company policies"})).toBeTruthy();
  expect(screen.getByRole("link",{name:"Add policy"}).getAttribute("href")).toBe("/policies/library/new");
  expect(screen.getByRole("link",{name:"Add activity"}).getAttribute("href")).toBe("/inbox/transactions?mode=csv");
  fireEvent.click(screen.getByRole("button",{name:"People",exact:true}));
  await screen.findByText("Fictional Reviewer");
  expect(screen.getByRole("link",{name:"Invite people"}).getAttribute("href")).toBe("/settings?section=Team");
  expect(screen.getByRole("navigation",{name:"Workspace sections"})).toBeTruthy();
});
test("auditors see the workspace inventory without create or invitation actions", async () => {
  useSession.mockReturnValue({user:{workspace:"Bluewater Team",role:"auditor"}});
  render(<MemoryRouter><WorkspaceHome/></MemoryRouter>);
  fireEvent.click(screen.getByRole("button",{name:"People",exact:true}));
  await screen.findByText("Fictional Reviewer");
  expect(screen.queryByRole("link",{name:"Add policy"})).toBeNull();
  expect(screen.queryByRole("link",{name:"Invite people"})).toBeNull();
});

test("workspace collections switch and search without leaving the current workspace", async () => {
  render(<MemoryRouter><WorkspaceHome/></MemoryRouter>);
  fireEvent.click(screen.getByRole("button",{name:"People",exact:true}));
  await screen.findByText("Fictional Reviewer");
  const input = screen.getByRole("textbox",{name:"Search people…"});
  fireEvent.change(input,{target:{value:"No match"}});
  expect(screen.queryByText("Fictional Reviewer")).toBeNull();
  expect(screen.getByText("No matching records")).toBeTruthy();
  fireEvent.click(screen.getByRole("button",{name:"Transactions",exact:true}));
  expect(screen.getByRole("textbox",{name:"Search transactions…"}).value).toBe("");
  expect(screen.getByRole("link",{name:"Import transactions"}).getAttribute("href")).toBe("/inbox/transactions?mode=csv");
  expect(screen.getByRole("heading",{name:"Bluewater Team"})).toBeTruthy();
});

test("a failed inventory is not reported as zero records", async () => {
  api.mockImplementation(async path => {
    if (path === "/policies") throw new Error("Policy inventory unavailable");
    return [];
  });
  render(<MemoryRouter><WorkspaceHome/></MemoryRouter>);
  await screen.findByText("Policy inventory unavailable");
  expect(screen.getByRole("button",{name:/Company policies.*In your policy library/}).textContent).toContain("—");
  expect(screen.queryByText("Your policy library starts here.")).toBeNull();
});
